import json
import re
import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, List, Tuple


ROOT = Path(__file__).resolve().parents[1]

FILTERED_INPUT = ROOT / "data" / "baltic_hybrid_filtered_news.json"
CLUSTERED_OUTPUT = ROOT / "data" / "baltic_hybrid_clustered_events.json"
DOCS_CLUSTERED_OUTPUT = ROOT / "docs" / "data" / "baltic_hybrid_clustered_events.json"


COUNTRIES = ["Estonia", "Latvia", "Lithuania", "Poland"]


STOPWORDS = {
    "the", "a", "an", "and", "or", "to", "of", "in", "on", "for", "with",
    "from", "by", "as", "at", "after", "before", "over", "under", "into",
    "about", "amid", "new", "latest", "update", "updated", "says", "said",
    "warns", "warning", "report", "reports", "article", "news", "breaking",
    "live", "video", "photo", "photos"
}


EVENT_KEYWORDS = [
    "russia", "russian", "belarus", "belarusian", "nato", "eastern", "flank",
    "hybrid", "sabotage", "cyber", "cyberattack", "ddos", "malware",
    "disinformation", "propaganda", "gps", "gnss", "jamming", "spoofing",
    "drone", "uav", "airspace", "fighter", "jets", "scramble", "border",
    "migration", "espionage", "spy", "infrastructure", "pipeline", "cable",
    "kaliningrad", "suwalki", "baltic", "sea", "poland", "latvia",
    "lithuania", "estonia"
}


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
    text = re.sub(r"https?://\S+", " ", text)
    text = re.sub(r"[^a-z0-9áéíóöőúüűąćęłńóśźż\- ]+", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def tokenize(text: str) -> List[str]:
    text = normalize(text)
    tokens = [token for token in text.split() if len(token) >= 4]
    tokens = [token for token in tokens if token not in STOPWORDS]
    return tokens


def stable_id(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]


def title_signature(title: str) -> str:
    tokens = tokenize(title)

    important = [
        token for token in tokens
        if token in EVENT_KEYWORDS or len(token) >= 7
    ]

    if not important:
        important = tokens[:8]

    return " ".join(sorted(set(important))[:12])


def jaccard_similarity(a: List[str], b: List[str]) -> float:
    set_a = set(a)
    set_b = set(b)

    if not set_a or not set_b:
        return 0.0

    return len(set_a & set_b) / len(set_a | set_b)


def same_event(item_a: Dict[str, Any], item_b: Dict[str, Any]) -> bool:
    title_a = item_a.get("title", "")
    title_b = item_b.get("title", "")

    tokens_a = tokenize(title_a)
    tokens_b = tokenize(title_b)

    similarity = jaccard_similarity(tokens_a, tokens_b)

    if similarity >= 0.46:
        return True

    sig_a = title_signature(title_a)
    sig_b = title_signature(title_b)

    if sig_a and sig_a == sig_b:
        return True

    countries_a = set(item_a.get("countries", []))
    countries_b = set(item_b.get("countries", []))
    categories_a = set(item_a.get("categories", []))
    categories_b = set(item_b.get("categories", []))
    actors_a = set(item_a.get("actors", []))
    actors_b = set(item_b.get("actors", []))

    shared_context = (
        bool(countries_a & countries_b)
        and bool(categories_a & categories_b)
        and bool(actors_a & actors_b)
    )

    if shared_context and similarity >= 0.32:
        return True

    return False


def choose_primary_country(country_counts: Dict[str, int]) -> str:
    if not country_counts:
        return "Regional"

    sorted_items = sorted(
        country_counts.items(),
        key=lambda item: item[1],
        reverse=True
    )

    if len(sorted_items) >= 2 and sorted_items[0][1] == sorted_items[1][1]:
        return "Regional"

    return sorted_items[0][0]


def merge_unique(values: List[List[str]]) -> List[str]:
    merged = []

    for value_list in values:
        for value in value_list:
            if value not in merged:
                merged.append(value)

    return merged


def confidence_from_sources(source_count: int, source_groups: List[str]) -> str:
    unique_groups = len(set(source_groups))

    if source_count >= 5 and unique_groups >= 2:
        return "very_high"

    if source_count >= 3:
        return "high"

    if source_count == 2:
        return "medium"

    return "low"


def confidence_score(source_count: int, source_groups: List[str]) -> int:
    unique_groups = len(set(source_groups))

    score = 30
    score += min(source_count, 6) * 8
    score += min(unique_groups, 4) * 5

    return min(score, 100)


def build_cluster_event(cluster: List[Dict[str, Any]]) -> Dict[str, Any]:
    cluster = sorted(
        cluster,
        key=lambda item: (
            item.get("published_at", ""),
            float(item.get("relevance_score", 0))
        ),
        reverse=True
    )

    lead = cluster[0]

    country_counts: Dict[str, int] = {}
    for item in cluster:
        for country in item.get("countries", []):
            country_counts[country] = country_counts.get(country, 0) + 1

    source_names = []
    source_groups = []
    urls = []

    for item in cluster:
        source_name = item.get("source_name", "Unknown source")
        source_group = item.get("source_group", "unknown")
        url = item.get("url", "")

        if source_name not in source_names:
            source_names.append(source_name)

        if source_group not in source_groups:
            source_groups.append(source_group)

        if url and url not in urls:
            urls.append(url)

    countries = merge_unique([item.get("countries", []) for item in cluster])
    categories = merge_unique([item.get("categories", []) for item in cluster])
    actors = merge_unique([item.get("actors", []) for item in cluster])
    locations = merge_unique([item.get("locations", []) for item in cluster])

    avg_relevance = round(
        sum(float(item.get("relevance_score", 0)) for item in cluster) / len(cluster),
        2
    )

    event_key = title_signature(lead.get("title", "")) or lead.get("title", "")

    return {
        "event_id": stable_id(event_key + lead.get("published_at", "")[:10]),
        "title": lead.get("title"),
        "summary": lead.get("summary", ""),
        "url": lead.get("url"),
        "published_at": lead.get("published_at"),
        "primary_country": choose_primary_country(country_counts),
        "countries": countries,
        "categories": categories,
        "actors": actors,
        "locations": locations,
        "source_count": len(source_names),
        "source_names": source_names,
        "source_groups": source_groups,
        "confidence": confidence_from_sources(len(source_names), source_groups),
        "confidence_score": confidence_score(len(source_names), source_groups),
        "relevance_score": avg_relevance,
        "related_item_count": len(cluster),
        "related_urls": urls[:10],
        "related_titles": [item.get("title") for item in cluster[:10]],
        "clustered_at": datetime.now(timezone.utc).isoformat()
    }


def cluster_items(items: List[Dict[str, Any]]) -> List[List[Dict[str, Any]]]:
    clusters: List[List[Dict[str, Any]]] = []

    for item in items:
        placed = False

        for cluster in clusters:
            if same_event(item, cluster[0]):
                cluster.append(item)
                placed = True
                break

        if not placed:
            clusters.append([item])

    return clusters


def build_source_summary(events: List[Dict[str, Any]]) -> Dict[str, Any]:
    summary: Dict[str, Any] = {}

    for event in events:
        for source_name in event.get("source_names", []):
            if source_name not in summary:
                summary[source_name] = {
                    "source_name": source_name,
                    "event_count": 0
                }

            summary[source_name]["event_count"] += 1

    return dict(
        sorted(
            summary.items(),
            key=lambda pair: pair[1]["event_count"],
            reverse=True
        )
    )


def main() -> None:
    filtered = load_json(FILTERED_INPUT)
    items = filtered.get("items", [])

    clusters = cluster_items(items)
    events = [build_cluster_event(cluster) for cluster in clusters]

    events = sorted(
        events,
        key=lambda event: (
            event.get("published_at", ""),
            event.get("confidence_score", 0),
            event.get("relevance_score", 0)
        ),
        reverse=True
    )

    payload = {
        "project": filtered.get("project", "baltic-hybrid-monitor"),
        "region": filtered.get("region", "Baltic states and Poland"),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "input_generated_at": filtered.get("generated_at"),
        "raw_item_count": filtered.get("raw_item_count"),
        "filtered_item_count": filtered.get("item_count"),
        "event_count": len(events),
        "merged_item_count": len(items) - len(events),
        "method": {
            "description": "Event clustering layer for Baltic hybrid threat monitoring.",
            "rules": [
                "merge highly similar titles into one event",
                "merge items with shared country, actor and category context",
                "calculate primary country",
                "calculate source count and confidence score",
                "preserve related source titles and URLs"
            ]
        },
        "source_summary": build_source_summary(events),
        "events": events
    }

    save_json(CLUSTERED_OUTPUT, payload)
    save_json(DOCS_CLUSTERED_OUTPUT, payload)

    print(f"Filtered items: {len(items)}")
    print(f"Clustered events: {len(events)}")
    print(f"Merged items: {len(items) - len(events)}")
    print(f"Saved: {CLUSTERED_OUTPUT}")
    print(f"Saved: {DOCS_CLUSTERED_OUTPUT}")


if __name__ == "__main__":
    main()
