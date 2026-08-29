#!/usr/bin/env python3

import argparse
import json
import math
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


ROOT = Path(__file__).resolve().parents[1]

SCORED_INPUT = (
    ROOT
    / "data"
    / "baltic_hybrid_scored_news.json"
)

BACKFILL_OUTPUT = (
    ROOT
    / "data"
    / "baltic_daily_snapshot_backfill.json"
)

DOCS_BACKFILL_OUTPUT = (
    ROOT
    / "docs"
    / "data"
    / "baltic_daily_snapshot_backfill.json"
)

BACKFILL_VERSION = "baltic_daily_snapshot_backfill_v1_0"
SNAPSHOT_VERSION = "baltic_daily_snapshot_v1_1_exact_day"
TOP_EVENT_LIMIT = 20


def load_json(
    path: Path,
    default: Optional[Any] = None
) -> Any:

    if not path.exists():
        return default

    with path.open(
        "r",
        encoding="utf-8"
    ) as handle:

        return json.load(
            handle
        )


def save_json(
    path: Path,
    payload: Any
) -> None:

    path.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    with path.open(
        "w",
        encoding="utf-8"
    ) as handle:

        json.dump(
            payload,
            handle,
            ensure_ascii=False,
            indent=2
        )

        handle.write(
            "\n"
        )


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

    except (
        TypeError,
        ValueError
    ):

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
            "Date must use YYYY-MM-DD format."
        ) from exc


def safe_float(
    value: Any,
    default: float = 0.0
) -> float:

    try:

        number = float(
            value
        )

        if not math.isfinite(
            number
        ):

            return default

        return number

    except (
        TypeError,
        ValueError
    ):

        return default


def safe_int(
    value: Any,
    default: int = 0
) -> int:

    try:

        return int(
            value
        )

    except (
        TypeError,
        ValueError
    ):

        return default


def safe_round(
    value: Any,
    digits: int = 2
) -> float:

    return round(
        safe_float(
            value
        ),
        digits
    )


def average_top_scores(
    events: List[Dict[str, Any]],
    limit: int
) -> float:

    scores = sorted(
        [
            safe_float(
                event.get(
                    "hybrid_threat_score",
                    0
                )
            )
            for event in events
        ],
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


def exact_day_events(
    scored: Dict[str, Any],
    target_date: date
) -> List[Dict[str, Any]]:

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

        return []

    selected: List[
        Dict[str, Any]
    ] = []

    for event in events:

        published_at = parse_datetime(
            event.get(
                "published_at"
            )
        )

        if published_at is None:
            continue

        if (
            published_at.date()
            != target_date
        ):
            continue

        selected.append(
            event
        )

    selected.sort(
        key=lambda event: (
            safe_float(
                event.get(
                    "hybrid_threat_score",
                    0
                )
            ),
            event.get(
                "published_at"
            )
            or ""
        ),
        reverse=True
    )

    return selected


def normalize_subtype(
    event: Dict[str, Any]
) -> str:

    subtype = str(
        event.get(
            "event_subtype",
            ""
        )
    ).strip().lower()

    if subtype in {
        "incident",
        "activity",
        "indicator",
        "assessment"
    }:

        return subtype

    return "assessment"


def normalize_scope(
    event: Dict[str, Any]
) -> str:

    scope = str(
        event.get(
            "event_scope",
            "unknown"
        )
    ).strip().lower()

    return (
        scope
        if scope
        else "unknown"
    )


def summarize_group(
    events: List[Dict[str, Any]]
) -> Dict[str, Any]:

    scores = [
        safe_float(
            event.get(
                "hybrid_threat_score",
                0
            )
        )
        for event in events
    ]

    total = sum(
        scores
    )

    return {
        "event_count":
            len(
                events
            ),

        "score_total":
            safe_int(
                round(
                    total
                )
            ),

        "average_score":
            safe_round(
                (
                    total
                    / len(
                        scores
                    )
                )
                if scores
                else 0.0
            ),

        "highest_score":
            safe_int(
                round(
                    max(
                        scores,
                        default=0.0
                    )
                )
            )
    }


def summarize_by_key(
    events: List[Dict[str, Any]],
    key: str
) -> Dict[str, Any]:

    grouped: Dict[
        str,
        List[Dict[str, Any]]
    ] = {}

    for event in events:

        value = event.get(
            key
        )

        if not value:
            continue

        grouped.setdefault(
            str(
                value
            ),
            []
        ).append(
            event
        )

    return {
        name:
            summarize_group(
                group_events
            )
        for name, group_events
        in sorted(
            grouped.items()
        )
    }


def summarize_multivalue(
    events: List[Dict[str, Any]],
    key: str
) -> Dict[str, Any]:

    grouped: Dict[
        str,
        List[Dict[str, Any]]
    ] = {}

    for event in events:

        values = event.get(
            key,
            []
        )

        if isinstance(
            values,
            str
        ):

            values = [
                values
            ]

        if not isinstance(
            values,
            list
        ):

            continue

        for value in values:

            if not value:
                continue

            grouped.setdefault(
                str(
                    value
                ),
                []
            ).append(
                event
            )

    return {
        name:
            summarize_group(
                group_events
            )
        for name, group_events
        in sorted(
            grouped.items()
        )
    }


def build_hotspot(
    events: List[Dict[str, Any]]
) -> Dict[str, Any]:

    grouped: Dict[
        str,
        Dict[str, Any]
    ] = {}

    for event in events:

        locations = event.get(
            "locations",
            []
        )

        if isinstance(
            locations,
            str
        ):

            locations = [
                locations
            ]

        if not isinstance(
            locations,
            list
        ):

            continue

        score = safe_float(
            event.get(
                "hybrid_threat_score",
                0
            )
        )

        for location in locations:

            if not location:
                continue

            key = str(
                location
            )

            grouped.setdefault(
                key,
                {
                    "score": 0.0,
                    "event_count": 0
                }
            )

            grouped[
                key
            ][
                "score"
            ] += score

            grouped[
                key
            ][
                "event_count"
            ] += 1

    if not grouped:

        return {
            "location":
                None,

            "score":
                0,

            "event_count":
                0
        }

    location, values = max(
        grouped.items(),
        key=lambda item: (
            item[1][
                "score"
            ],
            item[1][
                "event_count"
            ],
            item[0]
        )
    )

    return {
        "location":
            location,

        "score":
            safe_int(
                round(
                    values[
                        "score"
                    ]
                )
            ),

        "event_count":
            safe_int(
                values[
                    "event_count"
                ]
            )
    }


def build_key_driver(
    events: List[Dict[str, Any]]
) -> Optional[str]:

    grouped: Dict[
        str,
        float
    ] = {}

    for event in events:

        categories = event.get(
            "categories",
            []
        )

        if isinstance(
            categories,
            str
        ):

            categories = [
                categories
            ]

        if not isinstance(
            categories,
            list
        ):

            continue

        score = safe_float(
            event.get(
                "hybrid_threat_score",
                0
            )
        )

        for category in categories:

            if not category:
                continue

            key = str(
                category
            )

            grouped[
                key
            ] = (
                grouped.get(
                    key,
                    0.0
                )
                + score
            )

    if not grouped:

        return None

    return max(
        grouped.items(),
        key=lambda item: (
            item[1],
            item[0]
        )
    )[0]


def build_dominant_actor(
    events: List[Dict[str, Any]]
) -> Optional[str]:

    grouped: Dict[
        str,
        float
    ] = {}

    for event in events:

        actors = event.get(
            "actors",
            []
        )

        if isinstance(
            actors,
            str
        ):

            actors = [
                actors
            ]

        if not isinstance(
            actors,
            list
        ):

            continue

        score = safe_float(
            event.get(
                "hybrid_threat_score",
                0
            )
        )

        for actor in actors:

            if not actor:
                continue

            key = str(
                actor
            )

            grouped[
                key
            ] = (
                grouped.get(
                    key,
                    0.0
                )
                + score
            )

    if not grouped:

        return None

    return max(
        grouped.items(),
        key=lambda item: (
            item[1],
            item[0]
        )
    )[0]


def compact_event(
    event: Dict[str, Any]
) -> Dict[str, Any]:

    return {
        "event_id":
            event.get(
                "event_id"
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
                "primary_country"
            ),

        "countries":
            event.get(
                "countries",
                []
            ),

        "locations":
            event.get(
                "locations",
                []
            ),

        "categories":
            event.get(
                "categories",
                []
            ),

        "actors":
            event.get(
                "actors",
                []
            ),

        "event_scope":
            event.get(
                "event_scope"
            ),

        "event_subtype":
            normalize_subtype(
                event
            ),

        "hybrid_threat_score":
            safe_int(
                round(
                    safe_float(
                        event.get(
                            "hybrid_threat_score",
                            0
                        )
                    )
                )
            ),

        "confidence_score":
            safe_int(
                round(
                    safe_float(
                        event.get(
                            "confidence_score",
                            0
                        )
                    )
                )
            ),

        "source_count":
            safe_int(
                event.get(
                    "source_count",
                    1
                ),
                default=1
            ),

        "cluster_size":
            safe_int(
                event.get(
                    "cluster_size",
                    1
                ),
                default=1
            )
    }


def build_snapshot(
    scored: Dict[str, Any],
    target_date: date
) -> Dict[str, Any]:

    events = exact_day_events(
        scored,
        target_date
    )

    subtype_groups = {
        "incident":
            [],

        "activity":
            [],

        "indicator":
            [],

        "assessment":
            []
    }

    for event in events:

        subtype_groups[
            normalize_subtype(
                event
            )
        ].append(
            event
        )

    operational_events = (
        subtype_groups[
            "incident"
        ]
        + subtype_groups[
            "activity"
        ]
    )

    early_warning_events = (
        subtype_groups[
            "indicator"
        ]
    )

    operational_index = (
        average_top_scores(
            operational_events,
            5
        )
    )

    early_warning_index = (
        average_top_scores(
            early_warning_events,
            8
        )
    )

    if operational_events:

        threat_index = safe_round(
            (
                0.80
                * operational_index
            )
            + (
                0.20
                * early_warning_index
            )
        )

    else:

        threat_index = safe_round(
            early_warning_index
        )

    overall = summarize_group(
        events
    )

    overall.update(
        {
            "incident_count":
                len(
                    subtype_groups[
                        "incident"
                    ]
                ),

            "activity_count":
                len(
                    subtype_groups[
                        "activity"
                    ]
                ),

            "indicator_count":
                len(
                    subtype_groups[
                        "indicator"
                    ]
                ),

            "assessment_count":
                len(
                    subtype_groups[
                        "assessment"
                    ]
                ),

            "operational_index":
                operational_index,

            "early_warning_index":
                early_warning_index,

            "threat_index":
                threat_index,

            "overall_level":
                level_from_score(
                    threat_index
                )
        }
    )

    subtype_summary = {
        subtype:
            summarize_group(
                group_events
            )
        for subtype, group_events
        in subtype_groups.items()
    }

    scope_groups: Dict[
        str,
        List[Dict[str, Any]]
    ] = {}

    for event in events:

        scope_groups.setdefault(
            normalize_scope(
                event
            ),
            []
        ).append(
            event
        )

    scope_summary = {
        scope:
            summarize_group(
                group_events
            )
        for scope, group_events
        in sorted(
            scope_groups.items()
        )
    }

    compact_events = [
        compact_event(
            event
        )
        for event in events
    ]

    return {
        "project":
            scored.get(
                "project",
                "baltic-hybrid-monitor"
            ),

        "title":
            "Baltic Hybrid Threat Daily Snapshot",

        "region":
            "Baltic states and Poland",

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
                    "Exact UTC calendar-day snapshot built only from "
                    "scored events whose published_at date equals "
                    "snapshot_date."
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
                    "Assessment events remain visible in counts and event lists "
                    "but do not contribute to operational or early-warning indices."
                ),

            "retention_role":
                (
                    "Historical backfill snapshot generated by a separate "
                    "maintenance script."
                )
        },

        "overall_summary":
            overall,

        "country_summary":
            summarize_by_key(
                events,
                "primary_country"
            ),

        "category_summary":
            summarize_multivalue(
                events,
                "categories"
            ),

        "actor_summary":
            summarize_multivalue(
                events,
                "actors"
            ),

        "subtype_summary":
            subtype_summary,

        "scope_summary":
            scope_summary,

        "hotspot":
            build_hotspot(
                events
            ),

        "key_driver":
            build_key_driver(
                events
            ),

        "dominant_actor":
            build_dominant_actor(
                events
            ),

        "top_events":
            compact_events[
                :TOP_EVENT_LIMIT
            ],

        "events":
            compact_events
    }


def daterange(
    start_date: date,
    end_date: date
):

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

        snapshots.append(
            build_snapshot(
                scored,
                target_date
            )
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
                    "a zero-event snapshot because historical source coverage cannot "
                    "be proven from the scored dataset alone."
                ),

            "zero_event_rule":
                (
                    "The backfill script does not infer historical zero-event days."
                ),

            "workflow_role":
                (
                    "Maintenance-only historical reconstruction. "
                    "This script is not part of the normal daily pipeline."
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


def parse_args() -> argparse.Namespace:

    parser = argparse.ArgumentParser(
        description=(
            "Generate strict historical exact-day Baltic "
            "hybrid-threat snapshots for matrix-history backfill."
        )
    )

    parser.add_argument(
        "--start",
        dest="start_date",
        type=parse_date,
        required=True,
        help="Backfill start date in YYYY-MM-DD format."
    )

    parser.add_argument(
        "--end",
        dest="end_date",
        type=parse_date,
        required=True,
        help="Backfill end date in YYYY-MM-DD format."
    )

    return parser.parse_args()


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

    bundle = build_backfill_bundle(
        scored,
        args.start_date,
        args.end_date
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
        "reconstructed_dates"
    ]:

        print(
            "Reconstructed dates: "
            + ", ".join(
                bundle[
                    "reconstructed_dates"
                ]
            )
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


if __name__ == "__main__":
    main()
