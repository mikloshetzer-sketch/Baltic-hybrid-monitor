import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List


ROOT = Path(__file__).resolve().parents[1]

SNAPSHOT_INPUT = ROOT / "data" / "baltic_daily_snapshot.json"

HISTORY_OUTPUT = (
    ROOT
    / "data"
    / "baltic_intelligence_matrix_history.json"
)

DOCS_HISTORY_OUTPUT = (
    ROOT
    / "docs"
    / "data"
    / "baltic_intelligence_matrix_history.json"
)


HISTORY_VERSION = "baltic_intelligence_matrix_history_v1_0"


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
# VALIDATION
# ---------------------------------------------------------------------

def validate_snapshot_date(
    value: Any
) -> str:

    if not isinstance(
        value,
        str
    ):

        raise ValueError(
            "snapshot_date must be a string "
            "in YYYY-MM-DD format."
        )

    try:

        parsed = datetime.strptime(
            value,
            "%Y-%m-%d"
        )

    except ValueError as exc:

        raise ValueError(
            f"Invalid snapshot_date: {value}"
        ) from exc

    normalized = parsed.strftime(
        "%Y-%m-%d"
    )

    if normalized != value:

        raise ValueError(
            f"Invalid snapshot_date: {value}"
        )

    return normalized


def validate_snapshot(
    snapshot: Dict[str, Any]
) -> str:

    snapshot_date = validate_snapshot_date(
        snapshot.get(
            "snapshot_date"
        )
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
            "Snapshot method field must be an object."
        )

    if method.get(
        "rolling_window_used"
    ) is True:

        raise ValueError(
            "History input must be an exact-day snapshot, "
            "not a rolling-window snapshot."
        )

    rolling_window_days = method.get(
        "rolling_window_days"
    )

    if (
        rolling_window_days
        not in {
            None,
            0
        }
    ):

        raise ValueError(
            "History input must use rolling_window_days = 0."
        )

    overall_summary = snapshot.get(
        "overall_summary"
    )

    if not isinstance(
        overall_summary,
        dict
    ):

        raise ValueError(
            "Snapshot is missing overall_summary."
        )

    required_summary_fields = [
        "event_count",
        "incident_count",
        "activity_count",
        "indicator_count",
        "assessment_count",
        "operational_index",
        "early_warning_index",
        "threat_index",
        "overall_level"
    ]

    missing = [
        field
        for field in required_summary_fields
        if field not in overall_summary
    ]

    if missing:

        raise ValueError(
            "Snapshot overall_summary is missing fields: "
            + ", ".join(
                missing
            )
        )

    events = snapshot.get(
        "events"
    )

    if not isinstance(
        events,
        list
    ):

        raise ValueError(
            "Snapshot events field must be a list."
        )

    top_events = snapshot.get(
        "top_events"
    )

    if not isinstance(
        top_events,
        list
    ):

        raise ValueError(
            "Snapshot top_events field must be a list."
        )

    return snapshot_date


# ---------------------------------------------------------------------
# HISTORY LOADING
# ---------------------------------------------------------------------

def empty_history() -> Dict[str, Any]:

    return {
        "project":
            "baltic-hybrid-monitor",

        "title":
            "Baltic Intelligence Matrix History",

        "region":
            "Baltic states and Poland",

        "generated_at":
            None,

        "history_version":
            HISTORY_VERSION,

        "record_count":
            0,

        "first_snapshot_date":
            None,

        "last_snapshot_date":
            None,

        "method": {
            "description":
                (
                    "Long-term archive of exact UTC calendar-day "
                    "Baltic Hybrid Threat Daily Snapshot records."
                ),

            "record_key":
                "snapshot_date",

            "update_rule":
                (
                    "A rerun for an existing snapshot_date replaces "
                    "only that date. All other historical dates are "
                    "preserved."
                ),

            "zero_event_days_retained":
                True,

            "rolling_windows_used":
                False,

            "retention":
                "unlimited",

            "intended_use":
                (
                    "Historical daily intelligence matrix input and "
                    "source dataset for future seven-day matrix views."
                )
        },

        "snapshots":
            []
    }


def load_history(
    path: Path
) -> Dict[str, Any]:

    if not path.exists():

        return empty_history()

    history = load_json(
        path
    )

    snapshots = history.get(
        "snapshots",
        []
    )

    if not isinstance(
        snapshots,
        list
    ):

        raise ValueError(
            "History snapshots field must be a list."
        )

    return history


# ---------------------------------------------------------------------
# SNAPSHOT NORMALIZATION
# ---------------------------------------------------------------------

def normalize_snapshot_record(
    snapshot: Dict[str, Any]
) -> Dict[str, Any]:

    snapshot_date = validate_snapshot(
        snapshot
    )

    record = dict(
        snapshot
    )

    record[
        "snapshot_date"
    ] = snapshot_date

    return record


# ---------------------------------------------------------------------
# HISTORY UPDATE
# ---------------------------------------------------------------------

def update_history(
    history: Dict[str, Any],
    snapshot: Dict[str, Any]
) -> Dict[str, Any]:

    record = normalize_snapshot_record(
        snapshot
    )

    snapshot_date = record[
        "snapshot_date"
    ]

    existing_snapshots = history.get(
        "snapshots",
        []
    )

    if not isinstance(
        existing_snapshots,
        list
    ):

        raise ValueError(
            "History snapshots field must be a list."
        )

    by_date: Dict[
        str,
        Dict[str, Any]
    ] = {}

    for existing in existing_snapshots:

        if not isinstance(
            existing,
            dict
        ):

            continue

        existing_date = existing.get(
            "snapshot_date"
        )

        if not existing_date:

            continue

        try:

            existing_date = (
                validate_snapshot_date(
                    existing_date
                )
            )

        except ValueError:

            continue

        by_date[
            existing_date
        ] = existing

    existed_before = (
        snapshot_date
        in by_date
    )

    by_date[
        snapshot_date
    ] = record

    ordered_dates = sorted(
        by_date.keys()
    )

    ordered_snapshots = [
        by_date[
            date
        ]
        for date in ordered_dates
    ]

    now = datetime.now(
        timezone.utc
    ).isoformat()

    output = {
        "project":
            history.get(
                "project",
                snapshot.get(
                    "project",
                    "baltic-hybrid-monitor"
                )
            ),

        "title":
            history.get(
                "title",
                "Baltic Intelligence Matrix History"
            ),

        "region":
            snapshot.get(
                "region",
                history.get(
                    "region",
                    "Baltic states and Poland"
                )
            ),

        "generated_at":
            now,

        "history_version":
            HISTORY_VERSION,

        "record_count":
            len(
                ordered_snapshots
            ),

        "first_snapshot_date":
            (
                ordered_dates[0]
                if ordered_dates
                else None
            ),

        "last_snapshot_date":
            (
                ordered_dates[-1]
                if ordered_dates
                else None
            ),

        "last_update": {
            "snapshot_date":
                snapshot_date,

            "action":
                (
                    "replaced"
                    if existed_before
                    else "inserted"
                ),

            "updated_at":
                now,

            "source_snapshot_generated_at":
                snapshot.get(
                    "generated_at"
                ),

            "source_snapshot_version":
                snapshot.get(
                    "snapshot_version"
                ),

            "source_score_engine_version":
                snapshot.get(
                    "score_engine_version"
                )
        },

        "method":
            history.get(
                "method",
                empty_history()[
                    "method"
                ]
            ),

        "snapshots":
            ordered_snapshots
    }

    return output


# ---------------------------------------------------------------------
# CONSISTENCY CHECKS
# ---------------------------------------------------------------------

def validate_history(
    history: Dict[str, Any]
) -> None:

    snapshots = history.get(
        "snapshots",
        []
    )

    if not isinstance(
        snapshots,
        list
    ):

        raise ValueError(
            "History snapshots field must be a list."
        )

    dates: List[str] = []

    for snapshot in snapshots:

        if not isinstance(
            snapshot,
            dict
        ):

            raise ValueError(
                "Every history snapshot must be an object."
            )

        dates.append(
            validate_snapshot_date(
                snapshot.get(
                    "snapshot_date"
                )
            )
        )

    if len(
        dates
    ) != len(
        set(
            dates
        )
    ):

        raise ValueError(
            "Duplicate snapshot_date values detected in history."
        )

    if dates != sorted(
        dates
    ):

        raise ValueError(
            "History snapshots are not sorted "
            "by snapshot_date."
        )

    if history.get(
        "record_count"
    ) != len(
        snapshots
    ):

        raise ValueError(
            "History record_count does not match "
            "the number of snapshots."
        )

    expected_first = (
        dates[0]
        if dates
        else None
    )

    expected_last = (
        dates[-1]
        if dates
        else None
    )

    if history.get(
        "first_snapshot_date"
    ) != expected_first:

        raise ValueError(
            "History first_snapshot_date is inconsistent."
        )

    if history.get(
        "last_snapshot_date"
    ) != expected_last:

        raise ValueError(
            "History last_snapshot_date is inconsistent."
        )


# ---------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------

def main() -> None:

    snapshot = load_json(
        SNAPSHOT_INPUT
    )

    snapshot_date = validate_snapshot(
        snapshot
    )

    history = load_history(
        HISTORY_OUTPUT
    )

    updated_history = update_history(
        history,
        snapshot
    )

    validate_history(
        updated_history
    )

    save_json(
        HISTORY_OUTPUT,
        updated_history
    )

    save_json(
        DOCS_HISTORY_OUTPUT,
        updated_history
    )

    last_update = updated_history.get(
        "last_update",
        {}
    )

    print(
        f"Snapshot date: "
        f"{snapshot_date}"
    )

    print(
        f"History action: "
        f"{last_update.get('action')}"
    )

    print(
        f"History records: "
        f"{updated_history.get('record_count')}"
    )

    print(
        f"First snapshot: "
        f"{updated_history.get('first_snapshot_date')}"
    )

    print(
        f"Last snapshot: "
        f"{updated_history.get('last_snapshot_date')}"
    )

    print(
        f"Saved: "
        f"{HISTORY_OUTPUT}"
    )

    print(
        f"Saved: "
        f"{DOCS_HISTORY_OUTPUT}"
    )


if __name__ == "__main__":
    main()
