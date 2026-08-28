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
# ANALYTICAL LAYER CATEGORIES
# ---------------------------------------------------------------------

OPERATIONAL_CATEGORIES = {
    "sabotage",
    "critical_infrastructure",
    "drone_incident",
    "gps_interference",
    "cyber",
    "espionage",
    "military_provocation",
    "border_pressure",
    "migration_pressure"
}


# ---------------------------------------------------------------------
# BASIC IO
# ---------------------------------------------------------------------

def load_json(
    path: Path,
    default: Any = None
) -> Any:

    if not path.exists():
        return default

    try:
        return json.loads(
            path.read_text(
                encoding="utf-8"
            )
        )

    except json.JSONDecodeError:
        return default


def save_json(
    path: Path,
    payload: Dict[str, Any]
) -> None:

    path.parent.mkdir(
        parents=True,
        exist_ok=True
    )

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

def parse_datetime(
    value: Optional[str]
) -> Optional[datetime]:

    if not value:
        return None

    try:

        dt = datetime.fromisoformat(
            str(value).replace(
                "Z",
                "+00:00"
            )
        )

        if dt.tzinfo is None:
            dt = dt.replace(
                tzinfo=timezone.utc
            )

        return dt.astimezone(
            timezone.utc
        )

    except Exception:
        return None


def parse_date(
    value: Optional[str]
):

    dt = parse_datetime(
        value
    )

    if dt is None:
        return None

    return dt.date()


# ---------------------------------------------------------------------
# THREAT LEVEL CLASSIFICATION
# ---------------------------------------------------------------------

def classify_level(
    score: float
) -> str:

    """
    Unified Baltic Hybrid Threat Score scale.

    LOW      0-19
    GUARDED  20-39
    ELEVATED 40-59
    HIGH     60-79
    CRITICAL 80+
    """

    if score >= 80:
        return "critical"

    if score >= 60:
        return "high"

    if score >= 40:
        return "elevated"

    if score >= 20:
        return "guarded"

    return "low"


# ---------------------------------------------------------------------
# EVENT HELPERS
# ---------------------------------------------------------------------

def event_score(
    item: Dict[str, Any]
) -> int:

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


def event_subtype(
    item: Dict[str, Any]
) -> str:

    subtype = str(
        item.get(
            "event_subtype",
            "assessment"
        )
    ).lower()

    valid = {
        "incident",
        "activity",
        "indicator",
        "assessment"
    }

    if subtype not in valid:
        return "assessment"

    return subtype


def event_layer(
    item: Dict[str, Any]
) -> str:

    """
    Analytical layer classification.

    information:
        Pure information/disinformation activity.

    early_warning:
        Indicators and precursor signals.

    operational:
        Operational incidents or activities.

    assessment:
        Strategic/institutional/analytical background.

    Mixed operational + disinformation events remain operational.
    """

    subtype = event_subtype(
        item
    )

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

    if (
        "disinformation" in categories
        and not (
            categories
            & OPERATIONAL_CATEGORIES
        )
    ):
        return "information"

    if subtype in {
        "incident",
        "activity"
    }:
        return "operational"

    return "assessment"


# ---------------------------------------------------------------------
# DATE FILTERING
# ---------------------------------------------------------------------

def filter_items_by_date(
    items: List[Dict[str, Any]],
    target_date
) -> List[Dict[str, Any]]:

    output = []

    for item in items:

        published_date = parse_date(
            item.get(
                "published_at"
            )
        )

        if published_date is None:
            continue

        if published_date == target_date:

            output.append(
                item
            )

    return output


def filter_items_by_window(
    items: List[Dict[str, Any]],
    target_date,
    days: int
) -> List[Dict[str, Any]]:

    start_date = (
        target_date
        - timedelta(
            days=days - 1
        )
    )

    output = []

    for item in items:

        published_date = parse_date(
            item.get(
                "published_at"
            )
        )

        if published_date is None:
            continue

        if (
            start_date
            <= published_date
            <= target_date
        ):

            output.append(
                item
            )

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
        event_score(
            item
        )
        for item in items
    ]

    subtype_counts = {
        "incident": 0,
        "activity": 0,
        "indicator": 0,
        "assessment": 0
    }

    for item in items:

        subtype = event_subtype(
            item
        )

        subtype_counts[
            subtype
        ] += 1

    total = sum(
        scores
    )

    average = round(
        total / len(items),
        2
    )

    highest = max(
        scores
    )

    return {
        "event_count":
            len(items),

        "incident_count":
            subtype_counts[
                "incident"
            ],

        "activity_count":
            subtype_counts[
                "activity"
            ],

        "indicator_count":
            subtype_counts[
                "indicator"
            ],

        "assessment_count":
            subtype_counts[
                "assessment"
            ],

        "score_total":
            total,

        "average_score":
            average,

        "highest_score":
            highest,

        "overall_level":
            classify_level(
                average
            )
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
                country_items.append(
                    item
                )

        scores = [
            event_score(
                item
            )
            for item in country_items
        ]

        categories = {}

        for item in country_items:

            for category in item.get(
                "categories",
                []
            ):

                categories[
                    category
                ] = (
                    categories.get(
                        category,
                        0
                    )
                    + 1
                )

        total = sum(
            scores
        )

        if country_items:

            average = round(
                total
                / len(
                    country_items
                ),
                2
            )

            highest = max(
                scores
            )

        else:

            average = 0
            highest = 0

        output[
            country
        ] = {
            "country":
                country,

            "event_count":
                len(
                    country_items
                ),

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

        score = event_score(
            item
        )

        for category in item.get(
            "categories",
            []
        ):

            if category not in output:

                output[
                    category
                ] = {
                    "category":
                        category,

                    "event_count":
                        0,

                    "score_total":
                        0,

                    "average_score":
                        0,

                    "highest_score":
                        0
                }

            output[
                category
            ][
                "event_count"
            ] += 1

            output[
                category
            ][
                "score_total"
            ] += score

            output[
                category
            ][
                "highest_score"
            ] = max(
                output[
                    category
                ][
                    "highest_score"
                ],
                score
            )

    for category, data in output.items():

        count = data.get(
            "event_count",
            0
        )

        if count > 0:

            data[
                "average_score"
            ] = round(
                data[
                    "score_total"
                ]
                / count,
                2
            )

    return dict(
        sorted(
            output.items(),
            key=lambda pair:
                pair[1].get(
                    "score_total",
                    0
                ),
            reverse=True
        )
    )


def summarize_layers(
    items: List[Dict[str, Any]]
) -> Dict[str, Any]:

    layer_items = {
        "information": [],
        "early_warning": [],
        "operational": [],
        "assessment": []
    }

    for item in items:

        layer = event_layer(
            item
        )

        layer_items.setdefault(
            layer,
            []
        ).append(
            item
        )

    output = {}

    for (
        layer,
        items_for_layer
    ) in layer_items.items():

        summary = summarize_items(
            items_for_layer
        )

        output[
            layer
        ] = {
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
                ],

            "level":
                summary[
                    "overall_level"
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
                item.get(
                    "id"
                ),

            "title":
                item.get(
                    "title"
                ),

            "url":
                item.get(
                    "url"
                ),

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

    if location_scores:

        hotspot = max(
            location_scores,
            key=location_scores.get
        )

        return {
            "location":
                hotspot,

            "score":
                location_scores[
                    hotspot
                ],

            "event_count":
                location_counts[
                    hotspot
                ]
        }

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

                country = countries[
                    0
                ]

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
        "location":
            hotspot,

        "score":
            country_scores[
                hotspot
            ],

        "event_count":
            country_counts[
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

    category, _ = max(
        category_summary.items(),
        key=lambda pair:
            pair[1].get(
                "score_total",
                0
            )
    )

    return category


# ---------------------------------------------------------------------
# TREND
# ---------------------------------------------------------------------

def calculate_trend(
    previous_average: Optional[float],
    current_average: float
) -> str:

    if previous_average is None:
        return "stable"

    difference = (
        current_average
        - previous_average
    )

    if difference >= 3:
        return "increasing"

    if difference <= -3:
        return "decreasing"

    return "stable"


def get_daily_average_from_record(
    record: Optional[Dict[str, Any]]
) -> Optional[float]:

    if not record:
        return None

    value = (
        record
        .get(
            "daily_activity",
            {}
        )
        .get(
            "overall",
            {}
        )
        .get(
            "average_score"
        )
    )

    if isinstance(
        value,
        (int, float)
    ):
        return float(
            value
        )

    return None


# ---------------------------------------------------------------------
# BUILD ONE HISTORY RECORD
# ---------------------------------------------------------------------

def build_record(
    target_date,
    items: List[Dict[str, Any]],
    rolling_days: int,
    previous_daily_average: Optional[float],
    input_generated_at: Optional[str]
) -> Dict[str, Any]:

    daily_items = filter_items_by_date(
        items=items,
        target_date=target_date
    )

    rolling_items = filter_items_by_window(
        items=items,
        target_date=target_date,
        days=rolling_days
    )

    daily_overall = summarize_items(
        daily_items
    )

    daily_categories = summarize_categories(
        daily_items
    )

    rolling_overall = summarize_items(
        rolling_items
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
            input_generated_at,

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
                calculate_trend(
                    previous_daily_average,
                    daily_overall[
                        "average_score"
                    ]
                ),

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
# BUILD / MERGE HISTORY
# ---------------------------------------------------------------------

def build_history(
    scored_data: Dict[str, Any],
    existing_history: Dict[str, Any],
    days: int,
    rolling_days: int,
    end_date
) -> Dict[str, Any]:

    now = datetime.now(
        timezone.utc
    ).isoformat()

    start_date = (
        end_date
        - timedelta(
            days=days - 1
        )
    )

    items = scored_data.get(
        "items",
        []
    )

    existing_records = existing_history.get(
        "records",
        []
    )

    if not isinstance(
        existing_records,
        list
    ):
        existing_records = []

    # -------------------------------------------------------------
    # KEEP EVERY RECORD OUTSIDE THE BACKFILL RANGE
    #
    # This is the critical retention rule:
    # running a 28-day backfill does NOT delete older history.
    # Only dates inside the requested backfill range are rebuilt.
    # -------------------------------------------------------------

    preserved_records = []

    for record in existing_records:

        record_date = parse_date(
            record.get(
                "date"
            )
        )

        if record_date is None:
            continue

        if not (
            start_date
            <= record_date
            <= end_date
        ):
            preserved_records.append(
                record
            )

    # Build a date -> record map from preserved history.
    record_map = {
        record.get(
            "date"
        ): record
        for record in preserved_records
        if record.get(
            "date"
        )
    }

    rebuilt_records = []

    input_generated_at = scored_data.get(
        "generated_at"
    )

    for index in range(
        days
    ):

        current_date = (
            start_date
            + timedelta(
                days=index
            )
        )

        previous_date = (
            current_date
            - timedelta(
                days=1
            )
        ).isoformat()

        previous_record = None

        # First preference:
        # a record rebuilt earlier in this same backfill run.

        if rebuilt_records:

            candidate = rebuilt_records[
                -1
            ]

            if candidate.get(
                "date"
            ) == previous_date:

                previous_record = candidate

        # Otherwise use an older preserved history record.

        if previous_record is None:

            previous_record = record_map.get(
                previous_date
            )

        previous_daily_average = (
            get_daily_average_from_record(
                previous_record
            )
        )

        new_record = build_record(
            target_date=current_date,
            items=items,
            rolling_days=rolling_days,
            previous_daily_average=
                previous_daily_average,
            input_generated_at=
                input_generated_at
        )

        rebuilt_records.append(
            new_record
        )

    # -------------------------------------------------------------
    # MERGE PRESERVED LONG-TERM HISTORY + REBUILT RANGE
    # -------------------------------------------------------------

    merged_records = (
        preserved_records
        + rebuilt_records
    )

    # Deduplicate by date as an additional safety layer.
    # If duplicates exist, the latest generated record wins.

    deduplicated = {}

    for record in merged_records:

        date_key = record.get(
            "date"
        )

        if not date_key:
            continue

        deduplicated[
            date_key
        ] = record

    final_records = sorted(
        deduplicated.values(),
        key=lambda record:
            record.get(
                "date",
                ""
            )
    )

    created_at = existing_history.get(
        "created_at"
    )

    if not created_at:
        created_at = now

    return {
        "project":
            "baltic-hybrid-monitor",

        "region":
            "Baltic states and Poland",

        "created_at":
            created_at,

        "updated_at":
            now,

        "record_count":
            len(
                final_records
            ),

        "method": {
            "description":
                (
                    "Historical Baltic hybrid-threat backfill "
                    "using the unified daily and rolling threat schema."
                ),

            "warning":
                (
                    "Historical records are reconstructed from currently "
                    "available scored items using published_at dates. "
                    "The backfill is not a complete historical archive "
                    "if older source items are no longer available."
                ),

            "backfill_days":
                days,

            "backfill_start_date":
                start_date.isoformat(),

            "backfill_end_date":
                end_date.isoformat(),

            "rolling_days":
                rolling_days,

            "threat_score_scale": {
                "low":
                    "0-19",

                "guarded":
                    "20-39",

                "elevated":
                    "40-59",

                "high":
                    "60-79",

                "critical":
                    "80+"
            },

            "daily_activity":
                (
                    "Uses only events whose published_at date matches "
                    "the displayed calendar date."
                ),

            "rolling_threat":
                (
                    f"Uses a {rolling_days}-day rolling window ending "
                    "on each displayed calendar date."
                ),

            "analytical_layers": {
                "information":
                    (
                        "Pure information or disinformation activity "
                        "without a concurrent operational threat category."
                    ),

                "early_warning":
                    (
                        "Indicators and precursor signals."
                    ),

                "operational":
                    (
                        "Reported incidents and operational activities, "
                        "including mixed events containing a concrete "
                        "operational threat component."
                    ),

                "assessment":
                    (
                        "Strategic, institutional or analytical background."
                    )
            },

            "trend":
                (
                    "Daily trend compares the current Daily Activity "
                    "average score with the previous calendar day's "
                    "Daily Activity average score."
                ),

            "history_retention":
                (
                    "Unlimited. Historical records outside the requested "
                    "backfill range are preserved."
                ),

            "backfill_update_mode":
                (
                    "Only calendar dates inside the requested backfill "
                    "range are rebuilt. Older and newer historical records "
                    "outside that range remain unchanged."
                ),

            "important":
                (
                    "Daily Activity and Rolling Threat are stored "
                    "separately. The rolling window does not limit "
                    "the lifetime of the historical database."
                )
        },

        "records":
            final_records
    }


# ---------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------

def main() -> None:

    parser = argparse.ArgumentParser(
        description=(
            "Safely rebuild a Baltic Hybrid Monitor historical "
            "backfill range while preserving long-term history."
        )
    )

    parser.add_argument(
        "--days",
        type=int,
        default=28,
        help=(
            "Number of calendar days to rebuild. "
            "Default: 28."
        )
    )

    parser.add_argument(
        "--rolling-days",
        type=int,
        default=14,
        help=(
            "Rolling threat calculation window. "
            "Default: 14."
        )
    )

    parser.add_argument(
        "--end-date",
        type=str,
        default=None,
        help=(
            "Optional end date of the backfill range "
            "in YYYY-MM-DD format. Default: current UTC date."
        )
    )

    args = parser.parse_args()

    if args.days < 1:

        raise ValueError(
            "--days must be at least 1."
        )

    if args.rolling_days < 1:

        raise ValueError(
            "--rolling-days must be at least 1."
        )

    if args.end_date:

        try:

            end_date = datetime.strptime(
                args.end_date,
                "%Y-%m-%d"
            ).date()

        except ValueError:

            raise ValueError(
                "--end-date must use YYYY-MM-DD format."
            )

    else:

        end_date = datetime.now(
            timezone.utc
        ).date()

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

    existing_history = load_json(
        HISTORY_OUTPUT,
        default={}
    )

    old_record_count = len(
        existing_history.get(
            "records",
            []
        )
    )

    history = build_history(
        scored_data=scored_data,
        existing_history=existing_history,
        days=args.days,
        rolling_days=args.rolling_days,
        end_date=end_date
    )

    save_json(
        HISTORY_OUTPUT,
        history
    )

    save_json(
        DOCS_HISTORY_OUTPUT,
        history
    )

    start_date = (
        end_date
        - timedelta(
            days=args.days - 1
        )
    )

    print(
        "Baltic Hybrid Monitor historical backfill completed."
    )

    print(
        f"Backfill range: "
        f"{start_date.isoformat()} "
        f"to {end_date.isoformat()}"
    )

    print(
        f"Backfill days: "
        f"{args.days}"
    )

    print(
        f"Rolling threat window: "
        f"{args.rolling_days} days"
    )

    print(
        f"Previous history records: "
        f"{old_record_count}"
    )

    print(
        f"Final history records: "
        f"{history.get('record_count', 0)}"
    )

    print(
        "Threat scale: "
        "LOW 0-19 | "
        "GUARDED 20-39 | "
        "ELEVATED 40-59 | "
        "HIGH 60-79 | "
        "CRITICAL 80+"
    )

    print(
        "History retention: unlimited"
    )

    print(
        "Records outside the rebuilt backfill range were preserved."
    )

    print(
        f"Saved: {HISTORY_OUTPUT}"
    )

    print(
        f"Saved: {DOCS_HISTORY_OUTPUT}"
    )


if __name__ == "__main__":
    main()
