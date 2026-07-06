import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, List


ROOT = Path(__file__).resolve().parents[1]

SCORED_INPUT = ROOT / "data" / "baltic_hybrid_scored_news.json"
HISTORY_INPUT = ROOT / "data" / "baltic_hybrid_history.json"
DASHBOARD_OUTPUT = ROOT / "docs" / "data" / "baltic_dashboard.json"


TOP_EVENT_LIMIT = 30
TOP_DRIVER_LIMIT = 10
HISTORY_LIMIT = 30


def load_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default

    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return default


def save_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )


def safe_round(value: Any, digits: int = 2) -> float:
    try:
        return round(float(value), digits)
    except (TypeError, ValueError):
        return 0.0


def level_from_score(score: float) -> str:
    if score >= 80:
        return "critical"
    if score >= 60:
        return "high"
    if score >= 40:
        return "elevated"
    if score >= 20:
        return "guarded"
    return "low"


def normalize_summary(scored: Dict[str, Any]) -> Dict[str, Any]:
    overall = scored.get("overall_summary", {})

    threat_index = safe_round(overall.get("threat_index", overall.get("average_score", 0)))

    return {
        "threat_index": threat_index,
        "threat_level": overall.get("overall_level", level_from_score(threat_index)),
        "event_count": int(overall.get("event_count", 0)),
        "incident_count": int(overall.get("incident_count", 0)),
        "activity_count": int(overall.get("activity_count", 0)),
        "indicator_count": int(overall.get("indicator_count", 0)),
        "assessment_count": int(overall.get("assessment_count", 0)),
        "score_total": int(overall.get("score_total", 0)),
        "average_score": safe_round(overall.get("average_score", 0)),
        "highest_score": int(overall.get("highest_score", 0)),
        "raw_item_count": int(scored.get("raw_item_count", 0) or 0),
        "filtered_item_count": int(scored.get("filtered_item_count", 0) or 0),
        "clustered_event_count": int(scored.get("clustered_event_count", 0) or 0),
        "merged_item_count": int(scored.get("merged_item_count", 0) or 0)
    }


def build_country_cards(scored: Dict[str, Any]) -> List[Dict[str, Any]]:
    country_summary = scored.get("country_summary", {})
    cards = []

    for country, data in country_summary.items():
        cards.append({
            "country": country,
            "event_count": int(data.get("event_count", 0)),
            "incident_count": int(data.get("incident_count", 0)),
            "activity_count": int(data.get("activity_count", 0)),
            "indicator_count": int(data.get("indicator_count", 0)),
            "assessment_count": int(data.get("assessment_count", 0)),
            "score_total": int(data.get("score_total", 0)),
            "average_score": safe_round(data.get("average_score", 0)),
            "highest_score": int(data.get("highest_score", 0)),
            "level": data.get("level", "low"),
            "top_categories": top_items_from_mapping(data.get("categories", {}), 5),
            "top_actors": top_items_from_mapping(data.get("actors", {}), 5)
        })

    return sorted(cards, key=lambda item: item["score_total"], reverse=True)


def top_items_from_mapping(mapping: Dict[str, Any], limit: int) -> List[Dict[str, Any]]:
    items = []

    for key, value in mapping.items():
        try:
            count = int(value)
        except (TypeError, ValueError):
            count = 0

        items.append({
            "name": key,
            "count": count
        })

    return sorted(items, key=lambda item: item["count"], reverse=True)[:limit]


def build_category_drivers(scored: Dict[str, Any]) -> List[Dict[str, Any]]:
    category_summary = scored.get("category_summary", {})
    drivers = []

    for category, data in category_summary.items():
        drivers.append({
            "category": category,
            "event_count": int(data.get("event_count", 0)),
            "score_total": int(data.get("score_total", 0)),
            "average_score": safe_round(data.get("average_score", 0)),
            "highest_score": int(data.get("highest_score", 0))
        })

    return sorted(drivers, key=lambda item: item["score_total"], reverse=True)[:TOP_DRIVER_LIMIT]


def build_actor_drivers(scored: Dict[str, Any]) -> List[Dict[str, Any]]:
    actor_summary = scored.get("actor_summary", {})
    actors = []

    for actor, data in actor_summary.items():
        actors.append({
            "actor": actor,
            "event_count": int(data.get("event_count", 0)),
            "score_total": int(data.get("score_total", 0)),
            "average_score": safe_round(data.get("average_score", 0)),
            "highest_score": int(data.get("highest_score", 0))
        })

    return sorted(actors, key=lambda item: item["score_total"], reverse=True)[:TOP_DRIVER_LIMIT]


def build_subtype_cards(scored: Dict[str, Any]) -> List[Dict[str, Any]]:
    subtype_summary = scored.get("subtype_summary", {})
    order = ["incident", "activity", "indicator", "assessment"]

    cards = []

    for subtype in order:
        data = subtype_summary.get(subtype, {})
        cards.append({
            "subtype": subtype,
            "label": subtype.title(),
            "event_count": int(data.get("event_count", 0)),
            "score_total": int(data.get("score_total", 0)),
            "average_score": safe_round(data.get("average_score", 0))
        })

    return cards


def compact_event(event: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "event_id": event.get("event_id"),
        "title": event.get("title"),
        "url": event.get("url"),
        "published_at": event.get("published_at"),
        "primary_country": event.get("primary_country", "Regional"),
        "countries": event.get("countries", [])[:5],
        "categories": event.get("categories", [])[:5],
        "actors": event.get("actors", [])[:5],
        "locations": event.get("locations", [])[:5],
        "event_type": event.get("event_type", "background"),
        "event_subtype": event.get("event_subtype", "assessment"),
        "source_count": int(event.get("source_count", 0)),
        "confidence": event.get("confidence", "low"),
        "confidence_score": int(event.get("confidence_score", 0)),
        "hybrid_threat_score": int(event.get("hybrid_threat_score", 0)),
        "hybrid_threat_level": event.get("hybrid_threat_level", "low"),
        "source_names": event.get("source_names", [])[:5],
        "related_item_count": int(event.get("related_item_count", 0))
    }


def build_top_events(scored: Dict[str, Any]) -> List[Dict[str, Any]]:
    events = scored.get("events", scored.get("items", []))

    compact = [compact_event(event) for event in events]
    compact = sorted(
        compact,
        key=lambda event: (
            event.get("hybrid_threat_score", 0),
            event.get("confidence_score", 0),
            event.get("published_at", "")
        ),
        reverse=True
    )

    return compact[:TOP_EVENT_LIMIT]


def build_recent_events(scored: Dict[str, Any]) -> List[Dict[str, Any]]:
    events = scored.get("events", scored.get("items", []))

    compact = [compact_event(event) for event in events]
    compact = sorted(
        compact,
        key=lambda event: event.get("published_at", ""),
        reverse=True
    )

    return compact[:TOP_EVENT_LIMIT]


def build_history(scored: Dict[str, Any], history: Dict[str, Any]) -> Dict[str, Any]:
    records = []

    if isinstance(history, dict):
        records = history.get("records", [])

    records = records[-HISTORY_LIMIT:]

    labels = []
    threat_index = []
    incident_count = []
    activity_count = []
    indicator_count = []
    assessment_count = []

    country_scores = {
        "Estonia": [],
        "Latvia": [],
        "Lithuania": [],
        "Poland": [],
        "Regional": []
    }

    for record in records:
        labels.append(record.get("date"))

        overall = record.get("overall", {})
        threat_index.append(
            safe_round(
                overall.get("threat_index", overall.get("average_score", 0))
            )
        )
        incident_count.append(int(overall.get("incident_count", 0)))
        activity_count.append(int(overall.get("activity_count", 0)))
        indicator_count.append(int(overall.get("indicator_count", 0)))
        assessment_count.append(int(overall.get("assessment_count", 0)))

        countries = record.get("countries", {})
        for country in country_scores:
            country_scores[country].append(
                safe_round(
                    countries.get(country, {}).get(
                        "average_score",
                        countries.get(country, {}).get("threat_index", 0)
                    )
                )
            )

    if not labels:
        summary = normalize_summary(scored)
        labels = [datetime.now(timezone.utc).date().isoformat()]
        threat_index = [summary["threat_index"]]
        incident_count = [summary["incident_count"]]
        activity_count = [summary["activity_count"]]
        indicator_count = [summary["indicator_count"]]
        assessment_count = [summary["assessment_count"]]

        for country in country_scores:
            country_scores[country] = [
                next(
                    (
                        card["average_score"]
                        for card in build_country_cards(scored)
                        if card["country"] == country
                    ),
                    0
                )
            ]

    return {
        "labels": labels,
        "threat_index": threat_index,
        "incident_count": incident_count,
        "activity_count": activity_count,
        "indicator_count": indicator_count,
        "assessment_count": assessment_count,
        "country_scores": country_scores
    }


def build_data_quality(scored: Dict[str, Any]) -> Dict[str, Any]:
    summary = normalize_summary(scored)

    raw_count = summary["raw_item_count"]
    filtered_count = summary["filtered_item_count"]
    clustered_count = summary["clustered_event_count"]

    filter_reduction = 0
    cluster_reduction = 0

    if raw_count > 0:
        filter_reduction = round((raw_count - filtered_count) / raw_count * 100, 2)

    if filtered_count > 0:
        cluster_reduction = round((filtered_count - clustered_count) / filtered_count * 100, 2)

    return {
        "raw_item_count": raw_count,
        "filtered_item_count": filtered_count,
        "clustered_event_count": clustered_count,
        "merged_item_count": summary["merged_item_count"],
        "filter_reduction_percent": filter_reduction,
        "cluster_reduction_percent": cluster_reduction
    }


def main() -> None:
    scored = load_json(SCORED_INPUT, default=None)
    history = load_json(HISTORY_INPUT, default={})

    if scored is None:
        raise FileNotFoundError(
            f"Missing scored input file: {SCORED_INPUT}. "
            "Run scripts/score_baltic_hybrid_news.py first."
        )

    payload = {
        "project": scored.get("project", "baltic-hybrid-monitor"),
        "title": "Baltic Hybrid Threat Monitor",
        "subtitle": "Event-based OSINT monitoring of hybrid threats in the Baltic states and Poland",
        "region": scored.get("region", "Baltic states and Poland"),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "latest_update": scored.get("generated_at"),
        "version": "Threat Intelligence Engine v1.0",
        "summary": normalize_summary(scored),
        "subtype_cards": build_subtype_cards(scored),
        "country_cards": build_country_cards(scored),
        "category_drivers": build_category_drivers(scored),
        "actor_drivers": build_actor_drivers(scored),
        "top_events": build_top_events(scored),
        "recent_events": build_recent_events(scored),
        "history": build_history(scored, history),
        "data_quality": build_data_quality(scored),
        "methodology": {
            "model": "Event-based rule-driven OSINT threat intelligence model.",
            "pipeline": [
                "RSS and HTML source collection",
                "Threat relevance filtering",
                "Event clustering",
                "Primary country assignment",
                "Threat ontology classification",
                "Confidence scoring",
                "Threat Score Engine v2",
                "Dashboard-optimized output"
            ],
            "event_subtypes": {
                "incident": "Reported operational event such as drone incident, cyberattack, sabotage, border event or GPS interference.",
                "activity": "Security or military activity shaping the threat environment.",
                "indicator": "Early warning or information signal.",
                "assessment": "Strategic, institutional or analytical background. It is not counted into the operational threat index."
            },
            "warning": "This dashboard is an OSINT monitoring aid. It does not confirm attribution and should not be treated as an official threat assessment."
        }
    }

    save_json(DASHBOARD_OUTPUT, payload)
    print(f"Saved dashboard data to {DASHBOARD_OUTPUT}")


if __name__ == "__main__":
    main()

