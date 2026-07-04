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
    return history.get("records", [])[-limit:]


def get_latest_record(records: List[Dict[str, Any]]) -> Dict[str, Any]:
    return records[-1] if records else {}


def calculate_change(records: List[Dict[str, Any]], path: List[str]) -> float:
    if len(records) < 2:
        return 0

    def get_value(record: Dict[str, Any]) -> float:
        value = record
        for key in path:
            value = value.get(key, {})
        return float(value) if isinstance(value, (int, float)) else 0

    return round(get_value(records[-1]) - get_value(records[-2]), 2)


def build_history_chart_data(records: List[Dict[str, Any]]) -> Dict[str, Any]:
    return {
        "labels": [record.get("date") for record in records],

        "threat_index": {
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
        },

        "daily_activity": {
            "overall_average_score": [
                record.get("daily_activity", {}).get("overall", {}).get("average_score", 0)
                for record in records
            ],
            "overall_incident_count": [
                record.get("daily_activity", {}).get("overall", {}).get("incident_count", 0)
                for record in records
            ],
            "country_average_scores": {
                country: [
                    record.get("daily_activity", {}).get("countries", {}).get(country, {}).get("average_score", 0)
                    for record in records
                ]
                for country in COUNTRIES
            }
        }
    }


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
    latest_daily = latest.get("daily_activity", {}).get("overall", {})

    return {
        "project": "baltic-hybrid-monitor",
        "title": "Baltic Hybrid Threat Monitor",
        "subtitle": "Daily OSINT monitoring of Russian hybrid threats in the Baltic states and Poland",
        "region": "Baltic states and Poland",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "latest_update": latest.get("generated_at") or scored.get("generated_at"),
        "current_window": build_window_info(records),

        "summary": {
            "threat_index": {
                "incident_count": latest_overall.get("incident_count", 0),
                "score_total": latest_overall.get("score_total", 0),
                "average_score": latest_overall.get("average_score", 0),
                "highest_score": latest_overall.get("highest_score", 0),
                "overall_level": latest_overall.get("overall_level", "low"),
                "average_score_change": calculate_change(records, ["overall", "average_score"]),
                "incident_count_change": calculate_change(records, ["overall", "incident_count"])
            },
            "daily_activity": {
                "incident_count": latest_daily.get("incident_count", 0),
                "score_total": latest_daily.get("score_total", 0),
                "average_score": latest_daily.get("average_score", 0),
                "highest_score": latest_daily.get("highest_score", 0),
                "overall_level": latest_daily.get("overall_level", "low"),
                "average_score_change": calculate_change(records, ["daily_activity", "overall", "average_score"]),
                "incident_count_change": calculate_change(records, ["daily_activity", "overall", "incident_count"])
            }
        },

        "history": build_history_chart_data(records),

        "methodology": {
            "model": "Rule-based OSINT scoring model based on the conflict-end-matrix structure.",
            "metrics": {
                "threat_index": "Threat Index is calculated from the rolling window ending on each displayed date.",
                "daily_activity": "Daily Activity is calculated only from items published on the displayed date."
            },
            "warning": "This dashboard is an OSINT monitoring aid. It does not confirm attribution and should not be treated as an official threat assessment."
        }
    }


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
