import json
import re
import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, List, Set


ROOT = Path(__file__).resolve().parents[1]

FILTERED_INPUT = ROOT / "data" / "baltic_hybrid_filtered_news.json"
CLUSTERED_OUTPUT = ROOT / "data" / "baltic_hybrid_clustered_events.json"
DOCS_CLUSTERED_OUTPUT = ROOT / "docs" / "data" / "baltic_hybrid_clustered_events.json"


COUNTRY_TERMS = {
    "Estonia": ["estonia", "estonian", "tallinn", "narva", "tartu"],
    "Latvia": ["latvia", "latvian", "riga", "daugavpils", "latgale"],
    "Lithuania": ["lithuania", "lithuanian", "vilnius", "kaunas", "klaipeda", "klaipėda"],
    "Poland": ["poland", "polish", "warsaw", "bialystok", "białystok", "gdansk", "gdańsk", "suwalki", "suwałki"]
}

LOCATION_COUNTRY_HINTS = {
    "Kaliningrad": ["Poland", "Lithuania"],
    "Suwalki Gap": ["Poland", "Lithuania"],
    "Belarus Border": ["Poland", "Lithuania", "Latvia"],
    "Poland-Belarus Border": ["Poland"],
    "Narva": ["Estonia"],
    "Riga": ["Latvia"],
    "Tallinn": ["Estonia"],
    "Vilnius": ["Lithuania"],
    "Klaipeda": ["Lithuania"],
    "Gdansk": ["Poland"],
    "Baltic Sea": ["Estonia", "Latvia", "Lithuania", "Poland"]
}

STOPWORDS = {
    "the", "and", "for", "with", "from", "that", "this", "into", "over",
    "after", "before", "about", "amid", "says", "said", "new", "latest",
    "update", "updated", "report", "reports", "article", "news", "live",
    "will", "have", "has", "are", "was", "were", "its", "their"
}

INCIDENT_TERMS = [
    "drone crash", "drone flies", "drone incident", "drone attack",
    "airspace violation", "airspace incursion", "airspace alert",
    "gps jamming", "gnss jamming", "spoofing", "navigation interference",
    "sabotage", "explosion", "arson", "cable damage", "undersea cable",
    "subsea cable", "pipeline damage", "cyberattack", "cyber attack",
    "ddos", "malware", "ransomware", "wiper", "phishing campaign",
    "espionage", "spy", "spying", "arrested spy", "border crossing",
    "border incident", "border breach", "missile", "attack", "incursion",
    "fighter jets scrambled", "scrambles fighter jets", "scramble fighter",
    "critical infrastructure attack"
]

ACTIVITY_TERMS = [
    "military exercise", "air policing", "patrol", "deployment",
    "troop movement", "readiness", "deterrence", "defence package",
    "defense package", "military aid", "nato summit", "summit",
    "sanctions", "border guard", "border protection", "eastern flank",
    "allied unity", "mobilisation", "mobilization", "preparedness",
    "security package", "joint exercise"
]

INDICATOR_TERMS = [
    "warning", "warns", "threat", "risk", "concern", "alert",
    "assessment", "intelligence warning", "hybrid threat",
    "russia threatens", "kremlin threat", "cyber warning",
    "gps warning", "preparedness warning", "disinformation campaign",
    "propaganda campaign", "influence operation"
]

ASSESSMENT_TERMS = [
    "framework", "strategy", "strategic", "analysis", "report",
    "study", "white paper", "ecosystem", "capabilities", "maturity",
    "training", "awareness", "cyber hygiene", "challenge",
    "investment", "conference", "reserve", "policy", "guidance",
    "implementation", "exercise diy"
]


def load_json(path: Path) -> Dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"Missing input file: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def save_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def normalize(text: str) -> str:
    text = text.lower()
    text = re.sub(r"https?://\S+", " ", text)
    text = re.sub(r"[^a-z0-9áéíóöőúüűąćęłńóśźż\- ]+", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def contains_any(text: str, terms: List[str]) -> bool:
    low = normalize(text)
    return any(term in low for term in terms)


def tokenize(text: str) -> Set[str]:
    return {
        token for token in normalize(text).split()
        if len(token) >= 4 and token not in STOPWORDS
    }


def stable_id(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]


def similarity(a: Set[str], b: Set[str]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def shared_context(item: Dict[str, Any], event: Dict[str, Any]) -> bool:
    item_countries = set(item.get("countries", []))
    event_countries = set(event.get("countries", []))
    item_categories = set(item.get("categories", []))
    event_categories = set(event.get("categories", []))
    item_actors = set(item.get("actors", []))
    event_actors = set(event.get("actors", []))

    if item_actors and event_actors and item_actors & event_actors:
        return True

    if item_categories and event_categories and item_categories & event_categories:
        if item_countries and event_countries and item_countries & event_countries:
            return True

    return False


def should_merge(item: Dict[str, Any], event: Dict[str, Any]) -> bool:
    title_score = similarity(tokenize(item.get("title", "")), tokenize(event.get("title", "")))

    if title_score >= 0.44:
        return True

    if title_score >= 0.30 and shared_context(item, event):
        return True

    return False


def unique_merge(existing: List[str], new_values: List[str]) -> List[str]:
    output = list(existing)
    for value in new_values:
        if value and value not in output:
            output.append(value)
    return output


def country_score_from_text(text: str, weight: int) -> Dict[str, int]:
    scores = {country: 0 for country in COUNTRY_TERMS}
    low = normalize(text)

    for country, terms in COUNTRY_TERMS.items():
        for term in terms:
            if term in low:
                scores[country] += weight

    return scores


def choose_primary_country_v2(event: Dict[str, Any]) -> str:
    scores = {country: 0 for country in COUNTRY_TERMS}

    title = event.get("title", "")
    summary = event.get("summary", "")
    url = event.get("url", "")

    for country, value in country_score_from_text(title, 6).items():
        scores[country] += value

    for country, value in country_score_from_text(summary, 3).items():
        scores[country] += value

    for country, value in country_score_from_text(url, 2).items():
        scores[country] += value

    for item in event.get("related_items", []):
        for country in item.get("countries", []):
            if country in scores:
                scores[country] += 3

    for location in event.get("locations", []):
        for country in LOCATION_COUNTRY_HINTS.get(location, []):
            if country in scores:
                scores[country] += 4

    text = normalize(f"{title} {summary} {url}")

    if "poland-belarus border" in text or "polish-belarusian border" in text:
        scores["Poland"] += 8

    if "suwalki" in text or "suwałki" in text:
        scores["Poland"] += 6
        scores["Lithuania"] += 3

    if "kaliningrad" in text:
        scores["Poland"] += 3
        scores["Lithuania"] += 3

    if "baltic states" in text or "baltics" in text:
        scores["Estonia"] += 1
        scores["Latvia"] += 1
        scores["Lithuania"] += 1

    sorted_scores = sorted(scores.items(), key=lambda pair: pair[1], reverse=True)
    top_country, top_score = sorted_scores[0]

    if top_score <= 0:
        return "Regional"

    if len(sorted_scores) > 1:
        second_score = sorted_scores[1][1]
        if second_score > 0 and top_score - second_score <= 1:
            return "Regional"

    return top_country


def calculate_confidence(source_count: int, source_group_count: int, source_names: List[str]) -> Dict[str, Any]:
    official_sources = [
        "NATO", "ENISA", "EUvsDisinfo", "CERT", "Ministry", "MOD",
        "Border Guard", "Defence", "Defense"
    ]

    score = 25
    score += min(source_count, 6) * 8
    score += min(source_group_count, 4) * 5

    if any(any(key.lower() in source.lower() for key in official_sources) for source in source_names):
        score += 10

    if source_count >= 3 and source_group_count >= 2:
        score += 8

    score = min(score, 100)

    if score >= 80:
        label = "very_high"
    elif score >= 65:
        label = "high"
    elif score >= 50:
        label = "medium"
    else:
        label = "low"

    return {"confidence": label, "confidence_score": score}


def classify_event_subtype(event: Dict[str, Any]) -> str:
    text = " ".join([
        str(event.get("title", "")),
        str(event.get("summary", "")),
        " ".join(event.get("categories", [])),
        " ".join(event.get("actors", [])),
        " ".join(event.get("locations", []))
    ])

    categories = set(event.get("categories", []))
    actors = set(event.get("actors", []))

    if contains_any(text, INCIDENT_TERMS):
        return "incident"

    if categories & {"drone_incident", "gps_interference", "sabotage", "espionage"}:
        if "Russia" in actors or "Belarus" in actors or contains_any(text, INCIDENT_TERMS):
            return "incident"

    if categories & {"cyber"} and (
        contains_any(text, ["cyberattack", "cyber attack", "ddos", "malware", "ransomware", "wiper"])
        or "Sandworm" in actors or "GRU" in actors or "FSB" in actors
    ):
        return "incident"

    if categories & {"border_pressure", "migration_pressure"} and (
        "Belarus" in actors or contains_any(text, ["border crossing", "border incident", "migrant pressure"])
    ):
        return "incident"

    if contains_any(text, ACTIVITY_TERMS):
        return "activity"

    if "NATO" in actors and ("Russia" in actors or "Belarus" in actors):
        return "activity"

    if contains_any(text, INDICATOR_TERMS):
        return "indicator"

    if categories & {"disinformation"}:
        return "indicator"

    if contains_any(text, ASSESSMENT_TERMS):
        return "assessment"

    if "EU" in actors and categories:
        return "assessment"

    if categories:
        return "indicator"

    return "assessment"


def classify_event_type(event_subtype: str) -> str:
    if event_subtype in {"incident", "activity", "indicator"}:
        return "operational"
    return "background"


def create_event_from_item(item: Dict[str, Any]) -> Dict[str, Any]:
    source_name = item.get("source_name", "Unknown source")
    source_group = item.get("source_group", "unknown")
    event_seed = normalize(item.get("title", "")) + item.get("published_at", "")[:10]
    confidence = calculate_confidence(1, 1, [source_name])

    event = {
        "event_id": stable_id(event_seed),
        "title": item.get("title", ""),
        "summary": item.get("summary", ""),
        "url": item.get("url", ""),
        "published_at": item.get("published_at"),
        "countries": item.get("countries", []),
        "categories": item.get("categories", []),
        "actors": item.get("actors", []),
        "locations": item.get("locations", []),
        "relevance_score": float(item.get("relevance_score", 0)),
        "source_count": 1,
        "source_names": [source_name],
        "source_groups": [source_group],
        "related_item_count": 1,
        "related_titles": [item.get("title", "")],
        "related_urls": [item.get("url", "")],
        "related_items": [item],
        "confidence": confidence["confidence"],
        "confidence_score": confidence["confidence_score"],
        "collection_methods": [item.get("collection_method", "rss")]
    }

    event["primary_country"] = choose_primary_country_v2(event)
    event["event_subtype"] = classify_event_subtype(event)
    event["event_type"] = classify_event_type(event["event_subtype"])
    return event


def merge_item_into_event(item: Dict[str, Any], event: Dict[str, Any]) -> None:
    event["related_items"].append(item)
    event["related_item_count"] = len(event["related_items"])

    event["countries"] = unique_merge(event.get("countries", []), item.get("countries", []))
    event["categories"] = unique_merge(event.get("categories", []), item.get("categories", []))
    event["actors"] = unique_merge(event.get("actors", []), item.get("actors", []))
    event["locations"] = unique_merge(event.get("locations", []), item.get("locations", []))

    source_name = item.get("source_name", "Unknown source")
    source_group = item.get("source_group", "unknown")
    method = item.get("collection_method", "rss")

    event["source_names"] = unique_merge(event.get("source_names", []), [source_name])
    event["source_groups"] = unique_merge(event.get("source_groups", []), [source_group])
    event["collection_methods"] = unique_merge(event.get("collection_methods", []), [method])
    event["related_titles"] = unique_merge(event.get("related_titles", []), [item.get("title", "")])
    event["related_urls"] = unique_merge(event.get("related_urls", []), [item.get("url", "")])

    event["source_count"] = len(event.get("source_names", []))
    event["relevance_score"] = round(
        sum(float(i.get("relevance_score", 0)) for i in event["related_items"]) /
        len(event["related_items"]),
        2
    )

    confidence = calculate_confidence(
        event["source_count"],
        len(event.get("source_groups", [])),
        event.get("source_names", [])
    )

    event["confidence"] = confidence["confidence"]
    event["confidence_score"] = confidence["confidence_score"]
    event["primary_country"] = choose_primary_country_v2(event)
    event["event_subtype"] = classify_event_subtype(event)
    event["event_type"] = classify_event_type(event["event_subtype"])


def cluster_items(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    events: List[Dict[str, Any]] = []
    sorted_items = sorted(
        items,
        key=lambda item: (item.get("published_at", ""), float(item.get("relevance_score", 0))),
        reverse=True
    )

    for item in sorted_items:
        matched_event = None

        for event in events:
            if should_merge(item, event):
                matched_event = event
                break

        if matched_event:
            merge_item_into_event(item, matched_event)
        else:
            events.append(create_event_from_item(item))

    return events


def clean_event_for_output(event: Dict[str, Any]) -> Dict[str, Any]:
    output = dict(event)
    output.pop("related_items", None)
    output["related_titles"] = output.get("related_titles", [])[:10]
    output["related_urls"] = output.get("related_urls", [])[:10]
    return output


def build_summary(events: List[Dict[str, Any]]) -> Dict[str, Any]:
    by_country: Dict[str, int] = {}
    by_category: Dict[str, int] = {}
    by_actor: Dict[str, int] = {}
    by_event_type: Dict[str, int] = {"operational": 0, "background": 0}
    by_event_subtype: Dict[str, int] = {
        "incident": 0,
        "activity": 0,
        "indicator": 0,
        "assessment": 0
    }

    for event in events:
        event_type = event.get("event_type", "background")
        event_subtype = event.get("event_subtype", "assessment")

        by_event_type[event_type] = by_event_type.get(event_type, 0) + 1
        by_event_subtype[event_subtype] = by_event_subtype.get(event_subtype, 0) + 1

        primary = event.get("primary_country", "Regional")
        by_country[primary] = by_country.get(primary, 0) + 1

        for category in event.get("categories", []):
            by_category[category] = by_category.get(category, 0) + 1

        for actor in event.get("actors", []):
            by_actor[actor] = by_actor.get(actor, 0) + 1

    return {
        "by_event_type": by_event_type,
        "by_event_subtype": by_event_subtype,
        "by_primary_country": dict(sorted(by_country.items())),
        "by_category": dict(sorted(by_category.items())),
        "by_actor": dict(sorted(by_actor.items()))
    }


def main() -> None:
    filtered = load_json(FILTERED_INPUT)
    items = filtered.get("items", [])

    events = cluster_items(items)
    output_events = [clean_event_for_output(event) for event in events]

    payload = {
        "project": filtered.get("project", "baltic-hybrid-monitor"),
        "region": filtered.get("region", "Baltic states and Poland"),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "input_generated_at": filtered.get("generated_at"),
        "raw_item_count": filtered.get("raw_item_count"),
        "filtered_item_count": filtered.get("item_count"),
        "event_count": len(output_events),
        "merged_item_count": len(items) - len(output_events),
        "summary": build_summary(output_events),
        "method": {
            "description": "Threat Intelligence Engine v1.0 event clustering with ontology subtype classification.",
            "rules": [
                "merge items with high title similarity",
                "merge moderately similar items when actor/category/country context overlaps",
                "calculate primary country using weighted title, summary, URL, location and related item signals",
                "calculate confidence score using source count, source diversity and official-source bonus",
                "classify event_type as operational or background",
                "classify event_subtype as incident, activity, indicator or assessment",
                "preserve related titles and URLs"
            ],
            "threat_ontology": {
                "incident": "confirmed or reported operational incident",
                "activity": "military, political or security activity that shapes risk",
                "indicator": "early warning or information signal",
                "assessment": "strategic, institutional or analytical background"
            }
        },
        "events": output_events
    }

    save_json(CLUSTERED_OUTPUT, payload)
    save_json(DOCS_CLUSTERED_OUTPUT, payload)

    print(f"Filtered items: {len(items)}")
    print(f"Clustered events: {len(output_events)}")
    print(f"Merged items: {len(items) - len(output_events)}")
    print(f"Saved: {CLUSTERED_OUTPUT}")
    print(f"Saved: {DOCS_CLUSTERED_OUTPUT}")


if __name__ == "__main__":
    main()
