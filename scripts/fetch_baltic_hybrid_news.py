import json
import os
import re
import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Any

import feedparser
import requests
from dateutil import parser as date_parser


ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "config" / "baltic_sources.json"
RAW_OUTPUT = ROOT / "data" / "baltic_hybrid_raw_news.json"
DOCS_OUTPUT = ROOT / "docs" / "data" / "baltic_hybrid_raw_news.json"


COUNTRY_KEYWORDS = {
    "Estonia": ["estonia", "estonian", "tallinn", "narva"],
    "Latvia": ["latvia", "latvian", "riga", "daugavpils"],
    "Lithuania": ["lithuania", "lithuanian", "vilnius", "kaunas", "klaipeda"],
    "Poland": ["poland", "polish", "warsaw", "bialystok", "suwalki", "kaliningrad", "belarus border"]
}

CATEGORY_KEYWORDS = {
    "sabotage": ["sabotage", "arson", "explosion", "railway", "attack on infrastructure"],
    "cyber": ["cyber", "ddos", "hack", "malware", "ransomware", "cyberattack"],
    "disinformation": ["disinformation", "propaganda", "influence operation", "fake news"],
    "border_pressure": ["border", "border crossing", "border pressure", "incursion"],
    "gps_interference": ["gps", "jamming", "navigation interference", "gnss"],
    "drone_incident": ["drone", "uav", "airspace violation"],
    "military_provocation": ["provocation", "military exercise", "troop movement", "missile", "airspace"],
    "critical_infrastructure": ["critical infrastructure", "energy", "pipeline", "rail", "port", "airport", "power grid"],
    "espionage": ["spy", "espionage", "intelligence service", "agent"],
    "migration_pressure": ["migration", "migrant", "asylum", "belarus border"]
}


def load_config() -> Dict[str, Any]:
    if not CONFIG_PATH.exists():
        raise FileNotFoundError(f"Missing config file: {CONFIG_PATH}")
    return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))


def clean_text(value: str) -> str:
    value = re.sub(r"<[^>]+>", " ", value or "")
    value = re.sub(r"\s+", " ", value)
    return value.strip()


def stable_id(*parts: str) -> str:
    raw = "|".join(parts)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


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


def detect_countries(text: str) -> List[str]:
    low = text.lower()
    found = []
    for country, keywords in COUNTRY_KEYWORDS.items():
        if any(k in low for k in keywords):
            found.append(country)
    return found


def detect_categories(text: str) -> List[str]:
    low = text.lower()
    found = []
    for category, keywords in CATEGORY_KEYWORDS.items():
        if any(k in low for k in keywords):
            found.append(category)
    return found


def rough_relevance_score(text: str, source_weight: float) -> float:
    low = text.lower()
    base = 0.0

    strong_terms = [
        "russia", "russian", "kremlin", "belarus", "kaliningrad",
        "hybrid", "sabotage", "cyber", "gps", "jamming",
        "border", "drone", "provocation", "espionage"
    ]

    for term in strong_terms:
        if term in low:
            base += 1.0

    categories = detect_categories(text)
    countries = detect_countries(text)

    base += len(categories) * 1.5
    base += len(countries) * 1.0

    return round(base * source_weight, 2)


def fetch_rss_source(source: Dict[str, Any]) -> List[Dict[str, Any]]:
    url = source["url"]
    parsed = feedparser.parse(url)
    items = []

    for entry in parsed.entries[:50]:
        title = clean_text(getattr(entry, "title", ""))
        summary = clean_text(getattr(entry, "summary", ""))
        link = getattr(entry, "link", "")
        published_at = parse_date(entry)

        combined = f"{title} {summary}"
        countries = detect_countries(combined)
        categories = detect_categories(combined)
        score = rough_relevance_score(combined, float(source.get("weight", 1.0)))

        if not countries and score < 3:
            continue

        items.append({
            "id": stable_id(title, link),
            "title": title,
            "summary": summary,
            "url": link,
            "published_at": published_at,
            "source_name": source["name"],
            "source_type": source.get("type", "rss"),
            "countries": countries,
            "categories": categories,
            "relevance_score": score,
            "collected_at": datetime.now(timezone.utc).isoformat()
        })

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
            "published_at": datetime.now(timezone.utc).isoformat(),
            "source_name": feed["name"],
            "source_type": "external_error",
            "countries": [],
            "categories": [],
            "relevance_score": 0,
            "collected_at": datetime.now(timezone.utc).isoformat()
        }]

    raw_items = data.get("items", data if isinstance(data, list) else [])
    output = []

    for item in raw_items[:100]:
        title = clean_text(str(item.get("title", "")))
        summary = clean_text(str(item.get("summary", item.get("description", ""))))
        url_value = item.get("url", item.get("link", ""))
        published_at = item.get("published_at", item.get("date", datetime.now(timezone.utc).isoformat()))

        combined = f"{title} {summary}"
        countries = detect_countries(combined)
        categories = detect_categories(combined)

        output.append({
            "id": stable_id(title, url_value),
            "title": title,
            "summary": summary,
            "url": url_value,
            "published_at": published_at,
            "source_name": feed["name"],
            "source_type": feed.get("type", "external_json"),
            "countries": countries,
            "categories": categories,
            "relevance_score": rough_relevance_score(combined, float(feed.get("weight", 1.0))),
            "collected_at": datetime.now(timezone.utc).isoformat()
        })

    return output


def deduplicate(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    seen = set()
    unique = []

    for item in sorted(items, key=lambda x: x.get("relevance_score", 0), reverse=True):
        key = item.get("id")
        if key in seen:
            continue
        seen.add(key)
        unique.append(item)

    return unique


def main() -> None:
    config = load_config()
    all_items = []

    for source in config.get("rss_sources", []):
        all_items.extend(fetch_rss_source(source))

    for feed in config.get("external_json_feeds", []):
        all_items.extend(fetch_external_json_feed(feed))

    unique_items = deduplicate(all_items)

    payload = {
        "project": config.get("project"),
        "region": config.get("region"),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "item_count": len(unique_items),
        "method": {
            "description": "RSS and optional external JSON collection for Baltic and Poland hybrid threat monitoring.",
            "countries": config.get("countries", []),
            "categories": config.get("threat_categories", [])
        },
        "items": unique_items
    }

    RAW_OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    DOCS_OUTPUT.parent.mkdir(parents=True, exist_ok=True)

    RAW_OUTPUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    DOCS_OUTPUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"Saved {len(unique_items)} items to {RAW_OUTPUT}")
    print(f"Saved public copy to {DOCS_OUTPUT}")


if __name__ == "__main__":
    main()
