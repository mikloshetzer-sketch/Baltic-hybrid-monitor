import json
import os
import re
import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Any, Optional
from urllib.parse import urlparse, urljoin

import feedparser
import requests
from bs4 import BeautifulSoup
from dateutil import parser as date_parser


ROOT = Path(__file__).resolve().parents[1]

CONFIG_PATH = ROOT / "config" / "baltic_sources.json"
RAW_OUTPUT = ROOT / "data" / "baltic_hybrid_raw_news.json"
DOCS_OUTPUT = ROOT / "docs" / "data" / "baltic_hybrid_raw_news.json"


COUNTRY_KEYWORDS = {
    "Estonia": ["estonia", "estonian", "tallinn", "narva", "tartu", "ida-viru", "ida-virumaa"],
    "Latvia": ["latvia", "latvian", "riga", "daugavpils", "latgale"],
    "Lithuania": ["lithuania", "lithuanian", "vilnius", "kaunas", "klaipeda", "klaipėda", "suwalki", "suwałki"],
    "Poland": ["poland", "polish", "warsaw", "bialystok", "białystok", "suwalki", "suwałki", "gdańsk", "gdansk"]
}


CATEGORY_KEYWORDS = {
    "sabotage": ["sabotage", "arson", "explosion", "explosive", "rail sabotage", "infrastructure sabotage", "subversion"],
    "cyber": ["cyber", "cyberattack", "cyber attack", "ddos", "malware", "ransomware", "phishing", "hack", "hacking", "apt", "wiper", "zero-day", "credential theft"],
    "disinformation": ["disinformation", "misinformation", "propaganda", "fake news", "influence operation", "cognitive war", "cognitive warfare", "information warfare", "bot network"],
    "border_pressure": ["border pressure", "border crossing", "border incident", "border provocation", "border crisis", "illegal crossing", "belarus border", "pushback"],
    "gps_interference": ["gps", "gnss", "jamming", "spoofing", "navigation interference", "satellite navigation", "signal interference"],
    "drone_incident": ["drone", "uav", "unmanned aerial", "shahed", "airspace violation", "airspace incursion", "drone debris"],
    "military_provocation": ["military provocation", "provocation", "fighter jet", "scramble", "intercept", "missile", "warship", "frigate", "submarine", "military exercise", "air policing"],
    "critical_infrastructure": ["critical infrastructure", "power grid", "energy grid", "pipeline", "lng", "substation", "railway", "port", "harbour", "airport", "telecom", "undersea cable", "subsea cable", "cable damage"],
    "espionage": ["spy", "spying", "espionage", "intelligence service", "agent", "fsb", "gru", "svr", "counterintelligence"],
    "migration_pressure": ["migration", "migrant", "migrants", "asylum", "instrumentalised migration", "weaponized migration", "belarus migrants"]
}


ACTOR_KEYWORDS = {
    "Russia": ["russia", "russian", "moscow", "kremlin", "putin", "russian federation"],
    "Belarus": ["belarus", "belarusian", "minsk", "lukashenko"],
    "NATO": ["nato", "allied", "alliance", "eastern flank", "air policing"],
    "EU": ["european union", "eu", "eeas", "enisa", "frontex"],
    "GRU": ["gru", "russian military intelligence"],
    "FSB": ["fsb", "federal security service"],
    "Sandworm": ["sandworm", "electrum"]
}


LOCATION_KEYWORDS = {
    "Kaliningrad": ["kaliningrad", "russian enclave"],
    "Suwalki Gap": ["suwalki gap", "suwałki gap"],
    "Baltic Sea": ["baltic sea", "gulf of finland", "gulf of riga"],
    "Narva": ["narva"],
    "Riga": ["riga"],
    "Tallinn": ["tallinn"],
    "Vilnius": ["vilnius"],
    "Klaipeda": ["klaipeda", "klaipėda"],
    "Gdansk": ["gdansk", "gdańsk"],
    "Belarus Border": ["belarus border", "border with belarus"],
    "Poland-Belarus Border": ["poland-belarus border", "polish-belarusian border"]
}


LOW_QUALITY_DOMAINS = [
    "youtube.com",
    "youtu.be",
    "tiktok.com",
    "facebook.com",
    "reddit.com"
]


FALLBACK_HOMEPAGES = {
    "LRT English Lithuania": "https://www.lrt.lt/en/news-in-english",
    "Polish Radio English": "https://www.polskieradio.pl/395",
    "TVP World": "https://tvpworld.com/",
    "NATO News": "https://www.nato.int/cps/en/natohq/news.htm",
    "ENISA News": "https://www.enisa.europa.eu/news"
}


def load_config() -> Dict[str, Any]:
    if not CONFIG_PATH.exists():
        raise FileNotFoundError(f"Missing config file: {CONFIG_PATH}")
    return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))


def clean_text(value: str) -> str:
    value = re.sub(r"<[^>]+>", " ", value or "")
    value = re.sub(r"&nbsp;", " ", value)
    value = re.sub(r"\s+", " ", value)
    return value.strip()


def normalize_for_matching(value: str) -> str:
    value = value.lower()
    value = re.sub(r"https?://\S+", " ", value)
    value = re.sub(r"[^a-z0-9áéíóöőúüűąćęłńóśźż\- ]+", " ", value)
    value = re.sub(r"\s+", " ", value)
    return value.strip()


def stable_id(*parts: str) -> str:
    raw = "|".join(parts)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def canonical_title(title: str) -> str:
    title = title.lower()
    title = re.sub(r"\s*-\s*[^-]{2,80}$", "", title)
    title = re.sub(r"[^a-z0-9áéíóöőúüűąćęłńóśźż ]+", " ", title)
    title = re.sub(r"\s+", " ", title)
    return title.strip()


def parse_date(entry: Any) -> str:
    for key in ["published", "updated", "created"]:
        if getattr(entry, key, None):
            try:
                dt = date_parser.parse(getattr(entry, key))
                if not dt.tzinfo:
                    dt = dt.replace(tzinfo=timezone.utc)
                return dt.astimezone(timezone.utc).isoformat()
            except Exception:
                pass

    return datetime.now(timezone.utc).isoformat()


def get_domain(url: str) -> str:
    try:
        parsed = urlparse(url)
        return parsed.netloc.replace("www.", "")
    except Exception:
        return ""


def is_low_quality_url(url: str) -> bool:
    domain = get_domain(url)
    return any(blocked in domain for blocked in LOW_QUALITY_DOMAINS)


def detect_from_keywords(text: str, mapping: Dict[str, List[str]]) -> List[str]:
    low = normalize_for_matching(text)
    found = []

    for label, keywords in mapping.items():
        if any(keyword.lower() in low for keyword in keywords):
            found.append(label)

    return found


def detect_countries(text: str, source_country: Optional[str] = None) -> List[str]:
    found = detect_from_keywords(text, COUNTRY_KEYWORDS)

    if source_country and source_country not in found:
        found.append(source_country)

    return found


def detect_categories(text: str) -> List[str]:
    return detect_from_keywords(text, CATEGORY_KEYWORDS)


def detect_actors(text: str) -> List[str]:
    return detect_from_keywords(text, ACTOR_KEYWORDS)


def detect_locations(text: str) -> List[str]:
    return detect_from_keywords(text, LOCATION_KEYWORDS)


def rough_relevance_score(
    text: str,
    source_weight: float,
    countries: List[str],
    categories: List[str],
    actors: List[str],
    locations: List[str]
) -> float:
    low = normalize_for_matching(text)

    base = 0.0

    strong_terms = [
        "hybrid", "sabotage", "cyber", "cyberattack", "gps", "gnss",
        "jamming", "spoofing", "border", "drone", "uav", "provocation",
        "espionage", "critical infrastructure", "airspace", "kaliningrad",
        "belarus", "nato", "russia", "russian", "kremlin", "baltic",
        "poland", "estonia", "latvia", "lithuania"
    ]

    for term in strong_terms:
        if term in low:
            base += 1.0

    base += len(countries) * 1.0
    base += len(categories) * 1.8
    base += len(actors) * 0.8
    base += len(locations) * 0.8

    if "Russia" in actors or "Belarus" in actors:
        base += 1.0

    return round(base * source_weight, 2)


def should_keep_item(
    title: str,
    summary: str,
    countries: List[str],
    categories: List[str],
    actors: List[str],
    score: float,
    url: str
) -> bool:
    text = normalize_for_matching(f"{title} {summary}")

    irrelevant_terms = [
        "sports", "football", "basketball", "celebrity", "movie",
        "music festival", "tourism guide", "recipe", "fashion"
    ]

    if any(term in text for term in irrelevant_terms):
        return False

    if is_low_quality_url(url):
        return False

    if countries or categories or actors:
        return True

    if score >= 3:
        return True

    return False


def build_item(
    title: str,
    summary: str,
    url: str,
    published_at: str,
    source: Dict[str, Any]
) -> Optional[Dict[str, Any]]:
    source_weight = float(source.get("weight", 1.0))
    source_country = source.get("country")

    combined = f"{title} {summary}"

    countries = detect_countries(combined, source_country=source_country)
    categories = detect_categories(combined)
    actors = detect_actors(combined)
    locations = detect_locations(combined)

    relevance = rough_relevance_score(
        text=combined,
        source_weight=source_weight,
        countries=countries,
        categories=categories,
        actors=actors,
        locations=locations
    )

    if not should_keep_item(
        title=title,
        summary=summary,
        countries=countries,
        categories=categories,
        actors=actors,
        score=relevance,
        url=url
    ):
        return None

    item_id = stable_id(
        canonical_title(title),
        published_at[:10],
        source.get("name", "")
    )

    return {
        "id": item_id,
        "title": title,
        "summary": summary,
        "url": url,
        "domain": get_domain(url),
        "published_at": published_at,
        "source_name": source.get("name", "Unknown source"),
        "source_type": source.get("type", "rss"),
        "source_group": source.get("source_group", "unknown"),
        "source_weight": source_weight,
        "countries": countries,
        "categories": categories,
        "actors": actors,
        "locations": locations,
        "relevance_score": relevance,
        "collected_at": datetime.now(timezone.utc).isoformat()
    }


def fetch_rss_source(source: Dict[str, Any]) -> List[Dict[str, Any]]:
    parsed = feedparser.parse(source["url"])

    if len(parsed.entries) == 0 and source.get("name") in FALLBACK_HOMEPAGES:
        return fetch_html_fallback_source(source)

    items = []

    for entry in parsed.entries[:50]:
        title = clean_text(getattr(entry, "title", ""))
        summary = clean_text(getattr(entry, "summary", ""))
        link = getattr(entry, "link", "")
        published_at = parse_date(entry)

        item = build_item(
            title=title,
            summary=summary,
            url=link,
            published_at=published_at,
            source=source
        )

        if item:
            items.append(item)

    return items


def fetch_html_fallback_source(source: Dict[str, Any]) -> List[Dict[str, Any]]:
    homepage = FALLBACK_HOMEPAGES.get(source.get("name"))

    if not homepage:
        return []

    try:
        response = requests.get(
            homepage,
            timeout=25,
            headers={
                "User-Agent": "Mozilla/5.0 BalticHybridMonitor/1.0"
            }
        )
        response.raise_for_status()
    except Exception:
        return []

    soup = BeautifulSoup(response.text, "html.parser")
    candidates = []

    for link in soup.find_all("a", href=True):
        title = clean_text(link.get_text(" ", strip=True))
        href = link.get("href", "")

        if not title or len(title) < 20:
            continue

        absolute_url = urljoin(homepage, href)

        if absolute_url in [item.get("url") for item in candidates]:
            continue

        candidates.append({
            "title": title,
            "url": absolute_url
        })

        if len(candidates) >= 40:
            break

    items = []

    for candidate in candidates:
        item = build_item(
            title=candidate["title"],
            summary="",
            url=candidate["url"],
            published_at=datetime.now(timezone.utc).isoformat(),
            source=source
        )

        if item:
            item["collection_method"] = "html_fallback"
            items.append(item)

    return items


def fetch_external_json_feed(feed: Dict[str, Any]) -> List[Dict[str, Any]]:
    env_var = feed.get("env_var")
    url = os.getenv(env_var, "").strip() if env_var else ""

    if not url:
        return []

    try:
        response = requests.get(url, timeout=25)
        response.raise_for_status()
        data = response.json()
    except Exception as exc:
        return [{
            "id": stable_id(feed["name"], "fetch_error"),
            "title": f"External feed error: {feed['name']}",
            "summary": str(exc),
            "url": url,
            "domain": get_domain(url),
            "published_at": datetime.now(timezone.utc).isoformat(),
            "source_name": feed["name"],
            "source_type": "external_error",
            "source_group": feed.get("source_group", "external_json"),
            "source_weight": float(feed.get("weight", 1.0)),
            "countries": [],
            "categories": [],
            "actors": [],
            "locations": [],
            "relevance_score": 0,
            "collected_at": datetime.now(timezone.utc).isoformat()
        }]

    raw_items = data.get("items", data if isinstance(data, list) else [])
    output = []

    for raw in raw_items[:150]:
        title = clean_text(str(raw.get("title", "")))
        summary = clean_text(str(raw.get("summary", raw.get("description", ""))))
        item_url = raw.get("url", raw.get("link", ""))
        published_at = raw.get(
            "published_at",
            raw.get("date", datetime.now(timezone.utc).isoformat())
        )

        item = build_item(
            title=title,
            summary=summary,
            url=item_url,
            published_at=published_at,
            source=feed
        )

        if item:
            output.append(item)

    return output


def deduplicate(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    grouped: Dict[str, Dict[str, Any]] = {}

    for item in items:
        key = canonical_title(item.get("title", ""))

        if not key:
            key = item.get("id")

        existing = grouped.get(key)

        if not existing:
            grouped[key] = item
            continue

        existing_score = float(existing.get("relevance_score", 0))
        new_score = float(item.get("relevance_score", 0))

        if new_score > existing_score:
            grouped[key] = item

    unique = list(grouped.values())

    return sorted(
        unique,
        key=lambda x: (x.get("published_at", ""), x.get("relevance_score", 0)),
        reverse=True
    )


def build_source_summary(items: List[Dict[str, Any]]) -> Dict[str, Any]:
    summary = {}

    for item in items:
        source_name = item.get("source_name", "Unknown source")

        if source_name not in summary:
            summary[source_name] = {
                "source_name": source_name,
                "source_group": item.get("source_group", "unknown"),
                "source_type": item.get("source_type", "unknown"),
                "item_count": 0
            }

        summary[source_name]["item_count"] += 1

    return dict(
        sorted(
            summary.items(),
            key=lambda pair: pair[1]["item_count"],
            reverse=True
        )
    )


def main() -> None:
    config = load_config()
    all_items = []

    for source in config.get("rss_sources", []):
        all_items.extend(fetch_rss_source(source))

    for feed in config.get("external_json_feeds", []):
        all_items.extend(fetch_external_json_feed(feed))

    unique_items = deduplicate(all_items)

    payload = {
        "project": config.get("project", "baltic-hybrid-monitor"),
        "region": config.get("region", "Baltic states and Poland"),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "item_count": len(unique_items),
        "source_summary": build_source_summary(unique_items),
        "method": {
            "description": "RSS, HTML fallback and optional external JSON collection for Baltic and Poland hybrid threat monitoring.",
            "countries": config.get("countries", []),
            "categories": config.get("threat_categories", []),
            "features": [
                "expanded category keyword detection",
                "actor detection",
                "location detection",
                "improved relevance scoring",
                "canonical title deduplication",
                "relaxed relevance filter",
                "HTML fallback for problematic RSS feeds"
            ]
        },
        "items": unique_items
    }

    RAW_OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    DOCS_OUTPUT.parent.mkdir(parents=True, exist_ok=True)

    RAW_OUTPUT.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )

    DOCS_OUTPUT.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )

    print(f"Saved {len(unique_items)} items to {RAW_OUTPUT}")
    print(f"Saved public copy to {DOCS_OUTPUT}")


if __name__ == "__main__":
    main()
