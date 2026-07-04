import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, List


ROOT = Path(__file__).resolve().parents[1]

SCORED_INPUT = ROOT / "data" / "baltic_hybrid_scored_news.json"
HISTORY_OUTPUT = ROOT / "data" / "baltic_hybrid_history.json"
DOCS_HISTORY_OUTPUT = ROOT / "docs" / "data" / "baltic_hybrid_history.json"


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


def today_utc() -> str:
    return datetime.now(timezone.utc).date().isoformat()


def get_country_snapshot(scored_data: Dict[str, Any]) -> Dict[str, Any]:
    country_summary = scored_data.get("country_summary", {})
    snapshot = {}

    for country in COUNTRIES:
        item = country_summary.get(country, {})

        snapshot[country] = {
            "incident_count": item.get("incident_count", 0),
            "score_total": item.get("score_total", 0),
            "average_score": item.get("average_score", 0),
            "highest_score": item.get("highest_score", 0),
            "level": item.get("level", "low"),
            "categories": item.get("categories", {})
        }

    return snapshot


def get_category_snapshot(scored_data: Dict[str, Any]) -> Dict[str, Any]:
    return scored_data.get("category_summary", {})


def get_top_items(scored_data: Dict[str, Any], limit: int = 10) -> List[Dict[str, Any]]:
    items = scored_data.get("items", [])

    top_items = sorted(
        items,
        key=lambda x: x.get("hybrid_threat_score", 0),
        reverse=True
    )[:limit]

    return [
        {
            "id": item.get("id"),
            "title": item.get("title"),
            "url": item.get("url"),
            "published_at": item.get("published_at"),
            "source_name": item.get("source_name"),
            "countries": item.get("countries", []),
            "categories": item.get("categories", []),
            "hybrid_threat_score": item.get("hybrid_threat_score", 0),
            "hybrid_threat_level": item.get("hybrid_threat_level", "low")
        }
        for item in top_items
    ]


def build_daily_record(scored_data: Dict[str, Any]) -> Dict[str, Any]:
    overall = scored_data.get("overall_summary", {})

    return {
        "date": today_utc(),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "input_generated_at": scored_data.get("generated_at"),
        "overall": {
            "incident_count": overall.get("incident_count", 0),
            "score_total": overall.get("score_total", 0),
            "average_score": overall.get("average_score", 0),
            "highest_score": overall.get("highest_score", 0),
            "overall_level": overall.get("overall_level", "low")
        },
        "countries": get_country_snapshot(scored_data),
        "categories": get_category_snapshot(scored_data),
        "top_items": get_top_items(scored_data, limit=10)
    }


def update_history(history: Dict[str, Any], daily_record: Dict[str, Any]) -> Dict[str, Any]:
    if not history:
        history = {
            "project": "baltic-hybrid-threat-monitor",
            "region": "Baltic states and Poland",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": None,
            "records": []
        }

    records = history.get("records", [])
    today = daily_record["date"]

    records = [
        record for record in records
        if record.get("date") != today
    ]

    records.append(daily_record)
    records = sorted(records, key=lambda x: x.get("date", ""))

    history["updated_at"] = datetime.now(timezone.utc).isoformat()
    history["record_count"] = len(records)
    history["records"] = records

    return history


def main() -> None:
    scored_data = load_json(SCORED_INPUT, default=None)

    if scored_data is None:
        raise FileNotFoundError(
            f"Missing scored input file: {SCORED_INPUT}. "
            "Run scripts/score_baltic_hybrid_news.py first."
        )

    history = load_json(HISTORY_OUTPUT, default={})
    daily_record = build_daily_record(scored_data)
    updated_history = update_history(history, daily_record)

    save_json(HISTORY_OUTPUT, updated_history)
    save_json(DOCS_HISTORY_OUTPUT, updated_history)

    print(f"Updated history: {HISTORY_OUTPUT}")
    print(f"Updated public history: {DOCS_HISTORY_OUTPUT}")
    print(f"History records: {updated_history.get('record_count', 0)}")


if __name__ == "__main__":
    main()
