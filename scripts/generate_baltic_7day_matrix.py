import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


ROOT = Path(__file__).resolve().parents[1]

HISTORY_INPUT = (
    ROOT
    / "data"
    / "baltic_intelligence_matrix_history.json"
)

MATRIX_OUTPUT = (
    ROOT
    / "data"
    / "baltic_7day_matrix.json"
)

DOCS_MATRIX_OUTPUT = (
    ROOT
    / "docs"
    / "data"
    / "baltic_7day_matrix.json"
)

MATRIX_VERSION = "baltic_7day_matrix_v1_0"
WINDOW_DAYS = 7


# ---------------------------------------------------------------------
# BASIC IO
# ---------------------------------------------------------------------

def load_json(
    path: Path
) -> Dict[str, Any]:

    if not path.exists():

        raise FileNotFoundError(
            f"Missing input file: {path}"
        )

    return json.loads(
        path.read_text(
            encoding="utf-8"
        )
    )


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
# DATE HELPERS
# ---------------------------------------------------------------------

def parse_date(
    value: Any
) -> datetime:

    if not isinstance(
        value,
        str
    ):

        raise ValueError(
            "Date must be a YYYY-MM-DD string."
        )

    try:

        return datetime.strptime(
            value,
            "%Y-%m-%d"
        )

    except ValueError as exc:

        raise ValueError(
            f"Invalid date: {value}"
        ) from exc


def format_date(
    value: datetime
) -> str:

    return value.strftime(
        "%Y-%m-%d"
    )


def build_window_dates(
    end_date: str,
    days: int = WINDOW_DAYS
) -> List[str]:

    if days <= 0:

        raise ValueError(
            "Window length must be greater than zero."
        )

    end_dt = parse_date(
        end_date
    )

    start_dt = (
        end_dt
        - timedelta(
            days=days - 1
        )
    )

    return [
        format_date(
            start_dt
            + timedelta(
                days=offset
            )
        )
        for offset in range(
            days
        )
    ]


# ---------------------------------------------------------------------
# VALIDATION
# ---------------------------------------------------------------------

def validate_history(
    history: Dict[str, Any]
) -> List[Dict[str, Any]]:

    snapshots = history.get(
        "snapshots"
    )

    if not isinstance(
        snapshots,
        list
    ):

        raise ValueError(
            "History snapshots field must be a list."
        )

    seen_dates = set()

    for snapshot in snapshots:

        if not isinstance(
            snapshot,
            dict
        ):

            raise ValueError(
                "Every history snapshot must be an object."
            )

        snapshot_date = snapshot.get(
            "snapshot_date"
        )

        parse_date(
            snapshot_date
        )

        if snapshot_date in seen_dates:

            raise ValueError(
                "Duplicate snapshot_date detected in history: "
                f"{snapshot_date}"
            )

        seen_dates.add(
            snapshot_date
        )

        method = snapshot.get(
            "method",
            {}
        )

        if not isinstance(
            method,
            dict
        ):

            raise ValueError(
                f"Snapshot {snapshot_date} method must be an object."
            )

        if method.get(
            "rolling_window_used"
        ) is True:

            raise ValueError(
                f"Snapshot {snapshot_date} is not exact-day data."
            )

        rolling_days = method.get(
            "rolling_window_days"
        )

        if rolling_days not in {
            None,
            0
        }:

            raise ValueError(
                f"Snapshot {snapshot_date} has "
                f"rolling_window_days={rolling_days}."
            )

        overall = snapshot.get(
            "overall_summary"
        )

        if not isinstance(
            overall,
            dict
        ):

            raise ValueError(
                f"Snapshot {snapshot_date} "
                "is missing overall_summary."
            )

    return snapshots


# ---------------------------------------------------------------------
# SAFE VALUE HELPERS
# ---------------------------------------------------------------------

def number_or_zero(
    value: Any
) -> float:

    if isinstance(
        value,
        bool
    ):

        return 0.0

    if isinstance(
        value,
        (
            int,
            float
        )
    ):

        return float(
            value
        )

    try:

        return float(
            value
        )

    except (
        TypeError,
        ValueError
    ):

        return 0.0


def int_or_zero(
    value: Any
) -> int:

    return int(
        round(
            number_or_zero(
                value
            )
        )
    )


def round_score(
    value: Any
) -> float:

    return round(
        number_or_zero(
            value
        ),
        2
    )


def merge_numeric_summary(
    target: Dict[str, float],
    source: Any
) -> None:

    if not isinstance(
        source,
        dict
    ):

        return

    for key, value in source.items():

        target[
            str(
                key
            )
        ] = (
            target.get(
                str(
                    key
                ),
                0.0
            )
            + number_or_zero(
                value
            )
        )


# ---------------------------------------------------------------------
# DAILY ROW
# ---------------------------------------------------------------------

def build_available_day(
    snapshot: Dict[str, Any]
) -> Dict[str, Any]:

    overall = snapshot.get(
        "overall_summary",
        {}
    )

    return {
        "date":
            snapshot.get(
                "snapshot_date"
            ),

        "status":
            "available",

        "snapshot_generated_at":
            snapshot.get(
                "generated_at"
            ),

        "snapshot_version":
            snapshot.get(
                "snapshot_version"
            ),

        "score_engine_version":
            snapshot.get(
                "score_engine_version"
            ),

        "event_count":
            int_or_zero(
                overall.get(
                    "event_count"
                )
            ),

        "incident_count":
            int_or_zero(
                overall.get(
                    "incident_count"
                )
            ),

        "activity_count":
            int_or_zero(
                overall.get(
                    "activity_count"
                )
            ),

        "indicator_count":
            int_or_zero(
                overall.get(
                    "indicator_count"
                )
            ),

        "assessment_count":
            int_or_zero(
                overall.get(
                    "assessment_count"
                )
            ),

        "score_total":
            round_score(
                overall.get(
                    "score_total"
                )
            ),

        "average_score":
            round_score(
                overall.get(
                    "average_score"
                )
            ),

        "highest_score":
            round_score(
                overall.get(
                    "highest_score"
                )
            ),

        "operational_index":
            round_score(
                overall.get(
                    "operational_index"
                )
            ),

        "early_warning_index":
            round_score(
                overall.get(
                    "early_warning_index"
                )
            ),

        "threat_index":
            round_score(
                overall.get(
                    "threat_index"
                )
            ),

        "overall_level":
            overall.get(
                "overall_level"
            ),

        "country_summary":
            snapshot.get(
                "country_summary",
                {}
            ),

        "category_summary":
            snapshot.get(
                "category_summary",
                {}
            ),

        "actor_summary":
            snapshot.get(
                "actor_summary",
                {}
            ),

        "subtype_summary":
            snapshot.get(
                "subtype_summary",
                {}
            ),

        "scope_summary":
            snapshot.get(
                "scope_summary",
                {}
            ),

        "hotspot":
            snapshot.get(
                "hotspot"
            ),

        "key_driver":
            snapshot.get(
                "key_driver"
            ),

        "dominant_actor":
            snapshot.get(
                "dominant_actor"
            ),

        "top_events":
            snapshot.get(
                "top_events",
                []
            ),

        "events":
            snapshot.get(
                "events",
                []
            )
    }


def build_missing_day(
    date_value: str
) -> Dict[str, Any]:

    return {
        "date":
            date_value,

        "status":
            "missing",

        "snapshot_generated_at":
            None,

        "snapshot_version":
            None,

        "score_engine_version":
            None,

        "event_count":
            None,

        "incident_count":
            None,

        "activity_count":
            None,

        "indicator_count":
            None,

        "assessment_count":
            None,

        "score_total":
            None,

        "average_score":
            None,

        "highest_score":
            None,

        "operational_index":
            None,

        "early_warning_index":
            None,

        "threat_index":
            None,

        "overall_level":
            None,

        "country_summary":
            None,

        "category_summary":
            None,

        "actor_summary":
            None,

        "subtype_summary":
            None,

        "scope_summary":
            None,

        "hotspot":
            None,

        "key_driver":
            None,

        "dominant_actor":
            None,

        "top_events":
            [],

        "events":
            []
    }


# ---------------------------------------------------------------------
# AGGREGATION
# ---------------------------------------------------------------------

def classify_threat_level(
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


def aggregate_window(
    available_snapshots: List[Dict[str, Any]],
    window_dates: List[str]
) -> Dict[str, Any]:

    available_days = len(
        available_snapshots
    )

    missing_days = (
        len(
            window_dates
        )
        - available_days
    )

    event_count = 0
    incident_count = 0
    activity_count = 0
    indicator_count = 0
    assessment_count = 0

    threat_values: List[float] = []
    operational_values: List[float] = []
    early_warning_values: List[float] = []

    country_totals: Dict[str, float] = {}
    category_totals: Dict[str, float] = {}
    actor_totals: Dict[str, float] = {}

    all_events: List[Dict[str, Any]] = []

    for snapshot in available_snapshots:

        overall = snapshot.get(
            "overall_summary",
            {}
        )

        event_count += int_or_zero(
            overall.get(
                "event_count"
            )
        )

        incident_count += int_or_zero(
            overall.get(
                "incident_count"
            )
        )

        activity_count += int_or_zero(
            overall.get(
                "activity_count"
            )
        )

        indicator_count += int_or_zero(
            overall.get(
                "indicator_count"
            )
        )

        assessment_count += int_or_zero(
            overall.get(
                "assessment_count"
            )
        )

        threat_values.append(
            number_or_zero(
                overall.get(
                    "threat_index"
                )
            )
        )

        operational_values.append(
            number_or_zero(
                overall.get(
                    "operational_index"
                )
            )
        )

        early_warning_values.append(
            number_or_zero(
                overall.get(
                    "early_warning_index"
                )
            )
        )

        merge_numeric_summary(
            country_totals,
            snapshot.get(
                "country_summary"
            )
        )

        merge_numeric_summary(
            category_totals,
            snapshot.get(
                "category_summary"
            )
        )

        merge_numeric_summary(
            actor_totals,
            snapshot.get(
                "actor_summary"
            )
        )

        events = snapshot.get(
            "events",
            []
        )

        if isinstance(
            events,
            list
        ):

            for event in events:

                if isinstance(
                    event,
                    dict
                ):

                    event_copy = dict(
                        event
                    )

                    event_copy[
                        "matrix_snapshot_date"
                    ] = snapshot.get(
                        "snapshot_date"
                    )

                    all_events.append(
                        event_copy
                    )

    average_threat = (
        sum(
            threat_values
        )
        / available_days
        if available_days
        else 0.0
    )

    average_operational = (
        sum(
            operational_values
        )
        / available_days
        if available_days
        else 0.0
    )

    average_early_warning = (
        sum(
            early_warning_values
        )
        / available_days
        if available_days
        else 0.0
    )

    highest_threat = (
        max(
            threat_values
        )
        if threat_values
        else 0.0
    )

    peak_day = None

    if available_snapshots:

        peak_snapshot = max(
            available_snapshots,
            key=lambda snapshot: (
                number_or_zero(
                    snapshot.get(
                        "overall_summary",
                        {}
                    ).get(
                        "threat_index"
                    )
                ),
                snapshot.get(
                    "snapshot_date",
                    ""
                )
            )
        )

        peak_overall = peak_snapshot.get(
            "overall_summary",
            {}
        )

        peak_day = {
            "date":
                peak_snapshot.get(
                    "snapshot_date"
                ),

            "threat_index":
                round_score(
                    peak_overall.get(
                        "threat_index"
                    )
                ),

            "overall_level":
                peak_overall.get(
                    "overall_level"
                ),

            "event_count":
                int_or_zero(
                    peak_overall.get(
                        "event_count"
                    )
                )
        }

    top_events = sorted(
        all_events,
        key=lambda event: (
            number_or_zero(
                event.get(
                    "threat_score",
                    event.get(
                        "score",
                        0
                    )
                )
            ),
            str(
                event.get(
                    "published_at",
                    ""
                )
                or ""
            )
        ),
        reverse=True
    )[:10]

    return {
        "coverage": {
            "window_days":
                len(
                    window_dates
                ),

            "available_days":
                available_days,

            "missing_days":
                missing_days,

            "coverage_ratio":
                round(
                    (
                        available_days
                        / len(
                            window_dates
                        )
                    )
                    if window_dates
                    else 0.0,
                    4
                ),

            "complete":
                (
                    available_days
                    == len(
                        window_dates
                    )
                )
        },

        "totals": {
            "event_count":
                event_count,

            "incident_count":
                incident_count,

            "activity_count":
                activity_count,

            "indicator_count":
                indicator_count,

            "assessment_count":
                assessment_count
        },

        "indices": {
            "average_operational_index_observed_days":
                round(
                    average_operational,
                    2
                ),

            "average_early_warning_index_observed_days":
                round(
                    average_early_warning,
                    2
                ),

            "average_threat_index_observed_days":
                round(
                    average_threat,
                    2
                ),

            "average_threat_level_observed_days":
                classify_threat_level(
                    average_threat
                ),

            "highest_daily_threat_index":
                round(
                    highest_threat,
                    2
                )
        },

        "peak_day":
            peak_day,

        "country_totals":
            {
                key:
                    round(
                        value,
                        2
                    )
                for key, value in sorted(
                    country_totals.items()
                )
            },

        "category_totals":
            {
                key:
                    round(
                        value,
                        2
                    )
                for key, value in sorted(
                    category_totals.items()
                )
            },

        "actor_totals":
            {
                key:
                    round(
                        value,
                        2
                    )
                for key, value in sorted(
                    actor_totals.items()
                )
            },

        "top_events":
            top_events
    }


# ---------------------------------------------------------------------
# MATRIX BUILD
# ---------------------------------------------------------------------

def build_matrix(
    history: Dict[str, Any]
) -> Dict[str, Any]:

    snapshots = validate_history(
        history
    )

    if not snapshots:

        raise ValueError(
            "Intelligence matrix history contains no snapshots."
        )

    snapshots_by_date = {
        snapshot[
            "snapshot_date"
        ]:
            snapshot
        for snapshot in snapshots
    }

    available_history_dates = sorted(
        snapshots_by_date.keys()
    )

    end_date = available_history_dates[-1]

    window_dates = build_window_dates(
        end_date=end_date,
        days=WINDOW_DAYS
    )

    start_date = window_dates[0]

    daily_matrix: List[
        Dict[str, Any]
    ] = []

    available_snapshots: List[
        Dict[str, Any]
    ] = []

    missing_dates: List[str] = []

    for date_value in window_dates:

        snapshot = snapshots_by_date.get(
            date_value
        )

        if snapshot is None:

            daily_matrix.append(
                build_missing_day(
                    date_value
                )
            )

            missing_dates.append(
                date_value
            )

            continue

        available_snapshots.append(
            snapshot
        )

        daily_matrix.append(
            build_available_day(
                snapshot
            )
        )

    summary = aggregate_window(
        available_snapshots=
            available_snapshots,
        window_dates=
            window_dates
    )

    generated_at = datetime.now(
        timezone.utc
    ).isoformat()

    return {
        "project":
            "baltic-hybrid-monitor",

        "title":
            "Baltic Hybrid Threat 7-Day Intelligence Matrix",

        "region":
            history.get(
                "region",
                "Baltic states and Poland"
            ),

        "generated_at":
            generated_at,

        "matrix_version":
            MATRIX_VERSION,

        "source_history_version":
            history.get(
                "history_version"
            ),

        "source_history_generated_at":
            history.get(
                "generated_at"
            ),

        "window": {
            "time_basis":
                "UTC calendar day",

            "window_days":
                WINDOW_DAYS,

            "start_date":
                start_date,

            "end_date":
                end_date,

            "anchor":
                "latest available snapshot_date in history",

            "construction":
                (
                    "Seven separate exact-day snapshots. "
                    "No rolling-window snapshots are used."
                )
        },

        "method": {
            "description":
                (
                    "Seven-calendar-day intelligence matrix built "
                    "from exact-day records stored in "
                    "baltic_intelligence_matrix_history.json."
                ),

            "missing_day_handling":
                (
                    "A missing history date is represented as "
                    "status=missing with null metrics. "
                    "It is not treated as a zero-event day."
                ),

            "zero_event_day_handling":
                (
                    "An available exact-day snapshot with zero events "
                    "is retained as a valid observed day with zero values."
                ),

            "aggregation_basis":
                (
                    "Totals sum available exact-day records. "
                    "Average indices use available observed days only. "
                    "Missing days are excluded from averages."
                ),

            "threat_index_semantics":
                (
                    "Daily Threat Index values are inherited from "
                    "the exact-day scorer output and are not "
                    "recomputed from a seven-day rolling window."
                )
        },

        "coverage":
            summary[
                "coverage"
            ],

        "missing_dates":
            missing_dates,

        "seven_day_summary": {
            "totals":
                summary[
                    "totals"
                ],

            "indices":
                summary[
                    "indices"
                ],

            "peak_day":
                summary[
                    "peak_day"
                ],

            "country_totals":
                summary[
                    "country_totals"
                ],

            "category_totals":
                summary[
                    "category_totals"
                ],

            "actor_totals":
                summary[
                    "actor_totals"
                ]
        },

        "top_events":
            summary[
                "top_events"
            ],

        "daily_matrix":
            daily_matrix
    }


# ---------------------------------------------------------------------
# OUTPUT VALIDATION
# ---------------------------------------------------------------------

def validate_matrix(
    matrix: Dict[str, Any]
) -> None:

    window = matrix.get(
        "window",
        {}
    )

    if window.get(
        "window_days"
    ) != WINDOW_DAYS:

        raise ValueError(
            "Matrix window_days is inconsistent."
        )

    daily_matrix = matrix.get(
        "daily_matrix"
    )

    if not isinstance(
        daily_matrix,
        list
    ):

        raise ValueError(
            "daily_matrix must be a list."
        )

    if len(
        daily_matrix
    ) != WINDOW_DAYS:

        raise ValueError(
            f"daily_matrix must contain exactly "
            f"{WINDOW_DAYS} calendar-day slots."
        )

    dates = [
        row.get(
            "date"
        )
        for row in daily_matrix
    ]

    expected_dates = build_window_dates(
        end_date=window.get(
            "end_date"
        ),
        days=WINDOW_DAYS
    )

    if dates != expected_dates:

        raise ValueError(
            "daily_matrix dates do not match "
            "the seven-day calendar window."
        )

    valid_statuses = {
        "available",
        "missing"
    }

    for row in daily_matrix:

        status = row.get(
            "status"
        )

        if status not in valid_statuses:

            raise ValueError(
                f"Invalid daily matrix status: {status}"
            )

        if status == "missing":

            numeric_fields = [
                "event_count",
                "incident_count",
                "activity_count",
                "indicator_count",
                "assessment_count",
                "operational_index",
                "early_warning_index",
                "threat_index"
            ]

            for field in numeric_fields:

                if row.get(
                    field
                ) is not None:

                    raise ValueError(
                        "Missing day contains a non-null metric: "
                        f"{row.get('date')} / {field}"
                    )

    coverage = matrix.get(
        "coverage",
        {}
    )

    available_count = sum(
        1
        for row in daily_matrix
        if row.get(
            "status"
        ) == "available"
    )

    missing_count = sum(
        1
        for row in daily_matrix
        if row.get(
            "status"
        ) == "missing"
    )

    if coverage.get(
        "available_days"
    ) != available_count:

        raise ValueError(
            "coverage.available_days is inconsistent."
        )

    if coverage.get(
        "missing_days"
    ) != missing_count:

        raise ValueError(
            "coverage.missing_days is inconsistent."
        )

    missing_dates = matrix.get(
        "missing_dates",
        []
    )

    expected_missing_dates = [
        row.get(
            "date"
        )
        for row in daily_matrix
        if row.get(
            "status"
        ) == "missing"
    ]

    if missing_dates != expected_missing_dates:

        raise ValueError(
            "missing_dates is inconsistent."
        )


# ---------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------

def main() -> None:

    history = load_json(
        HISTORY_INPUT
    )

    matrix = build_matrix(
        history
    )

    validate_matrix(
        matrix
    )

    save_json(
        MATRIX_OUTPUT,
        matrix
    )

    save_json(
        DOCS_MATRIX_OUTPUT,
        matrix
    )

    coverage = matrix.get(
        "coverage",
        {}
    )

    window = matrix.get(
        "window",
        {}
    )

    summary = matrix.get(
        "seven_day_summary",
        {}
    )

    indices = summary.get(
        "indices",
        {}
    )

    print(
        "Baltic 7-day intelligence matrix generated."
    )

    print(
        f"Window: "
        f"{window.get('start_date')} "
        f"to "
        f"{window.get('end_date')}"
    )

    print(
        f"Coverage: "
        f"{coverage.get('available_days')}"
        f"/"
        f"{coverage.get('window_days')}"
    )

    print(
        f"Missing days: "
        f"{coverage.get('missing_days')}"
    )

    print(
        f"Observed-day average Threat Index: "
        f"{indices.get('average_threat_index_observed_days')}"
    )

    print(
        f"Highest daily Threat Index: "
        f"{indices.get('highest_daily_threat_index')}"
    )

    print(
        f"Saved: "
        f"{MATRIX_OUTPUT}"
    )

    print(
        f"Saved: "
        f"{DOCS_MATRIX_OUTPUT}"
    )


if __name__ == "__main__":
    main()
