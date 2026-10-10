#!/usr/bin/env python3
"""Collect cautiously matched publisher article text for Baltic Hybrid Monitor.

Only public HTTPS pages are fetched. A retrieved page is NOT independent verification.
"""
import ipaddress
import json
import os
import re
import socket
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from difflib import SequenceMatcher
from html import unescape
from html.parser import HTMLParser
from pathlib import Path
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
DASH = ROOT / 'docs/data/baltic_dashboard.json'
CLUSTER = ROOT / 'data/baltic_hybrid_clustered_events.json'
OUTPUT = ROOT / 'docs/data/baltic_source_evidence.json'
MAX_EVENTS = max(1, min(10, int(os.getenv('EVIDENCE_MAX_EVENTS', '8'))))
MAX_ARTICLES = 4
MAX_DISCOVERED = 5
MAX_CHARS = 7000
MAX_BYTES = 650000
UA = 'Mozilla/5.0 (compatible; BalticHybridMonitor/2.2; public-research)'
AGGREGATORS = ('google.com', 'bing.com', 'googleusercontent.com', 'yahoo.com',
               'duckduckgo.com', 'msn.com', 'feedly.com')
BLOCK_PHRASES = ('before you continue to google', 'enable javascript to continue',
                 'sign in to continue reading', 'verify you are human', 'access denied',
                 'just a moment...', 'checking your browser', 'enable cookies to continue')


def hostname(url):
    return (urllib.parse.urlsplit(url).hostname or '').lower().rstrip('.')


def aggregator(url):
    h = hostname(url)
    return any(h == d or h.endswith('.' + d) for d in AGGREGATORS)


class Extractor(HTMLParser):
    SKIP = {'script', 'style', 'nav', 'footer', 'header', 'form', 'svg', 'noscript', 'aside'}
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.skip_depth = 0
        self.title_depth = 0
        self.article_depth = 0
        self.article_seen = False
        self.parts = []
        self.article_parts = []
        self.title = []
        self.metadata = {}
        self.links = []
    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag in self.SKIP:
            self.skip_depth += 1
        if tag == 'title':
            self.title_depth += 1
        if tag == 'article':
            self.article_depth += 1
            self.article_seen = True
        if tag == 'meta':
            key = (a.get('property') or a.get('name') or '').lower()
            if key in ('og:title', 'twitter:title', 'article:published_time', 'description', 'og:description'):
                self.metadata[key] = a.get('content', '')
        if tag == 'link' and (a.get('rel') or '').lower() == 'canonical':
            self.metadata['canonical'] = a.get('href', '')
        if tag == 'a' and a.get('href'):
            self.links.append(a['href'])
    def handle_endtag(self, tag):
        if tag == 'article' and self.article_depth:
            self.article_depth -= 1
        if tag == 'title' and self.title_depth:
            self.title_depth -= 1
        if tag in self.SKIP and self.skip_depth:
            self.skip_depth -= 1
    def handle_data(self, data):
        value = data.strip()
        if not value:
            return
        if self.title_depth:
            self.title.append(value)
        elif not self.skip_depth:
            self.parts.append(value)
            if self.article_depth:
                self.article_parts.append(value)


def safe_url(url):
    try:
        p = urllib.parse.urlsplit(str(url))
        if p.scheme != 'https' or not p.hostname or p.username or p.password or p.port not in (None, 443):
            return False
        host = p.hostname.lower().rstrip('.')
        if host in {'localhost', 'metadata.google.internal'} or host.endswith(('.local', '.internal', '.localhost')):
            return False
        addresses = socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)
        return bool(addresses) and all(ipaddress.ip_address(a[4][0]).is_global for a in addresses)
    except (ValueError, OSError, TypeError):
        return False


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


OPENER = urllib.request.build_opener(NoRedirect())


def fetch(url, max_hops=5):
    current, seen = url, set()
    for _ in range(max_hops + 1):
        if not safe_url(current):
            raise ValueError('unsafe/non-HTTPS destination')
        if current in seen:
            raise ValueError('redirect loop')
        seen.add(current)
        req = urllib.request.Request(current, headers={
            'User-Agent': UA,
            'Accept': 'text/html,application/rss+xml,application/xml,text/plain;q=0.8',
            'Accept-Language': 'en-US,en;q=0.8'})
        try:
            response = OPENER.open(req, timeout=12)
        except urllib.error.HTTPError as exc:
            if exc.code in (301, 302, 303, 307, 308):
                location = exc.headers.get('Location')
                if not location:
                    raise ValueError('redirect without Location') from exc
                current = urllib.parse.urljoin(current, location)
                continue
            raise
        with response:
            content_type = response.headers.get('Content-Type', '').lower()
            if not any(x in content_type for x in ('html', 'xml', 'rss', 'text/plain')):
                raise ValueError('unsupported content type')
            content = response.read(MAX_BYTES + 1)
            if len(content) > MAX_BYTES:
                raise ValueError('page exceeds size limit')
            charset = response.headers.get_content_charset() or 'utf-8'
            return content.decode(charset, errors='replace'), current
    raise ValueError('too many redirects')


def clean_title(title):
    value = unescape(str(title or ''))
    value = re.split(r'\s+[|–—-]\s+', value)[0]
    return re.sub(r'\s+', ' ', value).strip()


def words(value):
    return set(re.findall(r'\w{4,}', clean_title(value).casefold(), re.UNICODE))


def title_match(expected, found):
    """Prevent a generic search result or unrelated publisher page counting as evidence."""
    a, b = words(expected), words(found)
    if len(a) < 3 or len(b) < 3:
        return False
    overlap = len(a & b) / min(len(a), len(b))
    ratio = SequenceMatcher(None, clean_title(expected).casefold(), clean_title(found).casefold()).ratio()
    return overlap >= 0.60 or (overlap >= 0.45 and ratio >= 0.62)


def article(url, expected_title):
    try:
        raw, final = fetch(url)
        if aggregator(final):
            return {'url': url, 'final_url': final, 'status': 'aggregator_only',
                    'text': '', 'error': 'Aggregator/search page is not publisher article text'}
        parser = Extractor()
        parser.feed(raw)
        page_title = clean_title(parser.metadata.get('og:title') or parser.metadata.get('twitter:title')
                                 or ' '.join(parser.title))[:220]
        canonical = parser.metadata.get('canonical', '')
        if canonical:
            canonical = urllib.parse.urljoin(final, canonical)
            if safe_url(canonical) and aggregator(canonical):
                return {'url': url, 'final_url': final, 'status': 'aggregator_only',
                        'text': '', 'page_title': page_title, 'error': 'Aggregator canonical URL'}
        body = re.sub(r'\s+', ' ', ' '.join(parser.article_parts if parser.article_parts else parser.parts)).strip()
        if any(term in (page_title + ' ' + body[:900]).casefold() for term in BLOCK_PHRASES):
            return {'url': url, 'final_url': final, 'status': 'access_limited',
                    'text': '', 'page_title': page_title, 'error': 'Login/consent/JS gate'}
        if not title_match(expected_title, page_title):
            return {'url': url, 'final_url': final, 'status': 'title_mismatch',
                    'text': '', 'page_title': page_title, 'error': 'Page title does not match monitored headline'}
        if len(body) < 600:
            return {'url': url, 'final_url': final, 'status': 'insufficient_text',
                    'text': '', 'page_title': page_title, 'error': 'Less than 600 characters'}
        if not parser.article_seen and len(body) < 1100:
            return {'url': url, 'final_url': final, 'status': 'insufficient_text',
                    'text': '', 'page_title': page_title, 'error': 'No article element and little body text'}
        return {'url': url, 'final_url': final, 'status': 'retrieved',
                'text': body[:MAX_CHARS], 'page_title': page_title,
                'text_chars': min(len(body), MAX_CHARS),
                'note': 'Text retrieval does not establish independent verification'}
    except Exception as exc:
        return {'url': url, 'status': 'unavailable', 'text': '', 'error': str(exc)[:180]}


def extract_candidates_from_google_landing(url):
    """Look for explicit publisher links in a Google News landing page, without bypassing access gates."""
    try:
        raw, final = fetch(url)
        if not aggregator(final):
            return [final]
        parser = Extractor()
        parser.feed(raw)
        candidates = []
        for href in parser.links:
            link = urllib.parse.urljoin(final, unescape(href))
            if link.startswith('https://') and not aggregator(link):
                candidates.append(link)
        return list(dict.fromkeys(candidates))[:5]
    except Exception:
        return []


def search_candidates(title):
    """Bing News RSS and Google News RSS discovery; results are unverified candidates."""
    query = clean_title(title)[:100]
    if len(words(query)) < 3:
        return []
    endpoints = [
        ('bing_rss', 'https://www.bing.com/news/search?' + urllib.parse.urlencode({'q': '"' + query + '"', 'format': 'rss'})),
        ('google_rss', 'https://news.google.com/rss/search?' + urllib.parse.urlencode({
            'q': '"' + query + '"', 'hl': 'en-US', 'gl': 'US', 'ceid': 'US:en'})),
    ]
    found, seen = [], set()
    for method, endpoint in endpoints:
        try:
            raw, _ = fetch(endpoint)
            root = ET.fromstring(raw)
            for item in root.findall('.//item')[:12]:
                item_title = item.findtext('title') or ''
                if not title_match(title, item_title):
                    continue
                links = [(item.findtext('link') or '').strip()]
                description = unescape(item.findtext('description') or '')
                links += re.findall(r'href=["\'](https://[^"\']+)', description)
                for href in links:
                    candidate = unescape(href).replace('&amp;', '&')
                    if not candidate.startswith('https://') or aggregator(candidate) or candidate in seen:
                        continue
                    if not safe_url(candidate):
                        continue
                    seen.add(candidate)
                    found.append({'url': candidate, 'title': item_title[:250], 'method': method})
                    if len(found) >= MAX_DISCOVERED:
                        return found
        except Exception as exc:
            print(method + ' discovery unavailable: ' + str(exc)[:110])
    return found


def main():
    if not DASH.exists() or not CLUSTER.exists():
        print('Missing dashboard or clustered events', file=sys.stderr)
        return 1
    dash = json.loads(DASH.read_text(encoding='utf-8'))
    cluster = json.loads(CLUSTER.read_text(encoding='utf-8'))
    lookup = {str(x.get('event_id')): x for x in cluster.get('events', [])
              if isinstance(x, dict) and x.get('event_id')}
    selected, seen = [], set()
    for item in (dash.get('top_events') or []) + (dash.get('recent_events') or []):
        if not isinstance(item, dict):
            continue
        eid = str(item.get('event_id') or '')
        if not eid or eid in seen:
            continue
        seen.add(eid)
        c = lookup.get(eid, {})
        urls = list(c.get('related_urls') or [])
        if item.get('url'):
            urls.append(item['url'])
        urls = list(dict.fromkeys(u for u in urls if isinstance(u, str) and u.startswith('https://')))[:MAX_ARTICLES]
        if not urls:
            continue
        title = str(item.get('title') or '')[:300]
        articles = [article(u, title) for u in urls]
        discovered = []
        if os.getenv('EVIDENCE_WEB_DISCOVERY', '1') == '1':
            candidates = []
            for u in urls:
                if aggregator(u):
                    candidates.extend({'url': x, 'title': title, 'method': 'landing_link'}
                                      for x in extract_candidates_from_google_landing(u))
            candidates.extend(search_candidates(title))
            known = set(urls)
            for candidate in candidates:
                link = candidate['url']
                if link in known or len(discovered) >= MAX_DISCOVERED:
                    continue
                known.add(link)
                record = article(link, title)
                record['discovery_title'] = candidate['title']
                record['discovery_method'] = candidate['method']
                discovered.append(record)
        retrieved = sum(a['status'] == 'retrieved' for a in articles + discovered)
        selected.append({
            'event_id': eid, 'title': title, 'primary_country': item.get('primary_country'),
            'published_at': item.get('published_at'), 'articles': articles,
            'discovered_articles': discovered, 'retrieved_count': retrieved,
            'verification_status': 'NOT_INDEPENDENTLY_VERIFIED',
            'note': 'Retrieved text is not proof of truth, attribution, or independent corroboration.'})
        print(f'Event {eid}: readable matched publisher pages {retrieved}/{len(articles) + len(discovered)}')
        if len(selected) >= MAX_EVENTS:
            break
    output = {
        'generated_at': datetime.now(timezone.utc).isoformat(),
        'source_dashboard_generated_at': dash.get('generated_at'),
        'source_cluster_generated_at': cluster.get('generated_at'),
        'events': selected,
        'methodology': ('Public HTTPS extraction; title matching and aggregator exclusion; '
                        'Google/Bing RSS discovery. Retrieved text is not independent verification.')}
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    tmp = OUTPUT.with_suffix('.json.tmp')
    tmp.write_text(json.dumps(output, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    tmp.replace(OUTPUT)
    print(f'Evidence saved: {OUTPUT}; events: {len(selected)}; '
          f'readable articles: {sum(e["retrieved_count"] for e in selected)}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
