#!/usr/bin/env python3
"""Public-article retrieval with safe redirect handling, RSS discovery and auditable outcomes."""
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
from html.parser import HTMLParser
from pathlib import Path
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
DASH = ROOT / 'docs/data/baltic_dashboard.json'
CLUSTER = ROOT / 'data/baltic_hybrid_clustered_events.json'
OUTPUT = ROOT / 'docs/data/baltic_source_evidence.json'
MAX_EVENTS = max(1, min(10, int(os.getenv('EVIDENCE_MAX_EVENTS', '8'))))
MAX_ARTICLES = 4
MAX_DISCOVERED = 2
MAX_CHARS = 7000
MAX_BYTES = 650000
UA = 'Mozilla/5.0 (compatible; BalticHybridMonitor/2.0; public-research)'

class Extractor(HTMLParser):
    SKIP = {'script', 'style', 'nav', 'footer', 'header', 'form', 'svg', 'noscript', 'aside'}
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack = []
        self.parts = []
        self.title = []
        self.in_title = False
        self.canonical = ''
    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag in self.SKIP:
            self.stack.append(tag)
        if tag == 'title':
            self.in_title = True
        if tag == 'link' and attrs.get('rel', '').lower() == 'canonical':
            self.canonical = attrs.get('href', '')
        if tag == 'meta' and attrs.get('property') == 'og:url' and not self.canonical:
            self.canonical = attrs.get('content', '')
    def handle_endtag(self, tag):
        if tag in self.SKIP and tag in self.stack:
            self.stack.remove(tag)
        if tag == 'title':
            self.in_title = False
    def handle_data(self, data):
        if self.in_title:
            self.title.append(data)
        if not self.stack and not self.in_title and data.strip():
            self.parts.append(data.strip())

# Resolve DNS and reject private/loopback/link-local targets on EVERY redirect hop.
# DNS rebinding remains a residual risk with urllib; this is a bounded public-source collector,
# not a generic URL-fetching API. Never accept arbitrary user-supplied URL parameters here.
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
    current = url
    seen = set()
    for hop in range(max_hops + 1):
        if not safe_url(current):
            raise ValueError('unsafe/non-HTTPS destination')
        if current in seen:
            raise ValueError('redirect loop')
        seen.add(current)
        req = urllib.request.Request(current, headers={
            'User-Agent': UA,
            'Accept': 'text/html,application/rss+xml,application/xml,text/plain;q=0.8',
            'Accept-Language': 'en-US,en;q=0.8'
        })
        try:
            response = OPENER.open(req, timeout=12)
        except urllib.error.HTTPError as exc:
            if exc.code in (301, 302, 303, 307, 308):
                target = exc.headers.get('Location', '')
                if not target:
                    raise ValueError('redirect without Location') from exc
                current = urllib.parse.urljoin(current, target)
                continue
            raise
        with response:
            content_type = response.headers.get('Content-Type', '').lower()
            if not any(x in content_type for x in ('html', 'xml', 'rss', 'text/plain')):
                raise ValueError('unsupported content type: ' + content_type[:60])
            content = response.read(MAX_BYTES + 1)
            if len(content) > MAX_BYTES:
                raise ValueError('page exceeds size limit')
            charset = response.headers.get_content_charset() or 'utf-8'
            return content.decode(charset, errors='replace'), current
    raise ValueError('too many redirects')

def article(url):
    try:
        raw, final = fetch(url)
        parser = Extractor()
        parser.feed(raw)
        body = re.sub(r'\s+', ' ', ' '.join(parser.parts)).strip()
        title = re.sub(r'\s+', ' ', ' '.join(parser.title)).strip()[:220]
        # Do not mistake search/consent/login pages for readable reporting.
        if len(body) < 450:
            return {'url': url, 'final_url': final, 'status': 'insufficient_text',
                    'text': '', 'page_title': title, 'error': 'less than 450 characters'}
        if any(term in (title + ' ' + body[:500]).lower() for term in (
                'before you continue to google', 'enable javascript to continue', 'sign in to continue reading')):
            return {'url': url, 'final_url': final, 'status': 'access_limited',
                    'text': '', 'page_title': title, 'error': 'consent/login/JS gate'}
        return {'url': url, 'final_url': final, 'status': 'retrieved',
                'text': body[:MAX_CHARS], 'page_title': title, 'text_chars': min(len(body), MAX_CHARS)}
    except Exception as exc:
        return {'url': url, 'status': 'unavailable', 'text': '', 'error': str(exc)[:180]}

def discover(title):
    """Bing News RSS: discovered links are search candidates, never confirmations."""
    q = re.sub(r'[^\w\s-]', ' ', title, flags=re.UNICODE).strip()[:105]
    if len(q) < 12:
        return []
    url = 'https://www.bing.com/news/search?' + urllib.parse.urlencode({'q': q, 'format': 'rss'})
    try:
        raw, _ = fetch(url)
        root = ET.fromstring(raw)
        found = []
        for item in root.findall('.//item')[:8]:
            link = (item.findtext('link') or '').strip()
            if link.startswith('https://') and safe_url(link) and link not in {x['url'] for x in found}:
                found.append({'url': link, 'title': (item.findtext('title') or '')[:250]})
        return found[:MAX_DISCOVERED]
    except Exception as exc:
        print('Supplementary RSS search unavailable: ' + str(exc)[:110])
        return []

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
        articles = [article(u) for u in urls]
        discovered = []
        if os.getenv('EVIDENCE_WEB_DISCOVERY', '1') == '1':
            for candidate in discover(title):
                if candidate['url'] not in urls:
                    a = article(candidate['url'])
                    a['discovery_title'] = candidate['title']
                    discovered.append(a)
        retrieved = sum(a['status'] == 'retrieved' for a in articles + discovered)
        selected.append({
            'event_id': eid, 'title': title, 'primary_country': item.get('primary_country'),
            'published_at': item.get('published_at'), 'articles': articles,
            'discovered_articles': discovered, 'retrieved_count': retrieved,
            'verification_status': 'NOT_INDEPENDENTLY_VERIFIED',
            'note': 'Retrieved text is not proof of truth, attribution, or independent corroboration.'
        })
        print(f'Event {eid}: accessible articles {retrieved}/{len(articles) + len(discovered)}')
        if len(selected) >= MAX_EVENTS:
            break
    output = {
        'generated_at': datetime.now(timezone.utc).isoformat(),
        'source_dashboard_generated_at': dash.get('generated_at'),
        'source_cluster_generated_at': cluster.get('generated_at'),
        'events': selected,
        'methodology': ('Bounded public HTML extraction with validated redirects and optional Bing News RSS '
                        'discovery. No automatic independent verification, attribution or fact-checking.')
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    tmp = OUTPUT.with_suffix('.json.tmp')
    tmp.write_text(json.dumps(output, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    tmp.replace(OUTPUT)
    count = sum(e['retrieved_count'] for e in selected)
    print(f'Evidence saved: {OUTPUT}; events: {len(selected)}; readable articles: {count}; '
          f'discovery: {os.getenv("EVIDENCE_WEB_DISCOVERY", "1")}')
    return 0

if __name__ == '__main__':
    sys.exit(main())
