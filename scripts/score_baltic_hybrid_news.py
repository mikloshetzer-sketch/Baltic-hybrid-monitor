import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Any


ROOT = Path(__file__).resolve().parents[1]

CLUSTERED_INPUT = ROOT / "data" / "baltic_hybrid_clustered_events.json"
SCORED_OUTPUT = ROOT / "data" / "baltic_hybrid_scored_news.json"
DOCS_OUTPUT = ROOT / "docs" / "data" / "baltic_hybrid_scored_news.json"


COUNTRIES = ["Estonia", "Latvia", "Lithuania", "Poland", "Regional"]


CATEGORY_WEIGHTS = {
    "sabotage": 18,
    "critical_infrastructure": 17,
    "drone_incident": 16,
    "gps_interference": 15,
    "cyber": 14,
    "espionage": 13,
    "military_provocation": 12,
    "border_pressure": 10,
    "migration_pressure": 8,
    "disinformation": 7
}


SUBTYPE_WEIGHTS = {
    "incident": 1.00,
    "activity": 0.45,
    "indicator": 0.25,
    "assessment": 0.00
}


CONFIDENCE_MULTIPLIERS = {
    "very_high": 1.20,
    "high": 1.10,
    "medium": 1.00,
    "low": 0.85
}


ACTOR_WEIGHTS = {
    "Russia": 8,
    "Belarus": 6,
    "GRU": 8,
    "FSB": 8,
    "Sandworm": 8,
    "NATO": 4,
    "EU": 2
}


LOCATION_WEIGHTS = {
    "Kaliningrad": 8,
    "Suwalki Gap": 9,
    "Baltic Sea": 6,
    "Belarus Border": 7,
    "Poland-Belarus Border": 8,
    "Narva": 5,
    "Riga": 3,
    "Tallinn": 3,
    "Vilnius": 3,
    "Klaipeda": 4,
    "Gdansk": 4
}


ESCALATION_TERMS = {
    "critical": [
        "sabotage",
        "explosion",
        "airspace violation",
        "critical infrastructure",
        "undersea cable",
        "subsea cable",
        "pipeline",
        "ransomware",
        "wiper",
        "missile",
        "drone attack",
        "hybrid attack",
        "spy",
        "espionage"
    ],
    "high": [
        "cyberattack",
        "cyber attack",
        "ddos",
        "gps jamming",
        "gnss jamming",
        "spoofing",
        "border incident",
        "border crossing",
        "military provocation",
        "fighter jet",
        "scramble",
        "intercept",
        "migration pressure",
        "disinformation campaign"
    ],
    "medium": [
        "warning",
        "threat",
        "risk",
        "preparedness",
        "exercise",
        "sanctions",
        "eastern flank",
        "air policing"
    ]
}


def load_clustered_data() -> Dict[str, Any]:
    if not CLUSTERED_INPUT.exists():
        raise FileNotFoundError(
            f"Missing clustered input file: {CLUSTERED_INPUT}. "
            "Run scripts/fetch_baltic_hybrid_news.py, "
            "scripts/filter_baltic_hybrid_news.py and "
            "scripts/cluster_baltic_hybrid_events.py first."
        )

    return json.loads(CLUSTERED_INPUT.read_text(encoding="utf-8"))


def save_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )


def text_blob(event: Dict[str, Any]) -> str:
    return " ".join([
        str(event.get("title", "")),
        str(event.get("summary", "")),
        " ".join(event.get("categories", [])),
        " ".join(event.get("actors", [])),
        " ".join(event.get("locations", []))
    ]).lower()


def keyword_score(text: str) -> int:
    score = 0

    for term in ESCALATION_TERMS["critical"]:
        if term in text:
            score += 8

    for term in ESCALATION_TERMS["high"]:
        if term in text:
            score += 5

    for term in ESCALATION_TERMS["medium"]:
        if term in text:
            score += 2

    return score


def category_score(categories: List[str]) -> int:
    return sum(CATEGORY_WEIGHTS.get(category, 0) for category in categories)


def actor_score(actors: List[str]) -> int:
    return sum(ACTOR_WEIGHTS.get(actor, 0) for actor in actors)


def location_score(locations: List[str]) -> int:
    return sum(LOCATION_WEIGHTS.get(location, 0) for location in locations)


def source_confirmation_score(event: Dict[str, Any]) -> int:
    source_count = int(event.get("source_count", 1))
    related_item_count = int(event.get("related_item_count", 1))
    confidence_score = int(event.get("confidence_score", 0))

    score = 0
    score += min(source_count, 6) * 3
    score += min(related_item_count, 8) * 1

    if confidence_score >= 80:
        score += 8
    elif confidence_score >= 65:
        score += 5
    elif confidence_score >= 50:
        score += 3

    return score


def strategic_modifier(event: Dict[str, Any]) -> int:
    categories = set(event.get("categories", []))
    actors = set(event.get("actors", []))
    locations = set(event.get("locations", []))
    text = text_blob(event)

    modifier = 0

    if "Russia" in actors and "NATO" in actors:
        modifier += 5

    if "Belarus" in actors and ("border_pressure" in categories or "migration_pressure" in categories):
        modifier += 5

    if "Kaliningrad" in locations and "gps_interference" in categories:
        modifier += 6

    if "Suwalki Gap" in locations:
        modifier += 7

    if "Baltic Sea" in locations and "critical_infrastructure" in categories:
        modifier += 6

    if "cyber" in categories and "critical_infrastructure" in categories:
        modifier += 5

    if "drone_incident" in categories and "military_provocation" in categories:
        modifier += 4

    if "no signs of russian attack" in text:
        modifier -= 5

    if "full-scale war is not imminent" in text:
        modifier -= 4

    return modifier


def classify_level(score: int) -> str:
    if score >= 80:
        return "critical"
    if score >= 60:
        return "high"
    if score >= 40:
        return "elevated"
    if score >= 20:
        return "guarded"
    return "low"


def score_event(event: Dict[str, Any]) -> Dict[str, Any]:
    text = text_blob(event)

    subtype = event.get("event_subtype", "assessment")
    confidence = event.get("confidence", "low")

    base_score = 0
    base_score += int(round(float(event.get("relevance_score", 0))))
    base_score += keyword_score(text)
    base_score += category_score(event.get("categories", []))
    base_score += actor_score(event.get("actors", []))
    base_score += location_score(event.get("locations", []))
    base_score += source_confirmation_score(event)
    base_score += strategic_modifier(event)

    if base_score < 0:
        base_score = 0

    subtype_weight = SUBTYPE_WEIGHTS.get(subtype, 0.0)
    confidence_multiplier = CONFIDENCE_MULTIPLIERS.get(confidence, 0.85)

    weighted_score = round(base_score * subtype_weight * confidence_multiplier, 2)

    if subtype == "assessment":
        weighted_score = 0

    event["hybrid_threat_score"] = int(round(weighted_score))
    event["hybrid_threat_level"] = classify_level(event["hybrid_threat_score"])
    event["score_breakdown"] = {
        "raw_base_score": base_score,
        "relevance": int(round(float(event.get("relevance_score", 0)))),
        "keywords": keyword_score(text),
        "categories": category_score(event.get("categories", [])),
        "actors": actor_score(event.get("actors", [])),
        "locations": location_score(event.get("locations", [])),
        "source_confirmation": source_confirmation_score(event),
        "strategic_modifier": strategic_modifier(event),
        "event_subtype": subtype,
        "subtype_weight": subtype_weight,
        "confidence": confidence,
        "confidence_multiplier": confidence_multiplier,
        "weighted_score": weighted_score
    }

    return event


def build_country_summary(events: List[Dict[str, Any]]) -> Dict[str, Any]:
    summary = {
        country: {
            "country": country,
            "event_count": 0,
            "incident_count": 0,
            "activity_count": 0,
            "indicator_count": 0,
            "assessment_count": 0,
            "score_total": 0,
            "average_score": 0,
            "highest_score": 0,
            "level": "low",
            "categories": {},
            "actors": {}
        }
        for country in COUNTRIES
    }

    for event in events:
        primary_country = event.get("primary_country", "Regional")
        if primary_country not in summary:
            primary_country = "Regional"

        subtype = event.get("event_subtype", "assessment")
        score = int(event.get("hybrid_threat_score", 0))

        data = summary[primary_country]
        data["event_count"] += 1
        data["score_total"] += score
        data["highest_score"] = max(data["highest_score"], score)

        if subtype == "incident":
            data["incident_count"] += 1
        elif subtype == "activity":
            data["activity_count"] += 1
        elif subtype == "indicator":
            data["indicator_count"] += 1
        else:
            data["assessment_count"] += 1

        for category in event.get("categories", []):
            data["categories"][category] = data["categories"].get(category, 0) + 1

        for actor in event.get("actors", []):
            data["actors"][actor] = data["actors"].get(actor, 0) + 1

    for country, data in summary.items():
        if data["event_count"] > 0:
            data["average_score"] = round(data["score_total"] / data["event_count"], 2)

        data["level"] = classify_level(int(data["average_score"]))

    return summary


def build_category_summary(events: List[Dict[str, Any]]) -> Dict[str, Any]:
    summary: Dict[str, Any] = {}

    for event in events:
        score = int(event.get("hybrid_threat_score", 0))

        for category in event.get("categories", []):
            if category not in summary:
                summary[category] = {
                    "category": category,
                    "event_count": 0,
                    "score_total": 0,
                    "average_score": 0,
                    "highest_score": 0
                }

            summary[category]["event_count"] += 1
            summary[category]["score_total"] += score
            summary[category]["highest_score"] = max(summary[category]["highest_score"], score)

    for category, data in summary.items():
        if data["event_count"] > 0:
            data["average_score"] = round(data["score_total"] / data["event_count"], 2)

    return dict(sorted(summary.items(), key=lambda pair: pair[1]["score_total"], reverse=True))


def build_actor_summary(events: List[Dict[str, Any]]) -> Dict[str, Any]:
    summary: Dict[str, Any] = {}

    for event in events:
        score = int(event.get("hybrid_threat_score", 0))

        for actor in event.get("actors", []):
            if actor not in summary:
                summary[actor] = {
                    "actor": actor,
                    "event_count": 0,
                    "score_total": 0,
                    "average_score": 0,
                    "highest_score": 0
                }

            summary[actor]["event_count"] += 1
            summary[actor]["score_total"] += score
            summary[actor]["highest_score"] = max(summary[actor]["highest_score"], score)

    for actor, data in summary.items():
        if data["event_count"] > 0:
            data["average_score"] = round(data["score_total"] / data["event_count"], 2)

    return dict(sorted(summary.items(), key=lambda pair: pair[1]["score_total"], reverse=True))


def build_subtype_summary(events: List[Dict[str, Any]]) -> Dict[str, Any]:
    summary = {
        "incident": {"event_count": 0, "score_total": 0, "average_score": 0},
        "activity": {"event_count": 0, "score_total": 0, "average_score": 0},
        "indicator": {"event_count": 0, "score_total": 0, "average_score": 0},
        "assessment": {"event_count": 0, "score_total": 0, "average_score": 0}
    }

    for event in events:
        subtype = event.get("event_subtype", "assessment")
        if subtype not in summary:
            subtype = "assessment"

        score = int(event.get("hybrid_threat_score", 0))
        summary[subtype]["event_count"] += 1
        summary[subtype]["score_total"] += score

    for subtype, data in summary.items():
        if data["event_count"] > 0:
            data["average_score"] = round(data["score_total"] / data["event_count"], 2)

    return summary


def build_overall_summary(events: List[Dict[str, Any]]) -> Dict[str, Any]:
    if not events:
        return {
            "event_count": 0,
            "incident_count": 0,
            "activity_count": 0,
            "indicator_count": 0,
            "assessment_count": 0,
            "score_total": 0,
            "average_score": 0,
            "highest_score": 0,
            "threat_index": 0,
            "overall_level": "low"
        }

    score_total = sum(int(event.get("hybrid_threat_score", 0)) for event in events)
    highest_score = max(int(event.get("hybrid_threat_score", 0)) for event in events)
    average_score = round(score_total / len(events), 2)

    incident_count = sum(1 for event in events if event.get("event_subtype") == "incident")
    activity_count = sum(1 for event in events if event.get("event_subtype") == "activity")
    indicator_count = sum(1 for event in events if event.get("event_subtype") == "indicator")
    assessment_count = sum(1 for event in events if event.get("event_subtype") == "assessment")

    operational_events = [
        event for event in events
        if event.get("event_subtype") in {"incident", "activity", "indicator"}
    ]

    if operational_events:
        threat_index = round(
            sum(int(event.get("hybrid_threat_score", 0)) for event in operational_events) /
            len(operational_events),
            2
        )
    else:
        threat_index = 0

    return {
        "event_count": len(events),
        "incident_count": incident_count,
        "activity_count": activity_count,
        "indicator_count": indicator_count,
        "assessment_count": assessment_count,
        "score_total": score_total,
        "average_score": average_score,
        "highest_score": highest_score,
        "threat_index": threat_index,
        "overall_level": classify_level(int(threat_index))
    }


def main() -> None:
    clustered = load_clustered_data()
    events = clustered.get("events", [])

    scored_events = [score_event(event) for event in events]
    scored_events = sorted(
        scored_events,
        key=lambda event: (
            event.get("hybrid_threat_score", 0),
            event.get("confidence_score", 0),
            event.get("published_at", "")
        ),
        reverse=True
    )

    payload = {
        "project": clustered.get("project", "baltic-hybrid-monitor"),
        "region": clustered.get("region", "Baltic states and Poland"),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "input_generated_at": clustered.get("generated_at"),
        "raw_item_count": clustered.get("raw_item_count"),
        "filtered_item_count": clustered.get("filtered_item_count"),
        "clustered_event_count": clustered.get("event_count"),
        "merged_item_count": clustered.get("merged_item_count"),
        "method": {
            "description": "Threat Score Engine v2 using clustered events and threat ontology subtypes.",
            "input": "data/baltic_hybrid_clustered_events.json",
            "score_components": [
                "event relevance score",
                "hybrid escalation keywords",
                "threat category weights",
                "actor weights",
                "strategic location weights",
                "source confirmation",
                "strategic modifiers",
                "event subtype weighting",
                "confidence multiplier"
            ],
            "subtype_weights": SUBTYPE_WEIGHTS,
            "confidence_multipliers": CONFIDENCE_MULTIPLIERS,
            "levels": {
                "low": "0-19",
                "guarded": "20-39",
                "elevated": "40-59",
                "high": "60-79",
                "critical": "80+"
            }
        },
        "overall_summary": build_overall_summary(scored_events),
        "country_summary": build_country_summary(scored_events),
        "category_summary": build_category_summary(scored_events),
        "actor_summary": build_actor_summary(scored_events),
        "subtype_summary": build_subtype_summary(scored_events),
        "items": scored_events,
        "events": scored_events
    }

    save_json(SCORED_OUTPUT, payload)
    save_json(DOCS_OUTPUT, payload)

    print(f"Saved scored event data to {SCORED_OUTPUT}")
    print(f"Saved public scored event data to {DOCS_OUTPUT}")
    print(f"Events scored: {len(scored_events)}")
    print(f"Threat index: {payload['overall_summary']['threat_index']}")
    print(f"Overall level: {payload['overall_summary']['overall_level']}")


if __name__ == "__main__":
    main()
