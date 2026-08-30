import json
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Dict, Any, List, Optional


ROOT = Path(__file__).resolve().parents[1]

SCORED_INPUT = ROOT / "data" / "baltic_hybrid_scored_news.json"
HISTORY_INPUT = ROOT / "data" / "baltic_hybrid_history.json"
DASHBOARD_OUTPUT = ROOT / "docs" / "data" / "baltic_dashboard.json"


TOP_EVENT_LIMIT = 30
TOP_DRIVER_LIMIT = 10
HISTORY_LIMIT = 30
CURRENT_THREAT_WINDOW_DAYS = 14


# ---------------------------------------------------------------------
# BASIC IO
# ---------------------------------------------------------------------

def load_json(path: Path, default: Any = None) -> Any:

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


# ---------------------------------------------------------------------
# CURRENT SUMMARY
# ---------------------------------------------------------------------

def normalize_summary(
    scored: Dict[str, Any]
) -> Dict[str, Any]:

    overall = scored.get(
        "overall_summary",
        {}
    )

    threat_index = safe_round(
        overall.get(
            "threat_index",
            overall.get(
                "average_score",
                0
            )
        )
    )

    return {
        "threat_index":
            threat_index,

        "threat_level":
            overall.get(
                "overall_level",
                level_from_score(
                    threat_index
                )
            ),

        "operational_index":
            safe_round(
                overall.get(
                    "operational_index",
                    overall.get(
                        "operational_score",
                        0
                    )
                )
            ),

        "early_warning_index":
            safe_round(
                overall.get(
                    "early_warning_index",
                    overall.get(
                        "early_warning_score",
                        0
                    )
                )
            ),

        "event_count":
            safe_int(
                overall.get(
                    "event_count",
                    0
                )
            ),

        "incident_count":
            safe_int(
                overall.get(
                    "incident_count",
                    0
                )
            ),

        "activity_count":
            safe_int(
                overall.get(
                    "activity_count",
                    0
                )
            ),

        "indicator_count":
            safe_int(
                overall.get(
                    "indicator_count",
                    0
                )
            ),

        "assessment_count":
            safe_int(
                overall.get(
                    "assessment_count",
                    0
                )
            ),

        "score_total":
            safe_int(
                overall.get(
                    "score_total",
                    0
                )
            ),

        "average_score":
            safe_round(
                overall.get(
                    "average_score",
                    0
                )
            ),

        "highest_score":
            safe_int(
                overall.get(
                    "highest_score",
                    0
                )
            ),

        "raw_item_count":
            safe_int(
                scored.get(
                    "raw_item_count",
                    0
                )
            ),

        "filtered_item_count":
            safe_int(
                scored.get(
                    "filtered_item_count",
                    0
                )
            ),

        "clustered_event_count":
            safe_int(
                scored.get(
                    "clustered_event_count",
                    0
                )
            ),

        "merged_item_count":
            safe_int(
                scored.get(
                    "merged_item_count",
                    0
                )
            )
    }


# ---------------------------------------------------------------------
# GENERIC MAPPING HELPERS
# ---------------------------------------------------------------------

def top_items_from_mapping(
    mapping: Dict[str, Any],
    limit: int
) -> List[Dict[str, Any]]:

    items = []

    for key, value in mapping.items():

        try:
            count = int(
                value
            )

        except (TypeError, ValueError):
            count = 0

        items.append({
            "name":
                key,

            "count":
                count
        })

    return sorted(
        items,
        key=lambda item:
            item["count"],
        reverse=True
    )[:limit]


# ---------------------------------------------------------------------
# COUNTRY CARDS
# ---------------------------------------------------------------------

def build_country_cards(
    scored: Dict[str, Any]
) -> List[Dict[str, Any]]:

    country_summary = scored.get(
        "country_summary",
        {}
    )

    cards = []

    for country, data in country_summary.items():

        cards.append({
            "country":
                country,

            "event_count":
                safe_int(
                    data.get(
                        "event_count",
                        0
                    )
                ),

            "incident_count":
                safe_int(
                    data.get(
                        "incident_count",
                        0
                    )
                ),

            "activity_count":
                safe_int(
                    data.get(
                        "activity_count",
                        0
                    )
                ),

            "indicator_count":
                safe_int(
                    data.get(
                        "indicator_count",
                        0
                    )
                ),

            "assessment_count":
                safe_int(
                    data.get(
                        "assessment_count",
                        0
                    )
                ),

            "score_total":
                safe_int(
                    data.get(
                        "score_total",
                        0
                    )
                ),

            "average_score":
                safe_round(
                    data.get(
                        "average_score",
                        0
                    )
                ),

            "highest_score":
                safe_int(
                    data.get(
                        "highest_score",
                        0
                    )
                ),

            "level":
                data.get(
                    "level",
                    "low"
                ),

            "top_categories":
                top_items_from_mapping(
                    data.get(
                        "categories",
                        {}
                    ),
                    5
                ),

            "top_actors":
                top_items_from_mapping(
                    data.get(
                        "actors",
                        {}
                    ),
                    5
                )
        })

    return sorted(
        cards,
        key=lambda item:
            item["score_total"],
        reverse=True
    )


# ---------------------------------------------------------------------
# CATEGORY DRIVERS
# ---------------------------------------------------------------------

def build_category_drivers(
    scored: Dict[str, Any]
) -> List[Dict[str, Any]]:

    category_summary = scored.get(
        "category_summary",
        {}
    )

    drivers = []

    for category, data in category_summary.items():

        drivers.append({
            "category":
                category,

            "event_count":
                safe_int(
                    data.get(
                        "event_count",
                        0
                    )
                ),

            "score_total":
                safe_int(
                    data.get(
                        "score_total",
                        0
                    )
                ),

            "average_score":
                safe_round(
                    data.get(
                        "average_score",
                        0
                    )
                ),

            "highest_score":
                safe_int(
                    data.get(
                        "highest_score",
                        0
                    )
                )
        })

    return sorted(
        drivers,
        key=lambda item:
            item["score_total"],
        reverse=True
    )[:TOP_DRIVER_LIMIT]


# ---------------------------------------------------------------------
# ACTOR DRIVERS
# ---------------------------------------------------------------------

def build_actor_drivers(
    scored: Dict[str, Any]
) -> List[Dict[str, Any]]:

    actor_summary = scored.get(
        "actor_summary",
        {}
    )

    actors = []

    for actor, data in actor_summary.items():

        actors.append({
            "actor":
                actor,

            "event_count":
                safe_int(
                    data.get(
                        "event_count",
                        0
                    )
                ),

            "score_total":
                safe_int(
                    data.get(
                        "score_total",
                        0
                    )
                ),

            "average_score":
                safe_round(
                    data.get(
                        "average_score",
                        0
                    )
                ),

            "highest_score":
                safe_int(
                    data.get(
                        "highest_score",
                        0
                    )
                )
        })

    return sorted(
        actors,
        key=lambda item:
            item["score_total"],
        reverse=True
    )[:TOP_DRIVER_LIMIT]


# ---------------------------------------------------------------------
# SUBTYPE CARDS
# ---------------------------------------------------------------------

def build_subtype_cards(
    scored: Dict[str, Any]
) -> List[Dict[str, Any]]:

    subtype_summary = scored.get(
        "subtype_summary",
        {}
    )

    order = [
        "incident",
        "activity",
        "indicator",
        "assessment"
    ]

    cards = []

    for subtype in order:

        data = subtype_summary.get(
            subtype,
            {}
        )

        cards.append({
            "subtype":
                subtype,

            "label":
                subtype.title(),

            "event_count":
                safe_int(
                    data.get(
                        "event_count",
                        0
                    )
                ),

            "score_total":
                safe_int(
                    data.get(
                        "score_total",
                        0
                    )
                ),

            "average_score":
                safe_round(
                    data.get(
                        "average_score",
                        0
                    )
                )
        })

    return cards


# ---------------------------------------------------------------------
# EVENT NORMALIZATION
# ---------------------------------------------------------------------

def compact_event(
    event: Dict[str, Any]
) -> Dict[str, Any]:

    return {
        "event_id":
            event.get(
                "event_id",
                event.get("id")
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
            event.get(
                "countries",
                []
            )[:5],

        "categories":
            event.get(
                "categories",
                []
            )[:5],

        "actors":
            event.get(
                "actors",
                []
            )[:5],

        "locations":
            event.get(
                "locations",
                []
            )[:5],

        "event_type":
            event.get(
                "event_type",
                "background"
            ),

        "event_subtype":
            event.get(
                "event_subtype",
                "assessment"
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
            safe_int(
                event.get(
                    "hybrid_threat_score",
                    0
                )
            ),

        "hybrid_threat_level":
            event.get(
                "hybrid_threat_level",
                "low"
            ),

        "source_names":
            event.get(
                "source_names",
                []
            )[:5],

        "related_item_count":
            safe_int(
                event.get(
                    "related_item_count",
                    0
                )
            )
    }


# ---------------------------------------------------------------------
# CURRENT THREAT WINDOW
# ---------------------------------------------------------------------

def filter_events_by_current_window(
    events: List[Dict[str, Any]],
    window_days: int
) -> List[Dict[str, Any]]:

    now = datetime.now(
        timezone.utc
    )

    start_time = (
        now
        - timedelta(
            days=window_days - 1
        )
    ).replace(
        hour=0,
        minute=0,
        second=0,
        microsecond=0
    )

    filtered = []

    for event in events:

        published_at = parse_datetime(
            event.get(
                "published_at"
            )
        )

        if published_at is None:
            continue

        if (
            start_time
            <= published_at
            <= now
        ):

            filtered.append(
                event
            )

    return filtered


def build_top_events(
    scored: Dict[str, Any],
    window_days: int = CURRENT_THREAT_WINDOW_DAYS
) -> List[Dict[str, Any]]:

    events = scored.get(
        "events",
        scored.get(
            "items",
            []
        )
    )

    recent_events = filter_events_by_current_window(
        events,
        window_days
    )

    compact = [
        compact_event(
            event
        )
        for event in recent_events
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


def build_recent_events(
    scored: Dict[str, Any],
    window_days: int = CURRENT_THREAT_WINDOW_DAYS
) -> List[Dict[str, Any]]:

    events = scored.get(
        "events",
        scored.get(
            "items",
            []
        )
    )

    recent_events = filter_events_by_current_window(
        events,
        window_days
    )

    compact = [
        compact_event(
            event
        )
        for event in recent_events
    ]

    compact = sorted(
        compact,
        key=lambda event:
            event.get(
                "published_at",
                ""
            ),
        reverse=True
    )

    return compact[
        :TOP_EVENT_LIMIT
    ]


# ---------------------------------------------------------------------
# HISTORY
# ---------------------------------------------------------------------

def get_scored_events(
    scored: Dict[str, Any]
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

    return events


def event_date_iso(
    event: Dict[str, Any]
) -> Optional[str]:

    published_at = parse_datetime(
        event.get(
            "published_at"
        )
    )

    if published_at is None:
        return None

    return published_at.date().isoformat()


def filter_events_for_date(
    events: List[Dict[str, Any]],
    target_date: str
) -> List[Dict[str, Any]]:

    return [
        event
        for event in events
        if event_date_iso(
            event
        ) == target_date
    ]


def filter_events_for_rolling_window(
    events: List[Dict[str, Any]],
    target_date: str,
    window_days: int
) -> List[Dict[str, Any]]:

    try:
        end_date = datetime.fromisoformat(
            target_date
        ).date()

    except (TypeError, ValueError):
        return []

    start_date = (
        end_date
        - timedelta(
            days=window_days - 1
        )
    )

    selected = []

    for event in events:

        published_at = parse_datetime(
            event.get(
                "published_at"
            )
        )

        if published_at is None:
            continue

        published_date = (
            published_at.date()
        )

        if (
            start_date
            <= published_date
            <= end_date
        ):
            selected.append(
                event
            )

    return selected


def event_matches_country(
    event: Dict[str, Any],
    country: str
) -> bool:

    primary_country = event.get(
        "primary_country"
    )

    countries = event.get(
        "countries",
        []
    )

    if not isinstance(
        countries,
        list
    ):
        countries = []

    if country == "Regional":

        return (
            primary_country == "Regional"
            or "Regional" in countries
        )

    return (
        primary_country == country
        or country in countries
    )


def calculate_v32_indices(
    events: List[Dict[str, Any]]
) -> Dict[str, Any]:

    operational_scores = []
    early_warning_scores = []

    incident_count = 0
    activity_count = 0
    indicator_count = 0
    assessment_count = 0

    for event in events:

        subtype = str(
            event.get(
                "event_subtype",
                "assessment"
            )
        ).strip().lower()

        score = safe_round(
            event.get(
                "hybrid_threat_score",
                0
            )
        )

        if subtype == "incident":

            incident_count += 1
            operational_scores.append(
                score
            )

        elif subtype == "activity":

            activity_count += 1
            operational_scores.append(
                score
            )

        elif subtype == "indicator":

            indicator_count += 1
            early_warning_scores.append(
                score
            )

        else:

            assessment_count += 1

    top_operational = sorted(
        operational_scores,
        reverse=True
    )[:5]

    top_warning = sorted(
        early_warning_scores,
        reverse=True
    )[:8]

    operational_index = (
        safe_round(
            sum(
                top_operational
            )
            / len(
                top_operational
            )
        )
        if top_operational
        else 0.0
    )

    early_warning_index = (
        safe_round(
            sum(
                top_warning
            )
            / len(
                top_warning
            )
        )
        if top_warning
        else 0.0
    )

    if top_operational:

        threat_index = safe_round(
            (
                0.8
                * operational_index
            )
            + (
                0.2
                * early_warning_index
            )
        )

    else:

        threat_index = (
            early_warning_index
        )

    return {
        "event_count":
            len(
                events
            ),

        "incident_count":
            incident_count,

        "activity_count":
            activity_count,

        "indicator_count":
            indicator_count,

        "assessment_count":
            assessment_count,

        "operational_index":
            operational_index,

        "early_warning_index":
            early_warning_index,

        "threat_index":
            threat_index,

        "level":
            level_from_score(
                threat_index
            )
    }


def calculate_country_v32_index(
    events: List[Dict[str, Any]],
    country: str
) -> float:

    country_events = [
        event
        for event in events
        if event_matches_country(
            event,
            country
        )
    ]

    return calculate_v32_indices(
        country_events
    )[
        "threat_index"
    ]


def normalize_history_hotspot(
    container: Dict[str, Any]
) -> Dict[str, Any]:

    hotspot = container.get(
        "hotspot",
        {}
    )

    if not isinstance(
        hotspot,
        dict
    ):
        hotspot = {}

    return {
        "location":
            hotspot.get(
                "location"
            ),

        "score":
            safe_int(
                hotspot.get(
                    "score",
                    0
                )
            ),

        "event_count":
            safe_int(
                hotspot.get(
                    "event_count",
                    0
                )
            )
    }


def build_history(
    scored: Dict[str, Any],
    history: Dict[str, Any]
) -> Dict[str, Any]:

    records = []

    if isinstance(
        history,
        dict
    ):
        records = history.get(
            "records",
            []
        )

    if not isinstance(
        records,
        list
    ):
        records = []

    records = sorted(
        records,
        key=lambda record:
            record.get(
                "date",
                ""
            )
    )

    records = records[
        -HISTORY_LIMIT:
    ]

    events = get_scored_events(
        scored
    )

    labels = []

    daily_threat_index = []
    daily_operational_index = []
    daily_early_warning_index = []
    daily_level = []

    incident_count = []
    activity_count = []
    indicator_count = []
    assessment_count = []

    rolling_threat_index = []
    rolling_operational_index = []
    rolling_early_warning_index = []
    rolling_level = []

    country_scores = {
        "Estonia": [],
        "Latvia": [],
        "Lithuania": [],
        "Poland": [],
        "Regional": []
    }

    rolling_country_scores = {
        "Estonia": [],
        "Latvia": [],
        "Lithuania": [],
        "Poland": [],
        "Regional": []
    }

    daily_hotspots = []
    rolling_hotspots = []

    key_drivers = []
    trends = []

    for record in records:

        record_date = record.get(
            "date"
        )

        if not record_date:
            continue

        labels.append(
            record_date
        )

        daily = record.get(
            "daily_activity",
            {}
        )

        if not isinstance(
            daily,
            dict
        ):
            daily = {}

        rolling = record.get(
            "rolling_threat",
            {}
        )

        if not isinstance(
            rolling,
            dict
        ):
            rolling = {}

        daily_events = filter_events_for_date(
            events,
            record_date
        )

        rolling_events = (
            filter_events_for_rolling_window(
                events,
                record_date,
                CURRENT_THREAT_WINDOW_DAYS
            )
        )

        daily_indices = calculate_v32_indices(
            daily_events
        )

        rolling_indices = calculate_v32_indices(
            rolling_events
        )

        daily_threat_index.append(
            daily_indices[
                "threat_index"
            ]
        )

        daily_operational_index.append(
            daily_indices[
                "operational_index"
            ]
        )

        daily_early_warning_index.append(
            daily_indices[
                "early_warning_index"
            ]
        )

        daily_level.append(
            daily_indices[
                "level"
            ]
        )

        incident_count.append(
            daily_indices[
                "incident_count"
            ]
        )

        activity_count.append(
            daily_indices[
                "activity_count"
            ]
        )

        indicator_count.append(
            daily_indices[
                "indicator_count"
            ]
        )

        assessment_count.append(
            daily_indices[
                "assessment_count"
            ]
        )

        for country in country_scores:

            country_scores[
                country
            ].append(
                calculate_country_v32_index(
                    daily_events,
                    country
                )
            )

            rolling_country_scores[
                country
            ].append(
                calculate_country_v32_index(
                    rolling_events,
                    country
                )
            )

        daily_hotspots.append(
            normalize_history_hotspot(
                daily
            )
        )

        rolling_hotspots.append(
            normalize_history_hotspot(
                rolling
            )
        )

        key_drivers.append(
            daily.get(
                "key_driver"
            )
        )

        trends.append(
            daily.get(
                "trend",
                "stable"
            )
        )

        rolling_threat_index.append(
            rolling_indices[
                "threat_index"
            ]
        )

        rolling_operational_index.append(
            rolling_indices[
                "operational_index"
            ]
        )

        rolling_early_warning_index.append(
            rolling_indices[
                "early_warning_index"
            ]
        )

        rolling_level.append(
            rolling_indices[
                "level"
            ]
        )

    if not labels:

        summary = normalize_summary(
            scored
        )

        reference_date = (
            scored
            .get(
                "current_threat_window",
                {}
            )
            .get(
                "reference_date"
            )
        )

        current_date = (
            reference_date
            or datetime.now(
                timezone.utc
            ).date().isoformat()
        )

        labels = [
            current_date
        ]

        daily_threat_index = [
            0.0
        ]

        daily_operational_index = [
            0.0
        ]

        daily_early_warning_index = [
            0.0
        ]

        daily_level = [
            "low"
        ]

        rolling_threat_index = [
            summary[
                "threat_index"
            ]
        ]

        rolling_operational_index = [
            summary[
                "operational_index"
            ]
        ]

        rolling_early_warning_index = [
            summary[
                "early_warning_index"
            ]
        ]

        rolling_level = [
            summary[
                "threat_level"
            ]
        ]

        current_daily_events = (
            filter_events_for_date(
                events,
                current_date
            )
        )

        current_daily_indices = (
            calculate_v32_indices(
                current_daily_events
            )
        )

        daily_threat_index[0] = (
            current_daily_indices[
                "threat_index"
            ]
        )

        daily_operational_index[0] = (
            current_daily_indices[
                "operational_index"
            ]
        )

        daily_early_warning_index[0] = (
            current_daily_indices[
                "early_warning_index"
            ]
        )

        daily_level[0] = (
            current_daily_indices[
                "level"
            ]
        )

        incident_count = [
            current_daily_indices[
                "incident_count"
            ]
        ]

        activity_count = [
            current_daily_indices[
                "activity_count"
            ]
        ]

        indicator_count = [
            current_daily_indices[
                "indicator_count"
            ]
        ]

        assessment_count = [
            current_daily_indices[
                "assessment_count"
            ]
        ]

        rolling_events = (
            filter_events_for_rolling_window(
                events,
                current_date,
                CURRENT_THREAT_WINDOW_DAYS
            )
        )

        for country in country_scores:

            country_scores[
                country
            ] = [
                calculate_country_v32_index(
                    current_daily_events,
                    country
                )
            ]

            rolling_country_scores[
                country
            ] = [
                calculate_country_v32_index(
                    rolling_events,
                    country
                )
            ]

        daily_hotspots = [{
            "location":
                None,

            "score":
                0,

            "event_count":
                0
        }]

        rolling_hotspots = [{
            "location":
                None,

            "score":
                0,

            "event_count":
                0
        }]

        key_drivers = [
            None
        ]

        trends = [
            "stable"
        ]

    scorer_reference_date = (
        scored
        .get(
            "current_threat_window",
            {}
        )
        .get(
            "reference_date"
        )
    )

    summary = normalize_summary(
        scored
    )

    latest_history_date = (
        labels[-1]
        if labels
        else None
    )

    current_alignment = {
        "comparable":
            (
                latest_history_date
                == scorer_reference_date
            ),

        "history_latest_date":
            latest_history_date,

        "scorer_reference_date":
            scorer_reference_date,

        "summary_threat_index":
            summary[
                "threat_index"
            ],

        "history_latest_rolling_threat_index":
            (
                rolling_threat_index[-1]
                if rolling_threat_index
                else None
            ),

        "matches_current_summary":
            (
                bool(
                    labels
                )
                and (
                    latest_history_date
                    == scorer_reference_date
                )
                and (
                    abs(
                        rolling_threat_index[-1]
                        - summary[
                            "threat_index"
                        ]
                    )
                    < 0.01
                )
            )
    }

    return {
        "labels":
            labels,

        # Backward-compatible alias. This is now a real
        # exact-day v3.2 Threat Index, not average_score.
        "threat_index":
            daily_threat_index,

        "daily_threat_index":
            daily_threat_index,

        "daily_operational_index":
            daily_operational_index,

        "daily_early_warning_index":
            daily_early_warning_index,

        "daily_level":
            daily_level,

        "rolling_threat_index":
            rolling_threat_index,

        "rolling_operational_index":
            rolling_operational_index,

        "rolling_early_warning_index":
            rolling_early_warning_index,

        "rolling_level":
            rolling_level,

        "incident_count":
            incident_count,

        "activity_count":
            activity_count,

        "indicator_count":
            indicator_count,

        "assessment_count":
            assessment_count,

        "country_scores":
            country_scores,

        "rolling_country_scores":
            rolling_country_scores,

        "daily_hotspots":
            daily_hotspots,

        "rolling_hotspots":
            rolling_hotspots,

        "key_drivers":
            key_drivers,

        "trends":
            trends,

        "history_window":
            len(
                labels
            ),

        "rolling_window_days":
            CURRENT_THREAT_WINDOW_DAYS,

        "index_method": {
            "daily":
                (
                    "Recomputed from scored events published on each "
                    "UTC calendar day using the v3.2 Operational / "
                    "Early Warning / Threat Index method."
                ),

            "rolling":
                (
                    "Recomputed from scored events inside the 14 UTC "
                    "calendar-day window ending on each history date "
                    "using the same v3.2 index method as the current KPI."
                ),

            "operational_index":
                (
                    "Average of the five highest scoring "
                    "incident/activity events."
                ),

            "early_warning_index":
                (
                    "Average of the eight highest scoring "
                    "indicator events."
                ),

            "threat_index":
                (
                    "80% Operational Index + 20% Early Warning Index "
                    "when operational events exist; otherwise the "
                    "Early Warning Index."
                ),

            "assessment_handling":
                (
                    "Assessment events are counted but do not "
                    "contribute to either component index."
                )
        },

        "current_alignment":
            current_alignment
    }


# ---------------------------------------------------------------------
# DATA QUALITY
# ---------------------------------------------------------------------

def build_data_quality(
    scored: Dict[str, Any]
) -> Dict[str, Any]:

    summary = normalize_summary(
        scored
    )

    raw_count = summary[
        "raw_item_count"
    ]

    filtered_count = summary[
        "filtered_item_count"
    ]

    clustered_count = summary[
        "clustered_event_count"
    ]

    filter_reduction = 0
    cluster_reduction = 0

    if raw_count > 0:

        filter_reduction = round(
            (
                raw_count
                - filtered_count
            )
            / raw_count
            * 100,
            2
        )

    if filtered_count > 0:

        cluster_reduction = round(
            (
                filtered_count
                - clustered_count
            )
            / filtered_count
            * 100,
            2
        )

    return {
        "raw_item_count":
            raw_count,

        "filtered_item_count":
            filtered_count,

        "clustered_event_count":
            clustered_count,

        "merged_item_count":
            summary[
                "merged_item_count"
            ],

        "filter_reduction_percent":
            filter_reduction,

        "cluster_reduction_percent":
            cluster_reduction
    }


# ---------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------

def main() -> None:

    scored = load_json(
        SCORED_INPUT,
        default=None
    )

    history = load_json(
        HISTORY_INPUT,
        default={}
    )

    if scored is None:

        raise FileNotFoundError(
            f"Missing scored input file: "
            f"{SCORED_INPUT}. "
            "Run scripts/score_baltic_hybrid_news.py first."
        )

    dashboard_history = build_history(
        scored,
        history
    )

    scorer_engine_version = scored.get(
        "engine_version",
        "unknown"
    )

    payload = {
        "project":
            scored.get(
                "project",
                "baltic-hybrid-monitor"
            ),

        "title":
            "Baltic Hybrid Intelligence Platform",

        "subtitle":
            (
                "Event-based OSINT monitoring of hybrid threats "
                "in the Baltic states and Poland"
            ),

        "region":
            scored.get(
                "region",
                "Baltic states and Poland"
            ),

        "generated_at":
            datetime.now(
                timezone.utc
            ).isoformat(),

        "latest_update":
            scored.get(
                "generated_at"
            ),

        "version":
            "Baltic Dashboard Data v1.4",

        "score_engine_version":
            scorer_engine_version,

        "summary":
            normalize_summary(
                scored
            ),

        "subtype_cards":
            build_subtype_cards(
                scored
            ),

        "country_cards":
            build_country_cards(
                scored
            ),

        "category_drivers":
            build_category_drivers(
                scored
            ),

        "actor_drivers":
            build_actor_drivers(
                scored
            ),

        "top_events":
            build_top_events(
                scored,
                CURRENT_THREAT_WINDOW_DAYS
            ),

        "recent_events":
            build_recent_events(
                scored,
                CURRENT_THREAT_WINDOW_DAYS
            ),

        "current_threat_window": {
            "days":
                CURRENT_THREAT_WINDOW_DAYS,

            "window_type":
                "rolling_current_threat",

            "time_semantics":
                "14 calendar days",

            "description":
                (
                    "Top and recent events are limited to the "
                    "current rolling threat window."
                ),

            "separate_from_exact_day":
                True,

            "separate_from_7day_matrix":
                True
        },

        "history":
            dashboard_history,

        "data_quality":
            build_data_quality(
                scored
            ),

        "methodology": {
            "model":
                (
                    "Event-based rule-driven OSINT "
                    "threat intelligence model."
                ),

            "pipeline": [
                "RSS and HTML source collection",
                "Threat relevance filtering",
                "Event clustering",
                "Primary country assignment",
                "Threat ontology classification",
                "Confidence scoring",
                f"Threat Score Engine: {scorer_engine_version}",
                "Historical exact-day v3.2 index reconstruction",
                "Historical 14-day rolling v3.2 index reconstruction",
                "Current 14-day top-event filtering",
                "Dashboard-optimized output",
                "Exact-day snapshot and 7-day matrix are generated by separate pipeline stages"
            ],

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

            "time_semantics": {
                "current_threat":
                    "14-day rolling current threat picture.",

                "exact_day":
                    "One UTC calendar day; generated outside this dashboard-data script.",

                "seven_day_matrix":
                    (
                        "Seven separate exact-day snapshots; generated outside "
                        "this dashboard-data script. Missing historical day is not zero."
                    ),

                "history":
                    "Long-term historical archive; retention is independent of the current threat window."
            },

            "history_model": {
                "daily_activity":
                    (
                        "Exact calendar-day Threat Index reconstructed "
                        "from scored events published on that date using v3.2."
                    ),

                "rolling_threat":
                    (
                        "Fourteen-day rolling Threat Index reconstructed "
                        "from scored events ending on each calendar date using v3.2."
                    ),

                "historical_database":
                    (
                        "Long-term daily history is preserved "
                        "independently of the rolling calculation window."
                    )
            },

            "current_event_model": {
                "top_events":
                    (
                        "Highest-scoring events published inside the "
                        "current 14-day rolling threat window."
                    ),

                "recent_events":
                    (
                        "Most recently published events inside the "
                        "current 14-day rolling threat window."
                    ),

                "historical_events":
                    (
                        "Older events remain available in the scored "
                        "dataset and historical database but are not "
                        "presented as current top threats."
                    )
            },

            "event_subtypes": {
                "incident":
                    (
                        "Reported operational event such as drone "
                        "incident, cyberattack, sabotage, border event "
                        "or GPS interference."
                    ),

                "activity":
                    (
                        "Security or military activity shaping "
                        "the threat environment."
                    ),

                "indicator":
                    (
                        "Early warning or information signal."
                    ),

                "assessment":
                    (
                        "Strategic, institutional or analytical "
                        "background. It is not counted into the "
                        "operational threat index."
                    )
            },

            "warning":
                (
                    "This dashboard is an OSINT monitoring aid. "
                    "It does not confirm attribution and should not "
                    "be treated as an official threat assessment."
                )
        }
    }

    save_json(
        DASHBOARD_OUTPUT,
        payload
    )

    print(
        f"Saved dashboard data to "
        f"{DASHBOARD_OUTPUT}"
    )

    print(
        f"Dashboard history records: "
        f"{dashboard_history.get('history_window', 0)}"
    )

    print(
        f"Current top-event window: "
        f"{CURRENT_THREAT_WINDOW_DAYS} days"
    )

    print(
        "Top events now exclude older historical events."
    )

    print(
        "History source: unified daily_activity + rolling_threat schema"
    )


if __name__ == "__main__":
    main()
