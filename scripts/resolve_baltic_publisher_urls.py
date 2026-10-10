#!/usr/bin/env python3
"""Read-only Baltic event source discovery. Free RSS; no API keys or production writes."""
import argparse
import html
import json
import re
import urllib.parse
import urllib.request
import urllib.error
import xml.etree.ElementTree as ET
from collections import Counter
from datetime import datetime, timezone
from difflib import SequenceMatcher
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INPUT = ROOT / "data/baltic_hybrid_raw_news.json"
OUTPUT = ROOT / "docs/data/baltic_publisher_urls.json"
CONFIG = ROOT / "config/baltic_sources.json"
UA = "BalticHybridMonitor-SourceDiscovery/1.0 (+public RSS research)"
STOP = set("the and for with from after over about into says said amid ahead could would between russia russian baltic baltics estonia estonian latvia latvian lithuania lithuanian poland polish news article latest report reports".split())
BLOCKED = {"news.google.com", "google.com", "www.google.com", "www.bing.com", "bing.com", "www.gstatic.com"}


def is_publisher(url):
    try:
        u = urllib.parse.urlsplit(url)
        host = (u.hostname or "").lower().rstrip(".")
        return (u.scheme == "https" and host and not u.username and not u.password
                and u.port in (None, 443) and host not in BLOCKED
                and not host.endswith((".google.com", ".gstatic.com", ".googleusercontent.com"))
                and not host.endswith((".local", ".internal", ".localhost")))
    except ValueError:
        return False


def fetch_xml(url):
    # All requested hosts are either configured RSS providers or Google News RSS.
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/rss+xml,application/xml,text/xml,*/*"})
    with urllib.request.urlopen(req, timeout=12) as response:
        raw = response.read(1_500_001)
        if len(raw) > 1_500_000:
            raise ValueError("rss_too_large")
        return ET.fromstring(raw)


def clean(s):
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]*>", " ", str(s or "")))).strip()


def title_base(s):
    return re.split(r"\s+[|–—]\s+|\s+-\s+(?=[A-Z])", clean(s), maxsplit=1)[0]


def words(s):
    return {w for w in re.findall(r"[a-z0-9]{4,}", title_base(s).lower()) if w not in STOP}


def rss_entries(root, origin, max_items=120):
    items = root.findall(".//item")[:max_items]
    out = []
    for node in items:
        title = clean(node.findtext("title"))
        link = clean(node.findtext("link"))
        if not link:
            link = clean(node.findtext("{http://www.w3.org/2005/Atom}link"))
        desc = clean(node.findtext("description"))[:500]
        pub = clean(node.findtext("pubDate"))
        source = node.find("source")
        source_name = clean(source.text) if source is not None else ""
        if title and link.startswith("https://"):
            out.append({"title": title, "url": link, "description": desc,
                        "published": pub, "publisher": source_name or origin,
                        "discovered_via": origin})
    return out


def query_terms(item):
    title = title_base(item.get("title", ""))
    tokens = [x for x in re.findall(r"[\w-]{4,}", title) if x.lower() not in STOP]
    # Preserve meaningful word order, prefer a short human-like search.
    return " ".join(tokens[:6]) or title[:90]


def rank(item, candidate):
    a, b = words(item.get("title", "")), words(candidate.get("title", ""))
    if len(a) < 2 or len(b) < 2:
        return 0.0
    overlap = len(a & b) / max(1, len(a | b))
    coverage = len(a & b) / max(1, len(a))
    sequence = SequenceMatcher(None, title_base(item.get("title", "")).lower(), title_base(candidate.get("title", "")).lower()).ratio()
    return round(0.40 * overlap + 0.40 * coverage + 0.20 * sequence, 3)


def main():
    ap = argparse.ArgumentParser(description="Free RSS-based event source discovery; diagnostic only")
    ap.add_argument("--input", type=Path, default=INPUT)
    ap.add_argument("--output", type=Path, default=OUTPUT)
    ap.add_argument("--limit", type=int, default=10)
    ap.add_argument("--only-google", action="store_true")
    args = ap.parse_args()
    if not 1 <= args.limit <= 30:
        ap.error("--limit must be between 1 and 30")
    if args.output.resolve() in {args.input.resolve(), CONFIG.resolve()}:
        ap.error("output cannot overwrite source files")
    source = json.loads(args.input.read_text(encoding="utf-8"))
    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    items = [x for x in source.get("items", []) if isinstance(x, dict)]
    if args.only_google:
        items = [x for x in items if "news.google.com" in str(x.get("url", ""))]
    items = items[:args.limit]
    direct = []
    feed_stats = []
    for feed in config.get("rss_sources", []):
        if feed.get("source_group") == "google_news_search":
            continue
        url = feed.get("url", "")
        if not url.startswith("https://"):
            continue
        try:
            found = rss_entries(fetch_xml(url), feed.get("name", "direct_rss"))
            direct.extend(x for x in found if is_publisher(x["url"]))
            feed_stats.append({"feed": feed.get("name"), "count": len(found), "status": "ok"})
        except Exception as exc:
            feed_stats.append({"feed": feed.get("name"), "count": 0, "status": "error", "error": str(exc)[:150]})
    results = []
    for item in items:
        query = query_terms(item)
        google = []
        search_error = None
        try:
            url = "https://news.google.com/rss/search?" + urllib.parse.urlencode({"q": query, "hl": "en-US", "gl": "US", "ceid": "US:en"})
            google = rss_entries(fetch_xml(url), "google_news_rss", max_items=60)
        except Exception as exc:
            search_error = str(exc)[:160]
        original = str(item.get("url") or "")
        candidates = []
        seen = set()
        # The existing direct source is useful even when external search fails.
        pool = direct + google + ([{"title": item.get("title", ""), "url": original, "publisher": item.get("source_name", "original_rss"), "discovered_via": "original_direct_rss"}] if is_publisher(original) else [])
        for c in pool:
            u = c["url"]
            if u in seen or u == original or not is_publisher(u):
                continue
            seen.add(u)
            score = rank(item, c)
            if score < 0.55:
                continue
            candidates.append({"url": u, "title": c["title"], "publisher": c["publisher"],
                               "discovered_via": c["discovered_via"], "title_similarity": score,
                               "verification": "title_match_only_not_independent_confirmation"})
        candidates.sort(key=lambda c: c["title_similarity"], reverse=True)
        # Search RSS links remain useful as discovery leads, not as publisher URLs.
        leads = []
        for c in google:
            score = rank(item, c)
            if score >= 0.60 and not is_publisher(c["url"]):
                leads.append({"title": c["title"], "aggregator_url": c["url"],
                              "publisher_label": c["publisher"], "title_similarity": score})
        candidates = candidates[:5]
        results.append({"item_id": item.get("id"), "title": item.get("title"),
                        "original_rss_url": original, "source_group": item.get("source_group"),
                        "search_query": query, "publisher_url": candidates[0]["url"] if candidates else None,
                        "status": "publisher_candidates_found" if candidates else ("aggregator_leads_only" if leads else "no_publisher_match"),
                        "method": "direct_rss_event_title_match" if candidates else None,
                        "candidates": candidates, "google_news_leads": leads[:5],
                        "diagnostics": {"direct_rss_pool": len(direct), "google_news_search_results": len(google),
                                        "search_error": search_error}})
        print(str(item.get("id", ""))[:16], results[-1]["status"], "publisher candidates:", len(candidates), "google leads:", len(leads))
    counts = dict(Counter(x["status"] for x in results))
    output = {"generated_at": datetime.now(timezone.utc).isoformat(),
              "source_input_generated_at": source.get("generated_at"),
              "diagnostic_only": True, "pipeline_integrated": False,
              "note": "RSS title matches are discovery leads, not verified article bodies or independent event confirmations.",
              "summary": {"processed": len(results), "statuses": counts, "direct_rss_entries": len(direct),
                          "feeds_ok": sum(x["status"] == "ok" for x in feed_stats),
                          "feeds_failed": sum(x["status"] == "error" for x in feed_stats)},
              "feed_diagnostics": feed_stats, "results": results}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    tmp = args.output.with_suffix(args.output.suffix + ".tmp")
    tmp.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp.replace(args.output)
    print("Saved diagnostic:", args.output)
    print("Summary:", json.dumps(counts))


if __name__ == "__main__":
    main()
