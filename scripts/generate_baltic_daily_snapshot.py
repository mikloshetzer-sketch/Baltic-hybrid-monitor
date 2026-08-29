import argparse
import json
from collections import Counter, defaultdict
from datetime import date, datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional


ROOT = Path(__file__).resolve().parents[1]

SCORED_INPUT = ROOT / "data" / "baltic_hybrid_scored_news.json"
SNAPSHOT_OUTPUT = ROOT / "data" / "baltic_daily_snapshot.json"
DOCS_SNAPSHOT_OUTPUT = ROOT / "docs" / "data" / "baltic_daily_snapshot.json"

BACKFILL_OUTPUT = ROOT / "data" / "baltic_daily_snapshot_backfill.json"
DOCS_BACKFILL_OUTPUT = ROOT / "docs" / "data" / "baltic_daily_snapshot_backfill.json"

SNAPSHOT_VERSION = "baltic_daily_snapshot_v1_1_backfill_safe"
BACKFILL_VERSION = "baltic_daily_snapshot_backfill_v1_0"
TOP_EVENT_LIMIT = 20

COUNTRY_ORDER = [
    "Estonia",
    "Latvia",
    "Lithuania",
    "Poland",
    "Regional",
]


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
# HELPERS
# ---------------------------------------------------------------------

def safe_int(
    value: Any
) -> int:

    try:
        return int(
            round(
                float(value)
            )
        )

    except (TypeError, ValueError):
        return 0


def safe_round(
    value: Any,
    digits: int = 2
) -> float:

    try:
        return round(
            float(value),
            digits
        )

    except (TypeError, ValueError):
        return 0.0


def parse_datetime(
    value: Optional[str]
) -> Optional[datetime]:

    if not value:
        return None

    try:
        parsed = datetime.fromisoformat(
            str(value).replace(
                "Z",
                "+00:00"
            )
        )

        if parsed.tzinfo is None:
            parsed = parsed.replace(
                tzinfo=timezone.utc
            )

        return parsed.astimezone(
            timezone.utc
        )

    except Exception:
        return None


def parse_date(
    value: str
) -> date:

    try:
        return date.fromisoformat(
            value
        )

    except ValueError as exc:
        raise argparse.ArgumentTypeError(
            f"Invalid date '{value}'. Expected YYYY-MM-DD."
        ) from exc


def level_from_score(
    score: float
) -> str:

    if score >= 80:
        return "critical"

    if score >= 60:
        return "high"

    if score >= 40:
        return "elevated"

    if score >= 20:
        return "guarded"

    return "low"


def event_score(
    event: Dict[str, Any]
) -> int:

    return safe_int(
        event.get(
            "hybrid_threat_score",
            0
        )
    )


def event_subtype(
    event: Dict[str, Any]
) -> str:

    return str(
        event.get(
            "event_subtype",
            "assessment"
        )
        or "assessment"
    )


def event_scope(
    event: Dict[str, Any]
) -> str:

    score_breakdown = event.get(
        "score_breakdown",
        {}
    )

    if isinstance(
        score_breakdown,
        dict
    ):
        scope = score_breakdown.get(
            "geographic_scope"
        )

        if scope:
            return str(
                scope
            )

    scope = event.get(
        "geographic_scope"
    )

    if scope:
        return str(
            scope
        )

    return "unknown"


def unique_strings(
    values: Any
) -> List[str]:

    if not isinstance(
        values,
        list
    ):
        return []

    result = []
    seen = set()

    for value in values:

        text = str(
            value
        ).strip()

        if not text:
            continue

        if text in seen:
            continue

        seen.add(
            text
        )

        result.append(
            text
        )

    return result


# ---------------------------------------------------------------------
# EXACT-DAY FILTER
# ---------------------------------------------------------------------

def filter_events_for_date(
    events: List[Dict[str, Any]],
    target_date: date
) -> List[Dict[str, Any]]:

    exact_day_events = []

    for event in events:

        published_at = parse_datetime(
            event.get(
                "published_at"
            )
        )

        if published_at is None:
            continue

        if published_at.date() == target_date:
            exact_day_events.append(
                event
            )

    return exact_day_events


# ---------------------------------------------------------------------
# THREAT INDEX
# ---------------------------------------------------------------------

def average_top_scores(
    events: List[Dict[str, Any]],
    limit: int
) -> float:

    scores = sorted(
        (
            event_score(
                event
            )
            for event in events
        ),
        reverse=True
    )[:limit]

    if not scores:
        return 0.0

    return safe_round(
        sum(
            scores
        )
        / len(
            scores
        )
    )


def build_threat_indices(
    events: List[Dict[str, Any]]
) -> Dict[str, Any]:

    operational_events = [
        event
        for event in events
        if event_subtype(
            event
        ) in {
            "incident",
            "activity",
        }
    ]

    warning_events = [
        event
        for event in events
        if event_subtype(
            event
        ) == "indicator"
    ]

    operational_index = average_top_scores(
        operational_events,
        5
    )

    early_warning_index = average_top_scores(
        warning_events,
        8
    )

    if operational_events:

        threat_index = safe_round(
            operational_index * 0.8
            + early_warning_index * 0.2
        )

    elif warning_events:

        threat_index = early_warning_index

    else:
        threat_index = 0.0

    return {
        "operational_index":
            operational_index,

        "early_warning_index":
            early_warning_index,

        "threat_index":
            threat_index,

        "threat_level":
            level_from_score(
                threat_index
            )
    }


# ---------------------------------------------------------------------
# SUMMARY BUILDERS
# ---------------------------------------------------------------------

def build_overall_summary(
    events: List[Dict[str, Any]]
) -> Dict[str, Any]:

    subtype_counts = Counter(
        event_subtype(
            event
        )
        for event in events
    )

    non_assessment_events = [
        event
        for event in events
        if event_subtype(
            event
        ) != "assessment"
    ]

    score_total = sum(
        event_score(
            event
        )
        for event in events
    )

    highest_score = max(
        (
            event_score(
                event
            )
            for event in events
        ),
        default=0
    )

    if non_assessment_events:

        average_score = safe_round(
            sum(
                event_score(
                    event
                )
                for event in non_assessment_events
            )
            / len(
                non_assessment_events
            )
        )

    else:
        average_score = 0.0

    indices = build_threat_indices(
        events
    )

    return {
        "event_count":
            len(
                events
            ),

        "incident_count":
            subtype_counts.get(
                "incident",
                0
            ),

        "activity_count":
            subtype_counts.get(
                "activity",
                0
            ),

        "indicator_count":
            subtype_counts.get(
                "indicator",
                0
            ),

        "assessment_count":
            subtype_counts.get(
                "assessment",
                0
            ),

        "score_total":
            score_total,

        "average_score":
            average_score,

        "highest_score":
            highest_score,

        "operational_index":
            indices[
                "operational_index"
            ],

        "early_warning_index":
            indices[
                "early_warning_index"
            ],

        "threat_index":
            indices[
                "threat_index"
            ],

        "overall_level":
            indices[
                "threat_level"
            ]
    }


def build_country_summary(
    events: List[Dict[str, Any]]
) -> Dict[str, Any]:

    grouped = defaultdict(
        list
    )

    for event in events:

        country = str(
            event.get(
                "primary_country",
                "Regional"
            )
            or "Regional"
        )

        grouped[
            country
        ].append(
            event
        )

    result = {}

    ordered_countries = (
        COUNTRY_ORDER
        + sorted(
            country
            for country in grouped
            if country not in COUNTRY_ORDER
        )
    )

    for country in ordered_countries:

        country_events = grouped.get(
            country,
            []
        )

        if not country_events:
            continue

        summary = build_overall_summary(
            country_events
        )

        category_counts = Counter()
        actor_counts = Counter()

        for event in country_events:

            category_counts.update(
                unique_strings(
                    event.get(
                        "categories",
                        []
                    )
                )
            )

            actor_counts.update(
                unique_strings(
                    event.get(
                        "actors",
                        []
                    )
                )
            )

        result[
            country
        ] = {
            "country":
                country,

            **summary,

            "categories":
                dict(
                    category_counts.most_common()
                ),

            "actors":
                dict(
                    actor_counts.most_common()
                )
        }

    return result


def build_dimension_summary(
    events: List[Dict[str, Any]],
    field: str
) -> Dict[str, Any]:

    grouped = defaultdict(
        list
    )

    for event in events:

        values = unique_strings(
            event.get(
                field,
                []
            )
        )

        for value in values:
            grouped[
                value
            ].append(
                event
            )

    result = {}

    for value, grouped_events in sorted(
        grouped.items(),
        key=lambda item: (
            -sum(
                event_score(
                    event
                )
                for event in item[
                    1
                ]
            ),
            item[
                0
            ]
        )
    ):

        scores = [
            event_score(
                event
            )
            for event in grouped_events
        ]

        result[
            value
        ] = {
            "event_count":
                len(
                    grouped_events
                ),

            "score_total":
                sum(
                    scores
                ),

            "average_score":
                safe_round(
                    sum(
                        scores
                    )
                    / len(
                        scores
                    )
                )
                if scores
                else 0.0,

            "highest_score":
                max(
                    scores,
                    default=0
                )
        }

    return result


def build_subtype_summary(
    events: List[Dict[str, Any]]
) -> Dict[str, Any]:

    result = {}

    for subtype in [
        "incident",
        "activity",
        "indicator",
        "assessment",
    ]:

        subtype_events = [
            event
            for event in events
            if event_subtype(
                event
            ) == subtype
        ]

        scores = [
            event_score(
                event
            )
            for event in subtype_events
        ]

        result[
            subtype
        ] = {
            "event_count":
                len(
                    subtype_events
                ),

            "score_total":
                sum(
                    scores
                ),

            "average_score":
                safe_round(
                    sum(
                        scores
                    )
                    / len(
                        scores
                    )
                )
                if scores
                else 0.0,

            "highest_score":
                max(
                    scores,
                    default=0
                )
        }

    return result


def build_scope_summary(
    events: List[Dict[str, Any]]
) -> Dict[str, Any]:

    grouped = defaultdict(
        list
    )

    for event in events:

        grouped[
            event_scope(
                event
            )
        ].append(
            event
        )

    result = {}

    for scope, scope_events in sorted(
        grouped.items()
    ):

        scores = [
            event_score(
                event
            )
            for event in scope_events
        ]

        result[
            scope
        ] = {
            "event_count":
                len(
                    scope_events
                ),

            "score_total":
                sum(
                    scores
                ),

            "average_score":
                safe_round(
                    sum(
                        scores
                    )
                    / len(
                        scores
                    )
                )
                if scores
                else 0.0,

            "highest_score":
                max(
                    scores,
                    default=0
                )
        }

    return result


# ---------------------------------------------------------------------
# DRIVER / HOTSPOT
# ---------------------------------------------------------------------

def build_hotspot(
    events: List[Dict[str, Any]]
) -> Dict[str, Any]:

    location_scores = defaultdict(
        int
    )

    location_counts = Counter()

    for event in events:

        score = event_score(
            event
        )

        locations = unique_strings(
            event.get(
                "locations",
                []
            )
        )

        if not locations:

            primary_country = str(
                event.get(
                    "primary_country",
                    "Regional"
                )
                or "Regional"
            )

            locations = [
                primary_country
            ]

        for location in locations:

            location_scores[
                location
            ] += score

            location_counts[
                location
            ] += 1

    if not location_scores:

        return {
            "location":
                None,

            "score":
                0,

            "event_count":
                0
        }

    location = max(
        location_scores,
        key=lambda item: (
            location_scores[
                item
            ],
            location_counts[
                item
            ],
            item
        )
    )

    return {
        "location":
            location,

        "score":
            location_scores[
                location
            ],

        "event_count":
            location_counts[
                location
            ]
    }


def build_key_driver(
    events: List[Dict[str, Any]]
) -> Optional[str]:

    category_scores = defaultdict(
        int
    )

    category_counts = Counter()

    for event in events:

        score = event_score(
            event
        )

        for category in unique_strings(
            event.get(
                "categories",
                []
            )
        ):

            category_scores[
                category
            ] += score

            category_counts[
                category
            ] += 1

    if not category_scores:
        return None

    return max(
        category_scores,
        key=lambda item: (
            category_scores[
                item
            ],
            category_counts[
                item
            ],
            item
        )
    )


def build_dominant_actor(
    events: List[Dict[str, Any]]
) -> Optional[str]:

    actor_scores = defaultdict(
        int
    )

    actor_counts = Counter()

    for event in events:

        score = event_score(
            event
        )

        for actor in unique_strings(
            event.get(
                "actors",
                []
            )
        ):

            actor_scores[
                actor
            ] += score

            actor_counts[
                actor
            ] += 1

    if not actor_scores:
        return None

    return max(
        actor_scores,
        key=lambda item: (
            actor_scores[
                item
            ],
            actor_counts[
                item
            ],
            item
        )
    )


# ---------------------------------------------------------------------
# EVENT OUTPUT
# ---------------------------------------------------------------------

def compact_event(
    event: Dict[str, Any]
) -> Dict[str, Any]:

    return {
        "event_id":
            event.get(
                "event_id",
                event.get(
                    "id"
                )
            ),

        "title":
            event.get(
                "title"
            ),

        "url":
            event.get(
                "url"
            ),

        "published_at":
            event.get(
                "published_at"
            ),

        "primary_country":
            event.get(
                "primary_country",
                "Regional"
            ),

        "countries":
            unique_strings(
                event.get(
                    "countries",
                    []
                )
            )[:5],

        "categories":
            unique_strings(
                event.get(
                    "categories",
                    []
                )
            )[:5],

        "actors":
            unique_strings(
                event.get(
                    "actors",
                    []
                )
            )[:5],

        "locations":
            unique_strings(
                event.get(
                    "locations",
                    []
                )
            )[:5],

        "event_type":
            event.get(
                "event_type",
                "background"
            ),

        "event_subtype":
            event_subtype(
                event
            ),

        "analysis_layer":
            event.get(
                "analysis_layer"
            ),

        "geographic_scope":
            event_scope(
                event
            ),

        "source_count":
            safe_int(
                event.get(
                    "source_count",
                    0
                )
            ),

        "confidence":
            event.get(
                "confidence",
                "low"
            ),

        "confidence_score":
            safe_int(
                event.get(
                    "confidence_score",
                    0
                )
            ),

        "hybrid_threat_score":
            event_score(
                event
            ),

        "hybrid_threat_level":
            event.get(
                "hybrid_threat_level",
                level_from_score(
                    event_score(
                        event
                    )
                )
            ),

        "source_names":
            unique_strings(
                event.get(
                    "source_names",
                    []
                )
            )[:5],

        "related_item_count":
            safe_int(
                event.get(
                    "related_item_count",
                    0
                )
            )
    }


def build_top_events(
    events: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:

    compact = [
        compact_event(
            event
        )
        for event in events
    ]

    compact = sorted(
        compact,
        key=lambda event: (
            event.get(
                "hybrid_threat_score",
                0
            ),
            event.get(
                "confidence_score",
                0
            ),
            event.get(
                "published_at",
                ""
            )
        ),
        reverse=True
    )

    return compact[
        :TOP_EVENT_LIMIT
    ]


# ---------------------------------------------------------------------
# SNAPSHOT
# ---------------------------------------------------------------------

def build_snapshot(
    scored: Dict[str, Any],
    target_date: date
) -> Dict[str, Any]:

    all_events = scored.get(
        "events",
        scored.get(
            "items",
            []
        )
    )

    if not isinstance(
        all_events,
        list
    ):
        all_events = []

    daily_events = filter_events_for_date(
        all_events,
        target_date
    )

    overall_summary = build_overall_summary(
        daily_events
    )

    category_summary = build_dimension_summary(
        daily_events,
        "categories"
    )

    actor_summary = build_dimension_summary(
        daily_events,
        "actors"
    )

    payload = {
        "project":
            scored.get(
                "project",
                "baltic-hybrid-monitor"
            ),

        "title":
            "Baltic Hybrid Threat Daily Snapshot",

        "region":
            scored.get(
                "region",
                "Baltic states and Poland"
            ),

        "generated_at":
            datetime.now(
                timezone.utc
            ).isoformat(),

        "snapshot_date":
            target_date.isoformat(),

        "snapshot_version":
            SNAPSHOT_VERSION,

        "score_engine_version":
            scored.get(
                "engine_version",
                scored.get(
                    "score_engine_version"
                )
            ),

        "source_generated_at":
            scored.get(
                "generated_at"
            ),

        "method": {
            "description":
                (
                    "Exact UTC calendar-day snapshot built only from scored "
                    "events whose published_at date equals snapshot_date."
                ),

            "time_basis":
                "UTC calendar day",

            "rolling_window_used":
                False,

            "rolling_window_days":
                0,

            "threat_index_method":
                (
                    "Operational Index = average of top 5 incident/activity "
                    "scores. Early Warning Index = average of top 8 indicator "
                    "scores. Daily Threat Index = 80% operational + 20% early "
                    "warning when operational events exist; otherwise the "
                    "early-warning index is used."
                ),

            "assessment_handling":
                (
                    "Assessment events remain visible in counts and event "
                    "lists but do not contribute to operational or early-warning "
                    "indices."
                ),

            "retention_role":
                (
                    "This file is the current exact-day snapshot. Long-term "
                    "retention belongs to the history and future intelligence "
                    "matrix history datasets."
                )
        },

        "overall_summary":
            overall_summary,

        "country_summary":
            build_country_summary(
                daily_events
            ),

        "category_summary":
            category_summary,

        "actor_summary":
            actor_summary,

        "subtype_summary":
            build_subtype_summary(
                daily_events
            ),

        "scope_summary":
            build_scope_summary(
                daily_events
            ),

        "hotspot":
            build_hotspot(
                daily_events
            ),

        "key_driver":
            build_key_driver(
                daily_events
            ),

        "dominant_actor":
            build_dominant_actor(
                daily_events
            ),

        "top_events":
            build_top_events(
                daily_events
            ),

        "events":
            [
                compact_event(
                    event
                )
                for event in sorted(
                    daily_events,
                    key=lambda item:
                        item.get(
                            "published_at",
                            ""
                        ),
                    reverse=True
                )
            ]
    }

    return payload


# ---------------------------------------------------------------------
# HISTORICAL BACKFILL
# ---------------------------------------------------------------------

def daterange(
    start_date: date,
    end_date: date
) -> List[date]:

    current = start_date

    while current <= end_date:

        yield current

        current += timedelta(
            days=1
        )


def observed_event_dates(
    scored: Dict[str, Any]
) -> set:

    events = scored.get(
        "events",
        scored.get(
            "items",
            []
        )
    )

    if not isinstance(
        events,
        list
    ):
        return set()

    dates = set()

    for event in events:

        published_at = parse_datetime(
            event.get(
                "published_at"
            )
        )

        if published_at is None:
            continue

        dates.add(
            published_at.date()
        )

    return dates


def build_backfill_bundle(
    scored: Dict[str, Any],
    start_date: date,
    end_date: date
) -> Dict[str, Any]:

    if end_date < start_date:

        raise ValueError(
            "Backfill end date must be on or after start date."
        )

    observed_dates = observed_event_dates(
        scored
    )

    snapshots = []
    missing_dates = []

    for target_date in daterange(
        start_date,
        end_date
    ):

        if target_date not in observed_dates:

            missing_dates.append(
                target_date.isoformat()
            )

            continue

        snapshot = build_snapshot(
            scored,
            target_date
        )

        snapshots.append(
            snapshot
        )

    requested_days = (
        end_date
        - start_date
    ).days + 1

    return {
        "project":
            scored.get(
                "project",
                "baltic-hybrid-monitor"
            ),

        "generated_at":
            datetime.now(
                timezone.utc
            ).isoformat(),

        "backfill_version":
            BACKFILL_VERSION,

        "snapshot_version":
            SNAPSHOT_VERSION,

        "score_engine_version":
            scored.get(
                "engine_version",
                scored.get(
                    "score_engine_version"
                )
            ),

        "source_generated_at":
            scored.get(
                "generated_at"
            ),

        "range": {
            "start_date":
                start_date.isoformat(),

            "end_date":
                end_date.isoformat(),

            "requested_days":
                requested_days
        },

        "coverage": {
            "reconstructable_days":
                len(
                    snapshots
                ),

            "unverified_missing_days":
                len(
                    missing_dates
                ),

            "complete":
                len(
                    missing_dates
                ) == 0
        },

        "method": {
            "mode":
                "strict_historical_backfill",

            "time_basis":
                "UTC calendar day",

            "rolling_window_used":
                False,

            "reconstruction_rule":
                (
                    "A historical date is reconstructed only when the scored "
                    "dataset contains at least one event with a valid published_at "
                    "timestamp on that UTC calendar date."
                ),

            "missing_day_rule":
                (
                    "A historical date with no scored event is not converted into "
                    "a zero-event snapshot because source coverage cannot be proven "
                    "from this dataset alone. It remains unverified/missing."
                ),

            "zero_event_rule":
                (
                    "Zero-event snapshots remain valid in normal current/exact-date "
                    "generation. Strict historical backfill does not infer historical "
                    "zero-event days without independent coverage evidence."
                ),

            "history_role":
                (
                    "This bundle is an intermediate backfill source. It must be "
                    "merged into intelligence-matrix history without replacing "
                    "unverified missing dates with zero values."
                )
        },

        "reconstructed_dates":
            [
                snapshot[
                    "snapshot_date"
                ]
                for snapshot in snapshots
            ],

        "unverified_missing_dates":
            missing_dates,

        "snapshots":
            snapshots
    }


# ---------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------

def parse_args() -> argparse.Namespace:

    parser = argparse.ArgumentParser(
        description=(
            "Generate an exact UTC calendar-day Baltic hybrid-threat snapshot "
            "or a strict historical backfill bundle."
        )
    )

    parser.add_argument(
        "--date",
        dest="target_date",
        type=parse_date,
        default=None,
        help=(
            "Snapshot date in YYYY-MM-DD format. "
            "Default: current UTC date."
        )
    )

    parser.add_argument(
        "--backfill-start",
        dest="backfill_start",
        type=parse_date,
        default=None,
        help=(
            "Strict historical backfill start date in YYYY-MM-DD format. "
            "Must be used together with --backfill-end."
        )
    )

    parser.add_argument(
        "--backfill-end",
        dest="backfill_end",
        type=parse_date,
        default=None,
        help=(
            "Strict historical backfill end date in YYYY-MM-DD format. "
            "Must be used together with --backfill-start."
        )
    )

    args = parser.parse_args()

    if (
        args.backfill_start is None
    ) != (
        args.backfill_end is None
    ):

        parser.error(
            "--backfill-start and --backfill-end must be used together."
        )

    if (
        args.backfill_start is not None
        and args.target_date is not None
    ):

        parser.error(
            "--date cannot be combined with historical backfill mode."
        )

    return args


# ---------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------

def main() -> None:

    args = parse_args()

    scored = load_json(
        SCORED_INPUT,
        default=None
    )

    if scored is None:

        raise FileNotFoundError(
            f"Missing scored input file: {SCORED_INPUT}. "
            "Run scripts/score_baltic_hybrid_news.py first."
        )

    if args.backfill_start is not None:

        bundle = build_backfill_bundle(
            scored,
            args.backfill_start,
            args.backfill_end
        )

        save_json(
            BACKFILL_OUTPUT,
            bundle
        )

        save_json(
            DOCS_BACKFILL_OUTPUT,
            bundle
        )

        coverage = bundle[
            "coverage"
        ]

        print(
            f"Backfill version: {BACKFILL_VERSION}"
        )

        print(
            "Backfill range: "
            f"{bundle['range']['start_date']} -> "
            f"{bundle['range']['end_date']} UTC"
        )

        print(
            "Reconstructable days: "
            f"{coverage['reconstructable_days']}"
        )

        print(
            "Unverified/missing days: "
            f"{coverage['unverified_missing_days']}"
        )

        if bundle[
            "unverified_missing_dates"
        ]:

            print(
                "Unverified dates: "
                + ", ".join(
                    bundle[
                        "unverified_missing_dates"
                    ]
                )
            )

        print(
            f"Saved backfill bundle to: {BACKFILL_OUTPUT}"
        )

        print(
            f"Saved public backfill bundle to: {DOCS_BACKFILL_OUTPUT}"
        )

        return

    target_date = (
        args.target_date
        if args.target_date is not None
        else datetime.now(
            timezone.utc
        ).date()
    )

    snapshot = build_snapshot(
        scored,
        target_date
    )

    save_json(
        SNAPSHOT_OUTPUT,
        snapshot
    )

    save_json(
        DOCS_SNAPSHOT_OUTPUT,
        snapshot
    )

    summary = snapshot[
        "overall_summary"
    ]

    print(
        f"Daily snapshot version: {SNAPSHOT_VERSION}"
    )

    print(
        f"Snapshot date: {snapshot['snapshot_date']} UTC"
    )

    print(
        f"Events: {summary['event_count']}"
    )

    print(
        f"Incidents: {summary['incident_count']}"
    )

    print(
        f"Activities: {summary['activity_count']}"
    )

    print(
        f"Indicators: {summary['indicator_count']}"
    )

    print(
        f"Assessments: {summary['assessment_count']}"
    )

    print(
        f"Operational index: {summary['operational_index']}"
    )

    print(
        f"Early warning index: {summary['early_warning_index']}"
    )

    print(
        f"Daily threat index: {summary['threat_index']}"
    )

    print(
        f"Daily threat level: {summary['overall_level']}"
    )

    print(
        f"Saved snapshot to: {SNAPSHOT_OUTPUT}"
    )

    print(
        f"Saved public snapshot to: {DOCS_SNAPSHOT_OUTPUT}"
    )


if __name__ == "__main__":
    main()
