import json
import os
import re
import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Any
from urllib.parse import urlparse

import feedparser
import requests
from dateutil import parser as date_parser


ROOT = Path(__file__).resolve().parents[1]

CONFIG_PATH = ROOT / "config" / "baltic_sources.json"
RAW_OUTPUT = ROOT / "data" / "baltic_hybrid_raw_news.json"
DOCS_OUTPUT = ROOT / "docs" / "data" / "baltic_hybrid_raw_news.json"


COUNTRY_KEYWORDS = {
    "Estonia": [
        "estonia", "estonian", "tallinn", "narva", "tartu",
        "ida-viru", "ida-virumaa", "estonian defence forces"
    ],
    "Latvia": [
        "latvia", "latvian", "riga", "daugavpils", "latgale",
        "latvian national armed forces"
    ],
    "Lithuania": [
        "lithuania", "lithuanian", "vilnius", "kaunas", "klaipeda",
        "klaipėda", "suwalki", "suwałki"
    ],
    "Poland": [
        "poland", "polish", "warsaw", "bialystok", "białystok",
        "suwalki", "suwałki", "gdańsk", "gdansk",
        "polish border guard", "polish armed forces"
    ]
}


CATEGORY_KEYWORDS = {
    "sabotage": [
        "sabotage", "arson", "explosion", "explosive", "rail sabotage",
        "railway sabotage", "infrastructure sabotage", "vandalism",
        "attack on infrastructure", "covert operation", "subversion"
    ],
    "cyber": [
        "cyber", "cyberattack", "cyber attack", "ddos", "malware",
        "ransomware", "phishing", "hack", "hacking", "apt",
        "wiper", "zero-day", "credential theft", "sandworm",
        "electrum", "ics", "industrial control", "power grid cyber"
    ],
    "disinformation": [
        "disinformation", "misinformation", "propaganda", "fake news",
        "influence operation", "influence campaign", "cognitive war",
        "cognitive warfare", "information warfare", "bot network",
        "social media manipulation", "narrative", "kremlin narrative"
    ],
    "border_pressure": [
        "border pressure", "border crossing", "border incident",
        "border provocation", "border crisis", "illegal crossing",
        "belarus border", "frontier", "pushback"
    ],
    "gps_interference": [
        "gps", "gnss", "jamming", "spoofing", "navigation interference",
        "satellite navigation", "signal interference", "kaliningrad jamming",
        "aviation disruption"
    ],
    "drone_incident": [
        "drone", "uav", "unmanned aerial", "shahed", "loitering munition",
        "airspace violation", "airspace incursion", "drone debris"
    ],
    "military_provocation": [
        "military provocation", "provocation", "fighter jet", "fighter",
        "scramble", "intercept", "missile", "missile launch",
        "warship", "frigate", "submarine", "strategic bomber",
        "military exercise", "troop movement", "zapad", "air policing",
        "nato air policing"
    ],
    "critical_infrastructure": [
        "critical infrastructure", "power grid", "energy grid", "electricity",
        "pipeline", "lng", "substation", "transformer", "railway",
        "rail", "port", "harbour", "airport", "telecom", "undersea cable",
        "subsea cable", "cable damage", "balticconnector", "data cable"
    ],
    "espionage": [
        "spy", "spying", "espionage", "intelligence service", "agent",
        "fsb", "gru", "svr", "recruited", "foreign intelligence",
        "counterintelligence", "arrested spy"
    ],
    "migration_pressure": [
        "migration", "migrant", "migrants", "asylum", "instrumentalised migration",
        "weaponized migration", "belarus migrants", "border migrants"
    ]
}


ACTOR_KEYWORDS = {
    "Russia": [
        "russia", "russian", "moscow", "kremlin", "putin",
        "russian federation"
    ],
    "Belarus": [
        "belarus", "belarusian", "minsk", "lukashenko"
    ],
    "NATO": [
        "nato", "allied", "alliance", "eastern flank", "air policing"
    ],
    "EU": [
        "european union", "eu", "eeas", "enisa", "frontex"
    ],
    "GRU": [
        "gru", "russian military intelligence"
    ],
    "FSB": [
        "fsb", "russian domestic spy agency", "federal security service"
    ],
    "Sandworm": [
        "sandworm", "electrum"
    ]
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
    title = re.sub(r"\s*-\s*[^-]{2,60}$", "", title)
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


def detect_countries(text: str, source_country: str = None) -> List[str]:
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
        "belarus", "nato", "russia", "russian", "kremlin"
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

    if is_low_quality_url(url):
        return False

    if not countries and not categories:
        return False

    if "Russia" not in actors and "Belarus" not in actors and "NATO" not in actors:
        if score < 5:
            return False

    if score < 3:
        return False

    irrelevant_terms = [
        "sports", "football", "basketball", "celebrity", "movie",
        "music festival", "tourism guide"
    ]

    if any(term in text for term in irrelevant_terms):
        return False

    return True


def build_item(
    title: str,
    summary: str,
    url: str,
    published_at: str,
    source: Dict[str, Any]
) -> Dict[str, Any] | None:
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

    return {
        "id": stable_id(canonical_title(title), published_at[:10]),
        "title": title,
        "summary": summary,
        "url": url,
        "domain": get_domain(url),
        "published_at": published_at,
        "source_name": source.get("name", "Unknown source"),
        "source_type": source.get("type", "rss"),
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
        "method": {
            "description": "RSS and optional external JSON collection for Baltic and Poland hybrid threat monitoring.",
            "countries": config.get("countries", []),
            "categories": config.get("threat_categories", []),
            "features": [
                "expanded category keyword detection",
                "actor detection",
                "location detection",
                "improved relevance scoring",
                "canonical title deduplication"
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
