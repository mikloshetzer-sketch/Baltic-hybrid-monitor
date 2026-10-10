#!/usr/bin/env python3
"""Bounded, auditable article enrichment for the Baltic Hybrid Monitor."""
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
import ipaddress
import socket
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
DASH = ROOT / 'docs/data/baltic_dashboard.json'
CLUSTER = ROOT / 'data/baltic_hybrid_clustered_events.json'
OUTPUT = ROOT / 'docs/data/baltic_source_evidence.json'
MAX_EVENTS = min(10, max(1, int(os.getenv('EVIDENCE_MAX_EVENTS', '8'))))
MAX_ARTICLES = 4
MAX_CHARS = 6500
UA = 'BalticHybridMonitor-Research/1.0 (public OSINT report)'

class Extractor(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.ignore = 0
        self.parts = []
        self.title = []
        self.in_title = False
    def handle_starttag(self, tag, attrs):
        if tag in ('script','style','nav','footer','header','form','svg','noscript'):
            self.ignore += 1
        if tag == 'title': self.in_title = True
    def handle_endtag(self, tag):
        if tag in ('script','style','nav','footer','header','form','svg','noscript'):
            self.ignore = max(0,self.ignore-1)
        if tag == 'title': self.in_title = False
    def handle_data(self, data):
        if self.in_title: self.title.append(data)
        if not self.ignore and data.strip(): self.parts.append(data.strip())

def safe_url(url):
    try:
        p = urllib.parse.urlsplit(str(url))
        if p.scheme != 'https' or not p.hostname or p.username or p.password or p.port not in (None,443): return False
        host = p.hostname.lower().rstrip('.')
        if host in ('localhost',) or host.endswith(('.local','.internal','.localhost')): return False
        addresses = socket.getaddrinfo(host,443,type=socket.SOCK_STREAM)
        return bool(addresses) and all(ipaddress.ip_address(a[4][0]).is_global for a in addresses)
    except (ValueError, OSError, TypeError): return False

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise urllib.error.HTTPError(req.full_url,code,'redirect blocked',headers,fp)
OPENER = urllib.request.build_opener(NoRedirect())

def get(url, limit=450000):
    if not safe_url(url): raise ValueError('unsafe or non-HTTPS URL')
    req = urllib.request.Request(url,headers={'User-Agent':UA,'Accept':'text/html,application/rss+xml,application/xml;q=0.8'})
    with OPENER.open(req,timeout=12) as res:
        content_type = res.headers.get('Content-Type','').lower()
        if not any(x in content_type for x in ('html','xml','rss','text/plain')): raise ValueError('unsupported content type')
        data = res.read(limit+1)
        if len(data)>limit: raise ValueError('page exceeds size limit')
        charset = res.headers.get_content_charset() or 'utf-8'
        return data.decode(charset,errors='replace')

def extract(url):
    try:
        raw = get(url)
        parser = Extractor(); parser.feed(raw)
        text = re.sub(r'\s+',' ',' '.join(parser.parts)).strip()
        if len(text)<350: return {'url':url,'status':'insufficient_text','text':'','page_title':' '.join(parser.title)[:220]}
        return {'url':url,'status':'retrieved','text':text[:MAX_CHARS], 'page_title':' '.join(parser.title)[:220]}
    except Exception as exc:
        return {'url':url,'status':'unavailable','text':'','error':str(exc)[:160]}

def discover(title):
    # RSS discovery only: search results are candidates, not independent confirmations.
    q = re.sub(r'[^\w\s-]',' ',title,flags=re.UNICODE).strip()[:110]
    if len(q)<10: return []
    url = 'https://www.google.com/search?' + urllib.parse.urlencode({'q':q,'tbm':'nws','output':'rss'})
    # Google's RSS support varies; failure simply means no discovered candidates.
    try:
        root = ET.fromstring(get(url,limit=180000))
        found=[]
        for item in root.findall('.//item')[:5]:
            link=(item.findtext('link') or '').strip()
            if link.startswith('https://') and safe_url(link): found.append({'url':link,'title':(item.findtext('title') or '')[:250]})
        return found[:2]
    except Exception: return []

def main():
    if not DASH.exists() or not CLUSTER.exists():
        print('Missing dashboard or clustered events',file=sys.stderr); return 1
    dash=json.loads(DASH.read_text(encoding='utf-8'))
    clustered=json.loads(CLUSTER.read_text(encoding='utf-8'))
    lookup={str(x.get('event_id')):x for x in clustered.get('events',[]) if isinstance(x,dict) and x.get('event_id')}
    selected=[]; seen=set()
    for item in (dash.get('top_events') or [])+(dash.get('recent_events') or []):
        if not isinstance(item,dict): continue
        eid=str(item.get('event_id') or '')
        if not eid or eid in seen: continue
        seen.add(eid); cluster=lookup.get(eid,{})
        urls=list(cluster.get('related_urls') or [])
        if item.get('url'): urls.append(item['url'])
        urls=list(dict.fromkeys(u for u in urls if isinstance(u,str) and u.startswith('https://')))[:MAX_ARTICLES]
        if not urls: continue
        title=str(item.get('title') or '')[:300]
        articles=[extract(u) for u in urls]
        # Supplementary search is opt-in and intentionally bounded.
        discovered=[]
        if os.getenv('EVIDENCE_WEB_DISCOVERY','0')=='1':
            for candidate in discover(title):
                if candidate['url'] not in urls:
                    article=extract(candidate['url']); article['discovery_title']=candidate['title']
                    discovered.append(article)
        selected.append({'event_id':eid,'title':title,'primary_country':item.get('primary_country'),
            'published_at':item.get('published_at'),'articles':articles,'discovered_articles':discovered[:2],
            'retrieved_count':sum(a['status']=='retrieved' for a in articles+discovered[:2]),
            'verification_status':'NOT_INDEPENDENTLY_VERIFIED',
            'note':'Text retrieval does not establish truth, attribution or independent confirmation.'})
        if len(selected)>=MAX_EVENTS: break
    output={'generated_at':datetime.now(timezone.utc).isoformat(),
        'source_dashboard_generated_at':dash.get('generated_at'),
        'source_cluster_generated_at':clustered.get('generated_at'),
        'events':selected,'methodology':'Bounded retrieval of public HTML text; discovered links are candidates only; no factual or source-independence verification.'}
    OUTPUT.parent.mkdir(parents=True,exist_ok=True)
    temp=OUTPUT.with_suffix('.json.tmp');temp.write_text(json.dumps(output,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');temp.replace(OUTPUT)
    print(f'Evidence saved: {OUTPUT}; events: {len(selected)}; readable articles: {sum(e["retrieved_count"] for e in selected)}')
    return 0
if __name__=='__main__':sys.exit(main())
