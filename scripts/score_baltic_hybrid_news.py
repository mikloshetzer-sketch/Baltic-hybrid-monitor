import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Any


ROOT = Path(__file__).resolve().parents[1]

RAW_INPUT = ROOT / "data" / "baltic_hybrid_raw_news.json"
SCORED_OUTPUT = ROOT / "data" / "baltic_hybrid_scored_news.json"
DOCS_OUTPUT = ROOT / "docs" / "data" / "baltic_hybrid_scored_news.json"


COUNTRY_BASE = {
    "Estonia": 0,
    "Latvia": 0,
    "Lithuania": 0,
    "Poland": 0
}


CATEGORY_WEIGHTS = {
    "sabotage": 5,
    "cyber": 4,
    "disinformation": 3,
    "border_pressure": 4,
    "gps_interference": 4,
    "drone_incident": 5,
    "military_provocation": 5,
    "critical_infrastructure": 5,
    "espionage": 4,
    "migration_pressure": 3
}


ESCALATION_KEYWORDS = {
    "high": [
        "attack",
        "sabotage",
        "explosion",
        "drone",
        "airspace violation",
        "critical infrastructure",
        "military provocation",
        "arrested spy",
        "espionage",
        "hybrid attack"
    ],
    "medium": [
        "cyberattack",
        "ddos",
        "gps jamming",
        "border pressure",
        "migration pressure",
        "propaganda",
        "disinformation",
        "interference",
        "warning"
    ],
    "low": [
        "concern",
        "risk",
        "threat",
        "monitoring",
        "preparedness",
        "exercise"
    ]
}


def load_raw_data() -> Dict[str, Any]:
    if not RAW_INPUT.exists():
        raise FileNotFoundError(
            f"Missing raw input file: {RAW_INPUT}. "
            "Run scripts/fetch_baltic_hybrid_news.py first."
        )

    return json.loads(RAW_INPUT.read_text(encoding="utf-8"))


def text_blob(item: Dict[str, Any]) -> str:
    return f"{item.get('title', '')} {item.get('summary', '')}".lower()


def keyword_score(text: str) -> int:
    score = 0

    for word in ESCALATION_KEYWORDS["high"]:
        if word in text:
            score += 5

    for word in ESCALATION_KEYWORDS["medium"]:
        if word in text:
            score += 3

    for word in ESCALATION_KEYWORDS["low"]:
        if word in text:
            score += 1

    return score


def category_score(categories: List[str]) -> int:
    score = 0

    for category in categories:
        score += CATEGORY_WEIGHTS.get(category, 0)

    return score


def classify_level(score: int) -> str:
    if score >= 18:
        return "critical"
    if score >= 12:
        return "high"
    if score >= 7:
        return "elevated"
    if score >= 3:
        return "guarded"
    return "low"


def score_item(item: Dict[str, Any]) -> Dict[str, Any]:
    text = text_blob(item)
    categories = item.get("categories", [])
    base_relevance = float(item.get("relevance_score", 0))

    score = 0
    score += int(base_relevance)
    score += keyword_score(text)
    score += category_score(categories)

    if len(item.get("countries", [])) > 1:
        score += 2

    if "russia" in text or "russian" in text:
        score += 2

    if "belarus" in text:
        score += 2

    if "nato" in text:
        score += 1

    item["hybrid_threat_score"] = score
    item["hybrid_threat_level"] = classify_level(score)

    return item


def build_country_summary(items: List[Dict[str, Any]]) -> Dict[str, Any]:
    summary = {
        country: {
            "country": country,
            "incident_count": 0,
            "score_total": 0,
            "average_score": 0,
            "highest_score": 0,
            "level": "low",
            "categories": {}
        }
        for country in COUNTRY_BASE.keys()
    }

    for item in items:
        countries = item.get("countries", [])
        score = int(item.get("hybrid_threat_score", 0))

        for country in countries:
            if country not in summary:
                continue

            summary[country]["incident_count"] += 1
            summary[country]["score_total"] += score
            summary[country]["highest_score"] = max(
                summary[country]["highest_score"],
                score
            )

            for category in item.get("categories", []):
                summary[country]["categories"][category] = (
                    summary[country]["categories"].get(category, 0) + 1
                )

    for country, data in summary.items():
        if data["incident_count"] > 0:
            data["average_score"] = round(
                data["score_total"] / data["incident_count"],
                2
            )

        data["level"] = classify_level(int(data["average_score"]))

    return summary


def build_category_summary(items: List[Dict[str, Any]]) -> Dict[str, Any]:
    summary = {}

    for item in items:
        score = int(item.get("hybrid_threat_score", 0))

        for category in item.get("categories", []):
            if category not in summary:
                summary[category] = {
                    "category": category,
                    "incident_count": 0,
                    "score_total": 0,
                    "average_score": 0,
                    "highest_score": 0
                }

            summary[category]["incident_count"] += 1
            summary[category]["score_total"] += score
            summary[category]["highest_score"] = max(
                summary[category]["highest_score"],
                score
            )

    for category, data in summary.items():
        if data["incident_count"] > 0:
            data["average_score"] = round(
                data["score_total"] / data["incident_count"],
                2
            )

    return summary


def build_overall_summary(items: List[Dict[str, Any]]) -> Dict[str, Any]:
    if not items:
        return {
            "incident_count": 0,
            "score_total": 0,
            "average_score": 0,
            "highest_score": 0,
            "overall_level": "low"
        }

    score_total = sum(int(item.get("hybrid_threat_score", 0)) for item in items)
    highest_score = max(int(item.get("hybrid_threat_score", 0)) for item in items)
    average_score = round(score_total / len(items), 2)

    return {
        "incident_count": len(items),
        "score_total": score_total,
        "average_score": average_score,
        "highest_score": highest_score,
        "overall_level": classify_level(int(average_score))
    }


def main() -> None:
    raw_data = load_raw_data()
    items = raw_data.get("items", [])

    scored_items = [score_item(item) for item in items]
    scored_items = sorted(
        scored_items,
        key=lambda x: x.get("hybrid_threat_score", 0),
        reverse=True
    )

    payload = {
        "project": raw_data.get("project", "baltic-hybrid-threat-monitor"),
        "region": raw_data.get("region", "Baltic states and Poland"),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "input_generated_at": raw_data.get("generated_at"),
        "method": {
            "description": "Simple rule-based scoring model following the conflict-end-matrix style.",
            "score_components": [
                "raw relevance score",
                "hybrid escalation keywords",
                "threat category weights",
                "multi-country relevance bonus",
                "Russia/Belarus/NATO keyword modifiers"
            ],
            "levels": {
                "low": "0-2",
                "guarded": "3-6",
                "elevated": "7-11",
                "high": "12-17",
                "critical": "18+"
            }
        },
        "overall_summary": build_overall_summary(scored_items),
        "country_summary": build_country_summary(scored_items),
        "category_summary": build_category_summary(scored_items),
        "items": scored_items
    }

    SCORED_OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    DOCS_OUTPUT.parent.mkdir(parents=True, exist_ok=True)

    SCORED_OUTPUT.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )

    DOCS_OUTPUT.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )

    print(f"Saved scored data to {SCORED_OUTPUT}")
    print(f"Saved public scored data to {DOCS_OUTPUT}")
    print(f"Items scored: {len(scored_items)}")


if __name__ == "__main__":
    main()
