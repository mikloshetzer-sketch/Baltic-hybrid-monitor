import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, List


ROOT = Path(__file__).resolve().parents[1]

SCORED_INPUT = ROOT / "data" / "baltic_hybrid_scored_news.json"
HISTORY_INPUT = ROOT / "data" / "baltic_hybrid_history.json"
DASHBOARD_OUTPUT = ROOT / "docs" / "data" / "baltic_dashboard.json"


COUNTRIES = ["Estonia", "Latvia", "Lithuania", "Poland"]


def load_json(path: Path, default: Any) -> Any:
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


def calculate_change(records: List[Dict[str, Any]], field_path: List[str]) -> float:
    if len(records) < 2:
        return 0

    latest = records[-1]
    previous = records[-2]

    def get_value(record: Dict[str, Any]) -> float:
        value = record
        for field in field_path:
            value = value.get(field, {})
        if isinstance(value, (int, float)):
            return float(value)
        return 0

    return round(get_value(latest) - get_value(previous), 2)


def latest_records(history: Dict[str, Any], limit: int = 30) -> List[Dict[str, Any]]:
    records = history.get("records", [])
    return records[-limit:]


def build_country_cards(scored: Dict[str, Any], history_records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    country_summary = scored.get("country_summary", {})
    cards = []

    for country in COUNTRIES:
        current = country_summary.get(country, {})
        change = 0

        if len(history_records) >= 2:
            latest = history_records[-1].get("countries", {}).get(country, {})
            previous = history_records[-2].get("countries", {}).get(country, {})
            change = round(
                float(latest.get("average_score", 0)) -
                float(previous.get("average_score", 0)),
                2
            )

        cards.append({
            "country": country,
            "incident_count": current.get("incident_count", 0),
            "average_score": current.get("average_score", 0),
            "highest_score": current.get("highest_score", 0),
            "level": current.get("level", "low"),
            "change": change,
            "categories": current.get("categories", {})
        })

    return cards


def build_category_cards(scored: Dict[str, Any]) -> List[Dict[str, Any]]:
    categories = scored.get("category_summary", {})

    cards = []
    for category, data in categories.items():
        cards.append({
            "category": category,
            "incident_count": data.get("incident_count", 0),
            "average_score": data.get("average_score", 0),
            "highest_score": data.get("highest_score", 0)
        })

    return sorted(
        cards,
        key=lambda x: x.get("incident_count", 0),
        reverse=True
    )


def build_history_chart_data(records: List[Dict[str, Any]]) -> Dict[str, Any]:
    return {
        "labels": [record.get("date") for record in records],
        "overall_average_score": [
            record.get("overall", {}).get("average_score", 0)
            for record in records
        ],
        "overall_incident_count": [
            record.get("overall", {}).get("incident_count", 0)
            for record in records
        ],
        "country_average_scores": {
            country: [
                record.get("countries", {}).get(country, {}).get("average_score", 0)
                for record in records
            ]
            for country in COUNTRIES
        }
    }


def build_top_items(scored: Dict[str, Any], limit: int = 20) -> List[Dict[str, Any]]:
    items = scored.get("items", [])

    output = []
    for item in items[:limit]:
        output.append({
            "title": item.get("title"),
            "url": item.get("url"),
            "published_at": item.get("published_at"),
            "source_name": item.get("source_name"),
            "countries": item.get("countries", []),
            "categories": item.get("categories", []),
            "hybrid_threat_score": item.get("hybrid_threat_score", 0),
            "hybrid_threat_level": item.get("hybrid_threat_level", "low")
        })

    return output


def build_dashboard(scored: Dict[str, Any], history: Dict[str, Any]) -> Dict[str, Any]:
    records = latest_records(history, limit=30)
    overall = scored.get("overall_summary", {})

    dashboard = {
        "project": "baltic-hybrid-threat-monitor",
        "title": "Baltic Hybrid Threat Monitor",
        "subtitle": "Daily OSINT monitoring of Russian hybrid threats in the Baltic states and Poland",
        "region": "Baltic states and Poland",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "latest_update": scored.get("generated_at"),
        "summary": {
            "incident_count": overall.get("incident_count", 0),
            "score_total": overall.get("score_total", 0),
            "average_score": overall.get("average_score", 0),
            "highest_score": overall.get("highest_score", 0),
            "overall_level": overall.get("overall_level", "low"),
            "average_score_change": calculate_change(
                records,
                ["overall", "average_score"]
            ),
            "incident_count_change": calculate_change(
                records,
                ["overall", "incident_count"]
            )
        },
        "country_cards": build_country_cards(scored, records),
        "category_cards": build_category_cards(scored),
        "history": build_history_chart_data(records),
        "top_items": build_top_items(scored, limit=20),
        "methodology": {
            "model": "Rule-based OSINT scoring model based on the conflict-end-matrix structure.",
            "inputs": [
                "RSS news search feeds",
                "optional CEE Security Map JSON feed",
                "country and category keyword detection",
                "rule-based escalation scoring"
            ],
            "warning": "This dashboard is an OSINT monitoring aid. It does not confirm attribution and should not be treated as an official threat assessment."
        }
    }

    return dashboard


def main() -> None:
    scored = load_json(SCORED_INPUT, default=None)
    history = load_json(HISTORY_INPUT, default=None)

    if scored is None:
        raise FileNotFoundError(
            f"Missing scored input file: {SCORED_INPUT}"
        )

    if history is None:
        raise FileNotFoundError(
            f"Missing history input file: {HISTORY_INPUT}"
        )

    dashboard = build_dashboard(scored, history)
    save_json(DASHBOARD_OUTPUT, dashboard)

    print(f"Saved dashboard data to {DASHBOARD_OUTPUT}")


if __name__ == "__main__":
    main()
