import argparse
import json
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Dict, Any, List, Optional


ROOT = Path(__file__).resolve().parents[1]

SCORED_INPUT = ROOT / "data" / "baltic_hybrid_scored_news.json"

HISTORY_OUTPUT = ROOT / "data" / "baltic_hybrid_history.json"
DOCS_HISTORY_OUTPUT = ROOT / "docs" / "data" / "baltic_hybrid_history.json"


COUNTRIES = [
    "Estonia",
    "Latvia",
    "Lithuania",
    "Poland",
    "Regional"
]


# ---------------------------------------------------------------------
# BASIC IO
# ---------------------------------------------------------------------

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
        json.dumps(
            payload,
            ensure_ascii=False,
            indent=2
        ),
        encoding="utf-8"
    )


# ---------------------------------------------------------------------
# DATE HANDLING
# ---------------------------------------------------------------------

def parse_datetime(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None

    try:
        dt = datetime.fromisoformat(
            str(value).replace("Z", "+00:00")
        )

        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)

        return dt.astimezone(timezone.utc)

    except Exception:
        return None


def parse_date(value: Optional[str]):
    dt = parse_datetime(value)

    if dt is None:
        return None

    return dt.date()


def utc_today():
    return datetime.now(timezone.utc).date()


# ---------------------------------------------------------------------
# LEVEL CLASSIFICATION
# ---------------------------------------------------------------------

def classify_level(score: float) -> str:
    """
    Daily / rolling average threat level.

    Thresholds intentionally follow the existing historical
    dashboard logic instead of the individual-event 0–100 scale.
    """

    if score >= 18:
        return "critical"

    if score >= 12:
        return "high"

    if score >= 7:
        return "elevated"

    if score >= 3:
        return "guarded"

    return "low"


# ---------------------------------------------------------------------
# EVENT HELPERS
# ---------------------------------------------------------------------

def event_score(item: Dict[str, Any]) -> int:
    try:
        return int(
            round(
                float(
                    item.get(
                        "hybrid_threat_score",
                        0
                    )
                )
            )
        )
    except Exception:
        return 0


def event_subtype(item: Dict[str, Any]) -> str:
    subtype = str(
        item.get(
            "event_subtype",
            "assessment"
        )
    ).lower()

    if subtype not in {
        "incident",
        "activity",
        "indicator",
        "assessment"
    }:
        return "assessment"

    return subtype


def event_layer(item: Dict[str, Any]) -> str:
    """
    Analytical layer for the future Intelligence Matrix.

    This does NOT replace event_subtype or categories.
    It provides an additional analytical grouping.
    """

    subtype = event_subtype(item)

    categories = set(
        item.get(
            "categories",
            []
        )
    )

    if subtype == "assessment":
        return "assessment"

    if subtype == "indicator":
        return "early_warning"

    if subtype in {
        "incident",
        "activity"
    }:
        return "operational"

    if "disinformation" in categories:
        return "information"

    return "assessment"


# ---------------------------------------------------------------------
# DATE FILTERS
# ---------------------------------------------------------------------

def filter_items_by_date(
    items: List[Dict[str, Any]],
    target_date
) -> List[Dict[str, Any]]:

    output = []

    for item in items:

        published_date = parse_date(
            item.get("published_at")
        )

        if published_date is None:
            continue

        if published_date == target_date:
            output.append(item)

    return output


def filter_items_by_window(
    items: List[Dict[str, Any]],
    target_date,
    days: int
) -> List[Dict[str, Any]]:

    start_date = target_date - timedelta(
        days=days - 1
    )

    output = []

    for item in items:

        published_date = parse_date(
            item.get("published_at")
        )

        if published_date is None:
            continue

        if start_date <= published_date <= target_date:
            output.append(item)

    return output


# ---------------------------------------------------------------------
# SUMMARIES
# ---------------------------------------------------------------------

def summarize_items(
    items: List[Dict[str, Any]]
) -> Dict[str, Any]:

    if not items:
        return {
            "event_count": 0,
            "incident_count": 0,
            "activity_count": 0,
            "indicator_count": 0,
            "assessment_count": 0,
            "score_total": 0,
            "average_score": 0,
            "highest_score": 0,
            "overall_level": "low"
        }

    scores = [
        event_score(item)
        for item in items
    ]

    subtype_counts = {
        "incident": 0,
        "activity": 0,
        "indicator": 0,
        "assessment": 0
    }

    for item in items:

        subtype = event_subtype(item)

        subtype_counts[subtype] += 1

    total = sum(scores)

    average = round(
        total / len(items),
        2
    )

    highest = max(scores)

    return {
        "event_count": len(items),

        "incident_count":
            subtype_counts["incident"],

        "activity_count":
            subtype_counts["activity"],

        "indicator_count":
            subtype_counts["indicator"],

        "assessment_count":
            subtype_counts["assessment"],

        "score_total": total,

        "average_score": average,

        "highest_score": highest,

        "overall_level":
            classify_level(average)
    }


def summarize_countries(
    items: List[Dict[str, Any]]
) -> Dict[str, Any]:

    output = {}

    for country in COUNTRIES:

        country_items = []

        for item in items:

            primary_country = item.get(
                "primary_country"
            )

            countries = item.get(
                "countries",
                []
            )

            if (
                primary_country == country
                or country in countries
            ):
                country_items.append(item)

        scores = [
            event_score(item)
            for item in country_items
        ]

        categories = {}

        for item in country_items:

            for category in item.get(
                "categories",
                []
            ):

                categories[category] = (
                    categories.get(
                        category,
                        0
                    )
                    + 1
                )

        total = sum(scores)

        if country_items:
            average = round(
                total / len(country_items),
                2
            )

            highest = max(scores)

        else:
            average = 0
            highest = 0

        output[country] = {
            "country": country,

            "event_count":
                len(country_items),

            "score_total":
                total,

            "average_score":
                average,

            "highest_score":
                highest,

            "level":
                classify_level(
                    average
                ),

            "categories":
                categories
        }

    return output


def summarize_categories(
    items: List[Dict[str, Any]]
) -> Dict[str, Any]:

    output = {}

    for item in items:

        score = event_score(item)

        for category in item.get(
            "categories",
            []
        ):

            if category not in output:

                output[category] = {
                    "category": category,
                    "event_count": 0,
                    "score_total": 0,
                    "average_score": 0,
                    "highest_score": 0
                }

            output[category][
                "event_count"
            ] += 1

            output[category][
                "score_total"
            ] += score

            output[category][
                "highest_score"
            ] = max(
                output[category][
                    "highest_score"
                ],
                score
            )

    for category, data in output.items():

        count = data[
            "event_count"
        ]

        if count > 0:

            data[
                "average_score"
            ] = round(
                data[
                    "score_total"
                ] / count,
                2
            )

    return dict(
        sorted(
            output.items(),
            key=lambda pair:
                pair[1][
                    "score_total"
                ],
            reverse=True
        )
    )


def summarize_layers(
    items: List[Dict[str, Any]]
) -> Dict[str, Any]:

    layers = {
        "information": [],
        "early_warning": [],
        "operational": [],
        "assessment": []
    }

    for item in items:

        layer = event_layer(item)

        layers.setdefault(
            layer,
            []
        ).append(item)

    output = {}

    for layer, layer_items in layers.items():

        summary = summarize_items(
            layer_items
        )

        output[layer] = {
            "event_count":
                summary[
                    "event_count"
                ],

            "score_total":
                summary[
                    "score_total"
                ],

            "average_score":
                summary[
                    "average_score"
                ],

            "highest_score":
                summary[
                    "highest_score"
                ]
        }

    return output


# ---------------------------------------------------------------------
# TOP EVENTS
# ---------------------------------------------------------------------

def top_items(
    items: List[Dict[str, Any]],
    limit: int = 10
) -> List[Dict[str, Any]]:

    sorted_items = sorted(
        items,
        key=event_score,
        reverse=True
    )

    output = []

    for item in sorted_items[:limit]:

        output.append({
            "id":
                item.get("id"),

            "title":
                item.get("title"),

            "url":
                item.get("url"),

            "published_at":
                item.get(
                    "published_at"
                ),

            "source_name":
                item.get(
                    "source_name"
                ),

            "primary_country":
                item.get(
                    "primary_country"
                ),

            "countries":
                item.get(
                    "countries",
                    []
                ),

            "categories":
                item.get(
                    "categories",
                    []
                ),

            "actors":
                item.get(
                    "actors",
                    []
                ),

            "locations":
                item.get(
                    "locations",
                    []
                ),

            "event_subtype":
                event_subtype(
                    item
                ),

            "analytical_layer":
                event_layer(
                    item
                ),

            "confidence":
                item.get(
                    "confidence",
                    "low"
                ),

            "hybrid_threat_score":
                event_score(
                    item
                ),

            "hybrid_threat_level":
                item.get(
                    "hybrid_threat_level",
                    "low"
                )
        })

    return output


# ---------------------------------------------------------------------
# HOTSPOT
# ---------------------------------------------------------------------

def determine_hotspot(
    items: List[Dict[str, Any]]
) -> Dict[str, Any]:

    if not items:
        return {
            "location": None,
            "score": 0,
            "event_count": 0
        }

    location_scores = {}

    location_counts = {}

    for item in items:

        score = event_score(
            item
        )

        for location in item.get(
            "locations",
            []
        ):

            location_scores[
                location
            ] = (
                location_scores.get(
                    location,
                    0
                )
                + score
            )

            location_counts[
                location
            ] = (
                location_counts.get(
                    location,
                    0
                )
                + 1
            )

    if not location_scores:

        country_scores = {}

        country_counts = {}

        for item in items:

            score = event_score(
                item
            )

            country = item.get(
                "primary_country"
            )

            if not country:

                countries = item.get(
                    "countries",
                    []
                )

                if countries:
                    country = countries[0]

            if not country:
                continue

            country_scores[
                country
            ] = (
                country_scores.get(
                    country,
                    0
                )
                + score
            )

            country_counts[
                country
            ] = (
                country_counts.get(
                    country,
                    0
                )
                + 1
            )

        if not country_scores:
            return {
                "location": None,
                "score": 0,
                "event_count": 0
            }

        hotspot = max(
            country_scores,
            key=country_scores.get
        )

        return {
            "location": hotspot,
            "score":
                country_scores[
                    hotspot
                ],
            "event_count":
                country_counts[
                    hotspot
                ]
        }

    hotspot = max(
        location_scores,
        key=location_scores.get
    )

    return {
        "location": hotspot,

        "score":
            location_scores[
                hotspot
            ],

        "event_count":
            location_counts[
                hotspot
            ]
    }


# ---------------------------------------------------------------------
# KEY DRIVER
# ---------------------------------------------------------------------

def determine_key_driver(
    category_summary: Dict[str, Any]
) -> Optional[str]:

    if not category_summary:
        return None

    top_category = max(
        category_summary.items(),
        key=lambda pair:
            pair[1].get(
                "score_total",
                0
            )
    )

    return top_category[0]


# ---------------------------------------------------------------------
# TREND
# ---------------------------------------------------------------------

def calculate_trend(
    history: Dict[str, Any],
    current_daily_average: float
) -> str:

    records = history.get(
        "records",
        []
    )

    if not records:
        return "stable"

    previous_records = [
        record
        for record in records
        if record.get(
            "daily_activity"
        )
    ]

    if not previous_records:
        return "stable"

    previous = previous_records[-1]

    previous_average = (
        previous
        .get(
            "daily_activity",
            {}
        )
        .get(
            "overall",
            {}
        )
        .get(
            "average_score",
            0
        )
    )

    difference = (
        current_daily_average
        - previous_average
    )

    if difference >= 3:
        return "increasing"

    if difference <= -3:
        return "decreasing"

    return "stable"


# ---------------------------------------------------------------------
# DAILY RECORD
# ---------------------------------------------------------------------

def build_daily_record(
    scored_data: Dict[str, Any],
    history: Dict[str, Any],
    target_date,
    rolling_days: int
) -> Dict[str, Any]:

    all_items = scored_data.get(
        "items",
        []
    )

    daily_items = filter_items_by_date(
        items=all_items,
        target_date=target_date
    )

    rolling_items = filter_items_by_window(
        items=all_items,
        target_date=target_date,
        days=rolling_days
    )

    daily_overall = summarize_items(
        daily_items
    )

    rolling_overall = summarize_items(
        rolling_items
    )

    daily_categories = (
        summarize_categories(
            daily_items
        )
    )

    trend = calculate_trend(
        history=history,
        current_daily_average=
            daily_overall[
                "average_score"
            ]
    )

    rolling_start = (
        target_date
        - timedelta(
            days=rolling_days - 1
        )
    )

    return {
        "date":
            target_date.isoformat(),

        "generated_at":
            datetime.now(
                timezone.utc
            ).isoformat(),

        "input_generated_at":
            scored_data.get(
                "generated_at"
            ),

        "daily_activity": {
            "description":
                "Calculated only from events published on this calendar day.",

            "overall":
                daily_overall,

            "countries":
                summarize_countries(
                    daily_items
                ),

            "categories":
                daily_categories,

            "layers":
                summarize_layers(
                    daily_items
                ),

            "hotspot":
                determine_hotspot(
                    daily_items
                ),

            "key_driver":
                determine_key_driver(
                    daily_categories
                ),

            "trend":
                trend,

            "top_items":
                top_items(
                    daily_items,
                    limit=10
                )
        },

        "rolling_threat": {
            "description":
                "Rolling threat environment ending on this calendar day.",

            "window": {
                "days":
                    rolling_days,

                "start_date":
                    rolling_start.isoformat(),

                "end_date":
                    target_date.isoformat()
            },

            "overall":
                rolling_overall,

            "countries":
                summarize_countries(
                    rolling_items
                ),

            "categories":
                summarize_categories(
                    rolling_items
                ),

            "layers":
                summarize_layers(
                    rolling_items
                ),

            "hotspot":
                determine_hotspot(
                    rolling_items
                ),

            "top_items":
                top_items(
                    rolling_items,
                    limit=10
                )
        }
    }


# ---------------------------------------------------------------------
# HISTORY UPDATE
# ---------------------------------------------------------------------

def update_history(
    history: Dict[str, Any],
    daily_record: Dict[str, Any],
    rolling_days: int
) -> Dict[str, Any]:

    now = datetime.now(
        timezone.utc
    ).isoformat()

    if not history:

        history = {
            "project":
                "baltic-hybrid-monitor",

            "region":
                "Baltic states and Poland",

            "created_at":
                now,

            "updated_at":
                now,

            "record_count":
                0,

            "method": {
                "description":
                    "Daily Baltic hybrid-threat history with separate calendar-day activity and rolling threat environment.",

                "daily_activity":
                    "Uses only events whose published_at date matches the record date.",

                "rolling_threat":
                    f"Uses a {rolling_days}-day rolling window ending on the record date.",

                "important":
                    "Daily activity and rolling threat are intentionally stored separately to prevent rolling events from being counted as new incidents on multiple days."
            },

            "records": []
        }

    records = history.get(
        "records",
        []
    )

    target_date = daily_record[
        "date"
    ]

    records = [
        record
        for record in records
        if record.get(
            "date"
        )
        != target_date
    ]

    records.append(
        daily_record
    )

    records = sorted(
        records,
        key=lambda record:
            record.get(
                "date",
                ""
            )
    )

    history[
        "project"
    ] = "baltic-hybrid-monitor"

    history[
        "region"
    ] = "Baltic states and Poland"

    history[
        "updated_at"
    ] = now

    history[
        "record_count"
    ] = len(
        records
    )

    history[
        "records"
    ] = records

    return history


# ---------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------

def main() -> None:

    parser = argparse.ArgumentParser(
        description=(
            "Update Baltic Hybrid Monitor daily history "
            "with separate daily activity and rolling threat data."
        )
    )

    parser.add_argument(
        "--rolling-days",
        type=int,
        default=14,
        help=(
            "Rolling threat window in days. "
            "Default: 14."
        )
    )

    parser.add_argument(
        "--date",
        type=str,
        default=None,
        help=(
            "Optional target date in YYYY-MM-DD format. "
            "Default: current UTC date."
        )
    )

    args = parser.parse_args()

    scored_data = load_json(
        SCORED_INPUT,
        default=None
    )

    if scored_data is None:

        raise FileNotFoundError(
            f"Missing scored input file: "
            f"{SCORED_INPUT}. "
            "Run score_baltic_hybrid_news.py first."
        )

    history = load_json(
        HISTORY_OUTPUT,
        default={}
    )

    if args.date:

        try:
            target_date = (
                datetime.strptime(
                    args.date,
                    "%Y-%m-%d"
                )
                .date()
            )

        except ValueError:

            raise ValueError(
                "--date must use YYYY-MM-DD format."
            )

    else:

        target_date = utc_today()

    daily_record = build_daily_record(
        scored_data=scored_data,
        history=history,
        target_date=target_date,
        rolling_days=args.rolling_days
    )

    updated_history = update_history(
        history=history,
        daily_record=daily_record,
        rolling_days=args.rolling_days
    )

    save_json(
        HISTORY_OUTPUT,
        updated_history
    )

    save_json(
        DOCS_HISTORY_OUTPUT,
        updated_history
    )

    daily_overall = (
        daily_record
        .get(
            "daily_activity",
            {}
        )
        .get(
            "overall",
            {}
        )
    )

    rolling_overall = (
        daily_record
        .get(
            "rolling_threat",
            {}
        )
        .get(
            "overall",
            {}
        )
    )

    print(
        "Baltic Hybrid history updated."
    )

    print(
        f"Date: "
        f"{target_date.isoformat()}"
    )

    print(
        f"Daily events: "
        f"{daily_overall.get('event_count', 0)}"
    )

    print(
        f"Daily average score: "
        f"{daily_overall.get('average_score', 0)}"
    )

    print(
        f"Daily level: "
        f"{daily_overall.get('overall_level', 'low')}"
    )

    print(
        f"Rolling {args.rolling_days}-day events: "
        f"{rolling_overall.get('event_count', 0)}"
    )

    print(
        f"Rolling level: "
        f"{rolling_overall.get('overall_level', 'low')}"
    )

    print(
        f"History records: "
        f"{updated_history.get('record_count', 0)}"
    )

    print(
        f"Saved: {HISTORY_OUTPUT}"
    )

    print(
        f"Saved: {DOCS_HISTORY_OUTPUT}"
    )


if __name__ == "__main__":
    main()
