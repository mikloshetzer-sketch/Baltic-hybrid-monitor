import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, List


ROOT = Path(__file__).resolve().parents[1]

RAW_INPUT = ROOT / "data" / "baltic_hybrid_raw_news.json"
FILTERED_OUTPUT = ROOT / "data" / "baltic_hybrid_filtered_news.json"
DOCS_FILTERED_OUTPUT = ROOT / "docs" / "data" / "baltic_hybrid_filtered_news.json"


STRONG_KEEP_TERMS = [
    "russia", "russian", "kremlin", "moscow", "putin",
    "belarus", "belarusian", "lukashenko",
    "nato", "eastern flank", "allied", "air policing",
    "hybrid", "sabotage", "espionage", "spy", "intelligence",
    "cyber", "cyberattack", "ddos", "malware", "ransomware",
    "disinformation", "propaganda", "influence operation",
    "gps", "gnss", "jamming", "spoofing",
    "drone", "uav", "airspace", "fighter jet", "scramble",
    "border", "migration pressure", "migrant pressure",
    "critical infrastructure", "undersea cable", "subsea cable",
    "pipeline", "power grid", "energy infrastructure",
    "kaliningrad", "suwalki", "baltic sea"
]

NOISE_TERMS = [
    "culture", "concert", "music", "chopin", "violin", "orchestra",
    "sports", "football", "basketball", "mountaineering",
    "weather", "heavy rain", "water leak", "hospital",
    "seat selection", "airbaltic seats", "six-year-old",
    "human trafficking", "labour exploitation",
    "election candidate pool", "news in simple latvian",
    "population research", "bar open again", "tourism",
    "recipe", "fashion", "festival", "parade"
]

WEAK_CATEGORY_BLOCKLIST = [
    "critical_infrastructure"
]


def load_json(path: Path) -> Dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"Missing input file: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def save_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )


def normalize(text: str) -> str:
    text = text.lower()
    text = re.sub(r"[^a-z0-9áéíóöőúüűąćęłńóśźż\- /]+", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def contains_any(text: str, terms: List[str]) -> bool:
    low = normalize(text)
    return any(term in low for term in terms)


def has_strong_signal(item: Dict[str, Any]) -> bool:
    text = " ".join([
        str(item.get("title", "")),
        str(item.get("summary", "")),
        str(item.get("url", ""))
    ])

    actors = item.get("actors", [])
    categories = item.get("categories", [])
    locations = item.get("locations", [])

    if contains_any(text, STRONG_KEEP_TERMS):
        return True

    if actors:
        return True

    if locations:
        return True

    strong_categories = [
        category for category in categories
        if category not in WEAK_CATEGORY_BLOCKLIST
    ]

    if strong_categories:
        return True

    return False


def is_noise(item: Dict[str, Any]) -> bool:
    text = " ".join([
        str(item.get("title", "")),
        str(item.get("summary", "")),
        str(item.get("url", ""))
    ])

    categories = item.get("categories", [])
    actors = item.get("actors", [])

    if contains_any(text, NOISE_TERMS) and not actors:
        return True

    if categories == ["critical_infrastructure"] and not actors:
        if not contains_any(text, STRONG_KEEP_TERMS):
            return True

    return False


def filter_items(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    kept = []

    for item in items:
        if is_noise(item):
            continue

        if not has_strong_signal(item):
            continue

        kept.append(item)

    return kept


def build_source_summary(items: List[Dict[str, Any]]) -> Dict[str, Any]:
    summary = {}

    for item in items:
        name = item.get("source_name", "Unknown source")

        if name not in summary:
            summary[name] = {
                "source_name": name,
                "source_group": item.get("source_group", "unknown"),
                "source_type": item.get("source_type", "unknown"),
                "item_count": 0,
                "rss_count": 0,
                "html_fallback_count": 0,
                "external_json_count": 0
            }

        summary[name]["item_count"] += 1

        method = item.get("collection_method", "rss")

        if method == "html_fallback":
            summary[name]["html_fallback_count"] += 1
        elif method == "external_json":
            summary[name]["external_json_count"] += 1
        else:
            summary[name]["rss_count"] += 1

    return dict(
        sorted(
            summary.items(),
            key=lambda pair: pair[1]["item_count"],
            reverse=True
        )
    )


def main() -> None:
    raw = load_json(RAW_INPUT)
    raw_items = raw.get("items", [])

    filtered_items = filter_items(raw_items)

    payload = {
        "project": raw.get("project", "baltic-hybrid-monitor"),
        "region": raw.get("region", "Baltic states and Poland"),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "input_generated_at": raw.get("generated_at"),
        "raw_item_count": len(raw_items),
        "item_count": len(filtered_items),
        "removed_count": len(raw_items) - len(filtered_items),
        "source_summary": build_source_summary(filtered_items),
        "method": {
            "description": "Threat relevance filter for Baltic hybrid threat monitoring.",
            "rules": [
                "remove cultural, sport, lifestyle and general domestic noise",
                "remove weak infrastructure false positives without actor or security signal",
                "keep items linked to Russia, Belarus, NATO or hybrid threat categories",
                "keep items with strategic locations, actors or strong threat terms"
            ]
        },
        "items": filtered_items
    }

    save_json(FILTERED_OUTPUT, payload)
    save_json(DOCS_FILTERED_OUTPUT, payload)

    print(f"Raw items: {len(raw_items)}")
    print(f"Filtered items: {len(filtered_items)}")
    print(f"Removed items: {len(raw_items) - len(filtered_items)}")
    print(f"Saved: {FILTERED_OUTPUT}")
    print(f"Saved: {DOCS_FILTERED_OUTPUT}")


if __name__ == "__main__":
    main()
