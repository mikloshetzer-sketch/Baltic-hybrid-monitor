#!/usr/bin/env python3
"""Standalone, read-only publisher URL discovery for Baltic Hybrid Monitor.

Does not modify source data, workflow, event IDs or dashboard. Only writes a
separate diagnostics JSON. Candidate URLs are NOT treated as verified evidence.
"""
import argparse
import base64
import xml.etree.ElementTree as ET
import html
import ipaddress
import json
import re
import socket
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUT = ROOT / 'data/baltic_hybrid_raw_news.json'
DEFAULT_OUTPUT = ROOT / 'docs/data/baltic_publisher_urls.json'
UA = 'Mozilla/5.0 (compatible; BalticHybridMonitorPublisherURLDiagnostic/1.0)'
MAX_BYTES = 3_000_000  # Diagnostic Google News HTML can exceed 400 KB
AGGREGATORS = ('news.google.com', 'google.com', 'www.google.com', 'bing.com', 'www.bing.com')


def safe_https(url):
    try:
        p = urllib.parse.urlsplit(url)
        if p.scheme != 'https' or not p.hostname or p.username or p.password or p.port not in (None, 443):
            return False
        host = p.hostname.lower().rstrip('.')
        if host in ('localhost', 'metadata.google.internal') or host.endswith(('.local', '.internal', '.localhost')):
            return False
        addresses = socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)
        return bool(addresses) and all(ipaddress.ip_address(a[4][0]).is_global for a in addresses)
    except (ValueError, OSError, TypeError):
        return False


def aggregator(url):
    host = (urllib.parse.urlsplit(url).hostname or '').lower()
    return host in AGGREGATORS or host.endswith('.google.com') or host.endswith('.googleusercontent.com')


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


OPENER = urllib.request.build_opener(NoRedirect())


def request_page(url, max_redirects=4):
    seen = set()
    for _ in range(max_redirects + 1):
        if not safe_https(url):
            raise ValueError('blocked_non_public_https_url')
        if url in seen:
            raise ValueError('redirect_loop')
        seen.add(url)
        req = urllib.request.Request(url, headers={'User-Agent': UA, 'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.8', 'Accept-Language': 'en-US,en;q=0.8'})
        try:
            response = OPENER.open(req, timeout=9)
        except urllib.error.HTTPError as exc:
            if exc.code in (301, 302, 303, 307, 308):
                location = exc.headers.get('Location')
                if not location:
                    raise ValueError('redirect_without_location') from exc
                url = urllib.parse.urljoin(url, location)
                continue
            raise ValueError('http_' + str(exc.code)) from exc
        with response:
            ctype = response.headers.get('Content-Type', '').lower()
            if not any(t in ctype for t in ('text/html', 'application/xhtml', 'text/plain', 'application/xml', 'application/rss+xml', 'text/xml')):
                raise ValueError('unsupported_content_type')
            raw = response.read(MAX_BYTES + 1)
            if len(raw) > MAX_BYTES:
                raise ValueError('oversized_response')
            charset = response.headers.get_content_charset() or 'utf-8'
            return url, raw.decode(charset, errors='replace')
    raise ValueError('too_many_redirects')


class Links(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.urls = []
    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'a' and attrs.get('href'):
            self.urls.append(('html_anchor', attrs['href']))
        if tag == 'link' and attrs.get('rel') and attrs.get('href'):
            rel = str(attrs['rel']).lower()
            if 'canonical' in rel or 'alternate' in rel:
                self.urls.append(('html_' + rel.replace(' ', '_'), attrs['href']))
        for key in ('data-n-a-url', 'data-url', 'data-href'):
            if attrs.get(key):
                self.urls.append(('html_' + key, attrs[key]))


def title_words(value):
    value = re.split(r'\s+[|–—-]\s+', str(value or ''))[0].lower()
    return {w for w in re.findall(r'[a-z]{4,}', value) if w not in {'with', 'from', 'after', 'that', 'this', 'their', 'about', 'into', 'over', 'says', 'news'}}


def candidate_from_html(page, source_url, title):
    parser = Links()
    parser.feed(page)
    entries = parser.urls
    # Some Google News HTML embeds escaped absolute publisher links in JSON.
    for match in re.finditer(r'https?:(?:\\/\\/|//)[^\s"\'<>]{12,400}', page):
        raw = match.group(0).replace('\\/', '/')
        entries.append(('embedded_url', raw))
    found = []
    seen = set()
    title_set = title_words(title)
    for method, raw in entries:
        url = urllib.parse.urljoin(source_url, html.unescape(raw).replace('\\u0026', '&'))
        p = urllib.parse.urlsplit(url)
        if p.scheme != 'https' or not p.hostname or aggregator(url) or url in seen:
            continue
        seen.add(url)
        # Generic page links are not trustworthy as article matches.
        overlap = len(title_set.intersection(title_words(urllib.parse.unquote(p.path).replace('-', ' '))))
        if method == 'html_anchor' and overlap < 2:
            continue
        if method == 'embedded_url' and overlap < 3:
            continue
        found.append({'url': url, 'method': method, 'title_path_overlap': overlap})
    return found[:12]


def decode_legacy_google_url(url):
    """Decode only old-style RSS IDs that actually contain a publisher URL.

    Modern AU_yq... Google News identifiers contain no publisher URL; never
    manufacture one from those identifiers.
    """
    match = re.search(r'/rss/articles/([A-Za-z0-9_-]+)', url)
    if not match:
        return None
    token = match.group(1)
    try:
        data = base64.urlsafe_b64decode(token + '=' * (-len(token) % 4))
    except (ValueError, Exception):
        return None
    for candidate in re.findall(rb'https://[^\x00\s\x02-\x1f"<>]{8,1500}', data):
        target = candidate.decode('utf-8', errors='ignore').rstrip('\\')
        if target.startswith('https://') and not aggregator(target) and safe_https(target):
            return target
    return None


def normalized_title(value):
    # RSS headlines often append a publisher name after a dash.
    value = re.split(r'\s+[-|–—]\s+', str(value or ''))[0]
    return title_words(value)


def search_bing_rss(title):
    """Public RSS search, strictly diagnostic; does not trust a search snippet."""
    base_title = re.split(r'\s+[-|–—]\s+', title)[0].strip()
    query = '"' + base_title[:115] + '"'
    url = 'https://www.bing.com/news/search?' + urllib.parse.urlencode({'q': query, 'format': 'rss', 'setlang': 'en-US'})
    _, xml_text = request_page(url)
    root = ET.fromstring(xml_text)
    results = []
    expected = normalized_title(title)
    for node in root.findall('.//item')[:15]:
        result_title = node.findtext('title') or ''
        result_url = html.unescape(node.findtext('link') or '').strip()
        if not result_url.startswith('https://') or aggregator(result_url):
            continue
        found = normalized_title(result_title)
        if len(expected) < 4 or not found:
            continue
        overlap = len(expected & found) / max(len(expected), len(found))
        if overlap < 0.72:
            continue
        if not safe_https(result_url):
            continue
        results.append({'url': result_url, 'method': 'bing_news_rss_title_match',
                        'title_overlap': round(overlap, 3), 'search_title': result_title})
    return results[:5]


def resolve(item):
    original = str(item.get('url') or '').strip()
    title = str(item.get('title') or '')
    result = {'item_id': item.get('id'), 'title': title, 'original_rss_url': original,
              'source_group': item.get('source_group'), 'publisher_url': None,
              'status': 'unresolved', 'method': None, 'candidates': []}
    if not original.startswith('https://'):
        result['status'] = 'invalid_input_url'
        return result
    if not aggregator(original):
        result.update({'publisher_url': original, 'status': 'direct_publisher_url', 'method': 'rss_link'})
        return result
    result['diagnostics'] = {}
    try:
        decoded = decode_legacy_google_url(original)
        if decoded:
            result.update({'publisher_url': decoded, 'status': 'decoded_publisher_candidate_unverified',
                           'method': 'legacy_google_rss_base64'})
            return result
        result['diagnostics']['rss_id'] = 'no_embedded_publisher_url'
    except Exception as exc:
        result['diagnostics']['rss_id_error'] = str(exc)[:160]
    try:
        final, page = request_page(original)
        if not aggregator(final):
            result.update({'publisher_url': final, 'status': 'redirect_to_publisher', 'method': 'http_redirect'})
            return result
        candidates = candidate_from_html(page, final, title)
        # Google static assets and page scaffolding are never publisher candidates.
        candidates = [c for c in candidates if not (urllib.parse.urlsplit(c['url']).hostname or '').endswith('gstatic.com')]
        result['candidates'] = candidates
        result['diagnostics']['html'] = 'no_verified_publisher_url'
    except Exception as exc:
        result['diagnostics']['html_error'] = str(exc)[:160]
    try:
        matches = search_bing_rss(title)
        result['candidates'].extend(matches)
        if len(matches) == 1:
            result.update({'publisher_url': matches[0]['url'],
                           'status': 'publisher_candidate_unverified',
                           'method': 'bing_news_rss_title_match'})
        elif len(matches) > 1:
            result['status'] = 'multiple_publisher_candidates'
        else:
            result['status'] = 'no_publisher_match'
    except Exception as exc:
        result['status'] = 'search_failed'
        result['diagnostics']['search_error'] = str(exc)[:160]
    return result


def main():
    parser = argparse.ArgumentParser(description='Standalone publisher URL diagnostic; no changes to monitor pipeline')
    parser.add_argument('--input', type=Path, default=DEFAULT_INPUT)
    parser.add_argument('--output', type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument('--limit', type=int, default=10)
    parser.add_argument('--only-google', action='store_true', help='Only diagnose Google News URLs')
    args = parser.parse_args()
    if args.limit < 1 or args.limit > 30:
        parser.error('--limit must be between 1 and 30')
    if args.input.resolve() == args.output.resolve():
        parser.error('output cannot overwrite input')
    data = json.loads(args.input.read_text(encoding='utf-8'))
    items = data.get('items') or []
    if not isinstance(items, list):
        parser.error('input JSON must have an items array')
    if args.only_google:
        items = [x for x in items if isinstance(x, dict) and aggregator(str(x.get('url') or ''))]
    else:
        items = [x for x in items if isinstance(x, dict)]
    results = []
    for item in items[:args.limit]:
        result = resolve(item)
        results.append(result)
        print(f"{str(result['item_id'])[:16]}: {result['status']} | {result.get('publisher_url') or '-'} | {result.get('diagnostics', {})}")
    counts = {s: sum(x['status'] == s for x in results) for s in sorted({x['status'] for x in results})}
    output = {'generated_at': datetime.now(timezone.utc).isoformat(),
              'source_input_generated_at': data.get('generated_at'),
              'diagnostic_only': True, 'pipeline_integrated': False,
              'note': 'Candidate URL is not article-text evidence and is not independent verification.',
              'summary': {'processed': len(results), 'statuses': counts}, 'results': results}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    temp = args.output.with_suffix(args.output.suffix + '.tmp')
    temp.write_text(json.dumps(output, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    temp.replace(args.output)
    print('Saved diagnostic:', args.output)
    print('Summary:', json.dumps(counts, ensure_ascii=False))


if __name__ == '__main__':
    main()
