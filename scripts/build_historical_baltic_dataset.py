import argparse
import json
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Dict, Any, List


ROOT = Path(__file__).resolve().parents[1]

SCORED_INPUT = ROOT / "data" / "baltic_hybrid_scored_news.json"

HISTORY_OUTPUT = ROOT / "data" / "baltic_hybrid_history.json"
DOCS_HISTORY_OUTPUT = ROOT / "docs" / "data" / "baltic_hybrid_history.json"

COUNTRIES = ["Estonia", "Latvia", "Lithuania", "Poland"]


def load_json(path: Path) -> Dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"Missing file: {path}")

    return json.loads(path.read_text(encoding="utf-8"))


def save_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )


def parse_date(value: str):
    if not value:
        return None

    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).date()
    except Exception:
        return None


def classify_level(score: float) -> str:
    if score >= 18:
        return "critical"
    if score >= 12:
        return "high"
    if score >= 7:
        return "elevated"
    if score >= 3:
        return "guarded"
    return "low"


def summarize_items(items: List[Dict[str, Any]]) -> Dict[str, Any]:
    if not items:
        return {
            "incident_count": 0,
            "score_total": 0,
            "average_score": 0,
            "highest_score": 0,
            "overall_level": "low"
        }

    scores = [int(item.get("hybrid_threat_score", 0)) for item in items]
    total = sum(scores)
    average = round(total / len(scores), 2)
    highest = max(scores)

    return {
        "incident_count": len(items),
        "score_total": total,
        "average_score": average,
        "highest_score": highest,
        "overall_level": classify_level(average)
    }


def summarize_countries(items: List[Dict[str, Any]]) -> Dict[str, Any]:
    output = {}

    for country in COUNTRIES:
        country_items = [
            item for item in items
            if country in item.get("countries", [])
        ]

        scores = [
            int(item.get("hybrid_threat_score", 0))
            for item in country_items
        ]

        categories = {}

        for item in country_items:
            for category in item.get("categories", []):
                categories[category] = categories.get(category, 0) + 1

        if scores:
            total = sum(scores)
            average = round(total / len(scores), 2)
            highest = max(scores)
        else:
            total = 0
            average = 0
            highest = 0

        output[country] = {
            "country": country,
            "incident_count": len(country_items),
            "score_total": total,
            "average_score": average,
            "highest_score": highest,
            "level": classify_level(average),
            "categories": categories
        }

    return output


def summarize_categories(items: List[Dict[str, Any]]) -> Dict[str, Any]:
    output = {}

    for item in items:
        score = int(item.get("hybrid_threat_score", 0))

        for category in item.get("categories", []):
            if category not in output:
                output[category] = {
                    "category": category,
                    "incident_count": 0,
                    "score_total": 0,
                    "average_score": 0,
                    "highest_score": 0
                }

            output[category]["incident_count"] += 1
            output[category]["score_total"] += score
            output[category]["highest_score"] = max(
                output[category]["highest_score"],
                score
            )

    for category, data in output.items():
        if data["incident_count"] > 0:
            data["average_score"] = round(
                data["score_total"] / data["incident_count"],
                2
            )

    return output


def top_items(items: List[Dict[str, Any]], limit: int = 10) -> List[Dict[str, Any]]:
    sorted_items = sorted(
        items,
        key=lambda item: int(item.get("hybrid_threat_score", 0)),
        reverse=True
    )

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
        for item in sorted_items[:limit]
    ]


def build_record(target_date, items: List[Dict[str, Any]], rolling_days: int) -> Dict[str, Any]:
    start_date = target_date - timedelta(days=rolling_days - 1)

    window_items = []

    for item in items:
        published_date = parse_date(item.get("published_at"))

        if not published_date:
            continue

        if start_date <= published_date <= target_date:
            window_items.append(item)

    return {
        "date": target_date.isoformat(),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "input_generated_at": datetime.now(timezone.utc).isoformat(),
        "window": {
            "type": "rolling",
            "days": rolling_days,
            "start_date": start_date.isoformat(),
            "end_date": target_date.isoformat()
        },
        "overall": summarize_items(window_items),
        "countries": summarize_countries(window_items),
        "categories": summarize_categories(window_items),
        "top_items": top_items(window_items)
    }


def build_history(scored_data: Dict[str, Any], days: int, rolling_days: int) -> Dict[str, Any]:
    today = datetime.now(timezone.utc).date()
    start_date = today - timedelta(days=days - 1)

    items = scored_data.get("items", [])

    records = []

    for index in range(days):
        current_date = start_date + timedelta(days=index)
        records.append(
            build_record(
                target_date=current_date,
                items=items,
                rolling_days=rolling_days
            )
        )

    return {
        "project": "baltic-hybrid-threat-monitor",
        "region": "Baltic states and Poland",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "record_count": len(records),
        "method": {
            "description": "Historical backfill generated from currently collected scored items using published_at dates.",
            "warning": "This is a backfill based on available collected RSS results. It is suitable for initializing the dashboard, but it is not a complete historical archive.",
            "days": days,
            "rolling_days": rolling_days
        },
        "records": records
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build historical Baltic Hybrid Threat Monitor dataset."
    )

    parser.add_argument(
        "--days",
        type=int,
        default=14,
        help="Number of historical days to generate. Default: 14."
    )

    parser.add_argument(
        "--rolling-days",
        type=int,
        default=14,
        help="Rolling window used for each daily snapshot. Default: 14."
    )

    args = parser.parse_args()

    scored_data = load_json(SCORED_INPUT)

    history = build_history(
        scored_data=scored_data,
        days=args.days,
        rolling_days=args.rolling_days
    )

    save_json(HISTORY_OUTPUT, history)
    save_json(DOCS_HISTORY_OUTPUT, history)

    print(f"Historical dataset generated.")
    print(f"Days: {args.days}")
    print(f"Rolling window: {args.rolling_days}")
    print(f"Saved: {HISTORY_OUTPUT}")
    print(f"Saved: {DOCS_HISTORY_OUTPUT}")


if __name__ == "__main__":
    main()
