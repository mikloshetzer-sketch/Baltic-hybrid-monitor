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


def latest_records(history: Dict[str, Any], limit: int = 30) -> List[Dict[str, Any]]:
    records = history.get("records", [])
    return records[-limit:]


def calculate_change(records: List[Dict[str, Any]], field_path: List[str]) -> float:
    if len(records) < 2:
        return 0

    latest = records[-1]
    previous = records[-2]

    def get_value(record: Dict[str, Any]) -> float:
        value = record
        for field in field_path:
            value = value.get(field, {})
        return float(value) if isinstance(value, (int, float)) else 0

    return round(get_value(latest) - get_value(previous), 2)


def get_latest_record(records: List[Dict[str, Any]]) -> Dict[str, Any]:
    if not records:
        return {}
    return records[-1]


def build_country_cards(records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    latest = get_latest_record(records)
    latest_countries = latest.get("countries", {})

    cards = []

    for country in COUNTRIES:
        current = latest_countries.get(country, {})
        change = calculate_change(
            records,
            ["countries", country, "average_score"]
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


def build_category_cards(records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    latest = get_latest_record(records)
    categories = latest.get("categories", {})

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
        "labels": [
            record.get("date")
            for record in records
        ],
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
        },
        "country_incident_counts": {
            country: [
                record.get("countries", {}).get(country, {}).get("incident_count", 0)
                for record in records
            ]
            for country in COUNTRIES
        }
    }


def build_top_items(records: List[Dict[str, Any]], limit: int = 20) -> List[Dict[str, Any]]:
    latest = get_latest_record(records)
    items = latest.get("top_items", [])

    return items[:limit]


def build_window_info(records: List[Dict[str, Any]]) -> Dict[str, Any]:
    latest = get_latest_record(records)
    window = latest.get("window", {})

    return {
        "type": window.get("type", "rolling"),
        "days": window.get("days"),
        "start_date": window.get("start_date"),
        "end_date": window.get("end_date")
    }


def build_dashboard(scored: Dict[str, Any], history: Dict[str, Any]) -> Dict[str, Any]:
    records = latest_records(history, limit=30)
    latest = get_latest_record(records)
    latest_overall = latest.get("overall", {})

    dashboard = {
        "project": "baltic-hybrid-monitor",
        "title": "Baltic Hybrid Threat Monitor",
        "subtitle": "Daily OSINT monitoring of Russian hybrid threats in the Baltic states and Poland",
        "region": "Baltic states and Poland",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "latest_update": latest.get("generated_at") or scored.get("generated_at"),
        "current_window": build_window_info(records),
        "summary": {
            "incident_count": latest_overall.get("incident_count", 0),
            "score_total": latest_overall.get("score_total", 0),
            "average_score": latest_overall.get("average_score", 0),
            "highest_score": latest_overall.get("highest_score", 0),
            "overall_level": latest_overall.get("overall_level", "low"),
            "average_score_change": calculate_change(
                records,
                ["overall", "average_score"]
            ),
            "incident_count_change": calculate_change(
                records,
                ["overall", "incident_count"]
            )
        },
        "country_cards": build_country_cards(records),
        "category_cards": build_category_cards(records),
        "history": build_history_chart_data(records),
        "top_items": build_top_items(records, limit=20),
        "methodology": {
            "model": "Rule-based OSINT scoring model based on the conflict-end-matrix structure.",
            "inputs": [
                "RSS news search feeds",
                "optional CEE Security Map JSON feed",
                "country and category keyword detection",
                "rule-based escalation scoring",
                "rolling-window historical snapshots"
            ],
            "dashboard_interpretation": [
                "The summary indicators describe the latest available history record, not the full raw dataset.",
                "The incident count refers to the current rolling window.",
                "Each point in the chart represents the assessment ending on the displayed date.",
                "Moving averages smooth the displayed history series and do not represent separate daily event counts."
            ],
            "warning": "This dashboard is an OSINT monitoring aid. It does not confirm attribution and should not be treated as an official threat assessment."
        }
    }

    return dashboard


def main() -> None:
    scored = load_json(SCORED_INPUT, default=None)
    history = load_json(HISTORY_INPUT, default=None)

    if scored is None:
        raise FileNotFoundError(f"Missing scored input file: {SCORED_INPUT}")

    if history is None:
        raise FileNotFoundError(f"Missing history input file: {HISTORY_INPUT}")

    dashboard = build_dashboard(scored, history)
    save_json(DASHBOARD_OUTPUT, dashboard)

    print(f"Saved dashboard data to {DASHBOARD_OUTPUT}")


if __name__ == "__main__":
    main()
