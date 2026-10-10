#!/usr/bin/env python3
"""Standalone, read-only publisher URL discovery for Baltic Hybrid Monitor.

Does not modify source data, workflow, event IDs or dashboard. Only writes a
separate diagnostics JSON. Candidate URLs are NOT treated as verified evidence.
"""
import argparse
import collections
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


def unwrap_bing_click_url(link):
    """Decode Bing /ck/a destination locally; never follow a click-tracking URL."""
    parsed = urllib.parse.urlsplit(html.unescape(link))
    host = (parsed.hostname or '').lower()
    if host not in ('bing.com', 'www.bing.com') or not parsed.path.startswith('/ck/a'):
        return link, 'direct_link'
    params = urllib.parse.parse_qs(parsed.query)
    for key in ('url', 'u'):
        for raw in params.get(key, []):
            raw = urllib.parse.unquote(raw)
            if raw.startswith('https://'):
                return raw, 'bing_click_plain'
            if raw.startswith(('a1', 'a2')):
                encoded = raw[2:]
                try:
                    decoded = base64.urlsafe_b64decode(encoded + '=' * (-len(encoded) % 4)).decode('utf-8')
                    if decoded.startswith('https://'):
                        return decoded, 'bing_click_base64'
                except (ValueError, UnicodeDecodeError):
                    pass
    return link, 'bing_click_undecodable'



class SearchResultLinks(HTMLParser):
    """Keep visible anchor text and its surrounding heading (Bing result cards)."""
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.results = []
        self.current = None
        self.heading_depth = 0
    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag in ('h2', 'h3'):
            self.heading_depth += 1
        if tag == 'a' and attrs.get('href'):
            self.current = {'href': attrs['href'], 'text': [], 'heading': self.heading_depth > 0}
    def handle_data(self, data):
        if self.current is not None:
            self.current['text'].append(data)
    def handle_endtag(self, tag):
        if tag == 'a' and self.current is not None:
            self.results.append({'href': self.current['href'], 'text': ' '.join(self.current['text']).strip(), 'heading': self.current['heading']})
            self.current = None
        if tag in ('h2', 'h3'):
            self.heading_depth = max(0, self.heading_depth - 1)


def headline_similarity(expected_title, found_title):
    expected = normalized_title(expected_title)
    found = normalized_title(found_title)
    if len(expected) < 4 or len(found) < 3:
        return 0.0
    return len(expected & found) / max(1, len(expected | found))


def search_article_candidates(title, summary='', max_candidates=8):
    """Discover article candidates from visible search result titles, not URL slugs."""
    headline = re.split(r'\s+[-|–—]\s+', str(title or ''))[0].strip()
    report = {'queries': [], 'total_links_seen': 0, 'rejection_totals': {}}
    if not headline:
        return [], ['missing_title'], report
    queries = ['"' + headline[:135] + '"', headline[:135]]
    candidates, errors, seen = [], [], set()
    rejection_totals = collections.Counter()
    for query in queries:
        if len(candidates) >= max_candidates:
            break
        search_url = 'https://www.bing.com/search?' + urllib.parse.urlencode({'q': query, 'setlang': 'en-US'})
        stats = {'query': query, 'http_final_host': None, 'response_chars': 0,
                 'html_title': None, 'anchor_count': 0, 'rejections': {},
                 'candidate_count': 0, 'sample_links': [], 'decoded_bing_clicks': 0,
                 'title_matched_links': 0, 'error': None}
        rejects = collections.Counter()
        try:
            final, page = request_page(search_url)
            stats['http_final_host'] = urllib.parse.urlsplit(final).hostname
            stats['response_chars'] = len(page)
            match = re.search(r'<title[^>]*>(.*?)</title>', page, re.I | re.S)
            if match:
                stats['html_title'] = html.unescape(re.sub(r'<[^>]*>', '', match.group(1)))[:120]
            parser = SearchResultLinks()
            parser.feed(page)
            stats['anchor_count'] = len(parser.results)
            for entry in parser.results:
                raw = entry['href']
                link, link_method = unwrap_bing_click_url(raw)
                parsed = urllib.parse.urlsplit(link)
                if link_method == 'bing_click_base64':
                    stats['decoded_bing_clicks'] += 1
                host = (parsed.hostname or '').lower()
                visible_title = re.sub(r'\s+', ' ', entry['text']).strip()[:300]
                similarity = headline_similarity(title, visible_title)
                if len(stats['sample_links']) < 12 and (entry['heading'] or similarity >= .3):
                    stats['sample_links'].append({'host': host, 'path_prefix': parsed.path[:75],
                                                  'title': visible_title[:120], 'similarity': round(similarity, 3),
                                                  'heading': entry['heading']})
                if parsed.scheme != 'https' or not host:
                    rejects['invalid_https'] += 1
                    continue
                if aggregator(link) or host.endswith(('gstatic.com', 'microsoft.com', 'msn.com')):
                    rejects['aggregator_or_asset'] += 1
                    continue
                if link in seen:
                    rejects['duplicate'] += 1
                    continue
                seen.add(link)
                if len(link) > 1200:
                    rejects['oversized_url'] += 1
                    continue
                # Heading results are preferred, but title match is required either way.
                if similarity < 0.62:
                    rejects['low_visible_title_similarity'] += 1
                    continue
                stats['title_matched_links'] += 1
                if not safe_https(link):
                    rejects['unsafe_or_dns_failed'] += 1
                    continue
                candidates.append({'url': link, 'method': link_method + '_visible_title',
                                   'search_result_title': visible_title,
                                   'search_title_similarity': round(similarity, 3),
                                   'verification': 'unverified'})
                stats['candidate_count'] += 1
                if len(candidates) >= max_candidates:
                    break
        except Exception as exc:
            stats['error'] = str(exc)[:150]
            errors.append('bing_search: ' + stats['error'])
        stats['rejections'] = dict(rejects)
        rejection_totals.update(rejects)
        report['total_links_seen'] += stats['anchor_count']
        report['queries'].append(stats)
    report['rejection_totals'] = dict(rejection_totals)
    report['candidate_count'] = len(candidates)
    return candidates, errors, report

def verify_article_candidate(candidate, title):
    """Verify title similarity on publisher HTML; never infer from search snippet alone."""
    try:
        final, page = request_page(candidate['url'])
        if aggregator(final):
            return None
        page_title = ''
        match = re.search(r'<title[^>]*>(.*?)</title>', page, re.I | re.S)
        if match:
            page_title = html.unescape(re.sub(r'<[^>]+>', '', match.group(1))).strip()
        if not page_title:
            match = re.search(r'<meta[^>]+property=["\']og:title["\'][^>]+content=["\']([^"\']+)', page, re.I)
            if match:
                page_title = html.unescape(match.group(1))
        expected, actual = normalized_title(title), normalized_title(page_title)
        similarity = len(expected & actual) / max(1, len(expected | actual))
        if len(expected) >= 4 and similarity >= 0.65:
            return {'url': final, 'method': 'publisher_page_title_match', 'title_similarity': round(similarity, 3), 'page_title': page_title[:240], 'verification': 'title_matched_not_independently_corroborated'}
    except Exception as exc:
        candidate['verification_error'] = str(exc)[:120]
    return None


def resolve(item):
    original = str(item.get('url') or '').strip()
    title = str(item.get('title') or '')
    summary = str(item.get('summary') or '')
    result = {'item_id': item.get('id'), 'title': title, 'original_rss_url': original,
              'source_group': item.get('source_group'), 'publisher_url': None,
              'status': 'unresolved', 'method': None, 'candidates': [], 'diagnostics': {}}
    if not original.startswith('https://'):
        result['status'] = 'invalid_input_url'
        return result
    if not aggregator(original):
        result.update({'publisher_url': original, 'status': 'direct_publisher_url', 'method': 'rss_link'})
        return result
    # Preserve the inexpensive legacy decoder, but do not rely on Google HTML.
    decoded = decode_legacy_google_url(original)
    if decoded:
        result['candidates'].append({'url': decoded, 'method': 'legacy_google_rss_base64', 'verification': 'unverified'})
    discovered, errors, search_report = search_article_candidates(title, summary)
    existing = {x['url'] for x in result['candidates']}
    result['candidates'].extend(x for x in discovered if x['url'] not in existing)
    result['diagnostics']['search_errors'] = errors
    result['diagnostics']['search_report'] = search_report
    for candidate in result['candidates'][:8]:
        verified = verify_article_candidate(candidate, title)
        if verified:
            result.update({'publisher_url': verified['url'], 'status': 'publisher_page_title_matched', 'method': verified['method']})
            result['matched_article'] = verified
            return result
    result['status'] = 'candidates_unverified' if result['candidates'] else ('search_failed' if errors else 'no_publisher_match')
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
              'note': 'Candidate URL is not article-text evidence and is not independent verification. Diagnostic query samples may contain headline text.',
              'summary': {'processed': len(results), 'statuses': counts}, 'results': results}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    temp = args.output.with_suffix(args.output.suffix + '.tmp')
    temp.write_text(json.dumps(output, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    temp.replace(args.output)
    print('Saved diagnostic:', args.output)
    print('Summary:', json.dumps(counts, ensure_ascii=False))


if __name__ == '__main__':
    main()
