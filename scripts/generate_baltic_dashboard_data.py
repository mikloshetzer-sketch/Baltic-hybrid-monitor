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

    labels = []

    daily_threat_index = []
    daily_level = []

    incident_count = []
    activity_count = []
    indicator_count = []
    assessment_count = []

    rolling_threat_index = []
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

        labels.append(
            record.get(
                "date"
            )
        )

        daily = record.get(
            "daily_activity",
            {}
        )

        rolling = record.get(
            "rolling_threat",
            {}
        )

        daily_overall = daily.get(
            "overall",
            {}
        )

        rolling_overall = rolling.get(
            "overall",
            {}
        )

        daily_average = safe_round(
            daily_overall.get(
                "average_score",
                0
            )
        )

        daily_threat_index.append(
            daily_average
        )

        daily_level.append(
            daily_overall.get(
                "overall_level",
                level_from_score(
                    daily_average
                )
            )
        )

        incident_count.append(
            safe_int(
                daily_overall.get(
                    "incident_count",
                    0
                )
            )
        )

        activity_count.append(
            safe_int(
                daily_overall.get(
                    "activity_count",
                    0
                )
            )
        )

        indicator_count.append(
            safe_int(
                daily_overall.get(
                    "indicator_count",
                    0
                )
            )
        )

        assessment_count.append(
            safe_int(
                daily_overall.get(
                    "assessment_count",
                    0
                )
            )
        )

        daily_countries = daily.get(
            "countries",
            {}
        )

        for country in country_scores:

            country_data = daily_countries.get(
                country,
                {}
            )

            country_scores[
                country
            ].append(
                safe_round(
                    country_data.get(
                        "average_score",
                        0
                    )
                )
            )

        daily_hotspot = daily.get(
            "hotspot",
            {}
        )

        daily_hotspots.append({
            "location":
                daily_hotspot.get(
                    "location"
                ),

            "score":
                safe_int(
                    daily_hotspot.get(
                        "score",
                        0
                    )
                ),

            "event_count":
                safe_int(
                    daily_hotspot.get(
                        "event_count",
                        0
                    )
                )
        })

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

        rolling_average = safe_round(
            rolling_overall.get(
                "average_score",
                0
            )
        )

        rolling_threat_index.append(
            rolling_average
        )

        rolling_level.append(
            rolling_overall.get(
                "overall_level",
                level_from_score(
                    rolling_average
                )
            )
        )

        rolling_countries = rolling.get(
            "countries",
            {}
        )

        for country in rolling_country_scores:

            country_data = rolling_countries.get(
                country,
                {}
            )

            rolling_country_scores[
                country
            ].append(
                safe_round(
                    country_data.get(
                        "average_score",
                        0
                    )
                )
            )

        rolling_hotspot = rolling.get(
            "hotspot",
            {}
        )

        rolling_hotspots.append({
            "location":
                rolling_hotspot.get(
                    "location"
                ),

            "score":
                safe_int(
                    rolling_hotspot.get(
                        "score",
                        0
                    )
                ),

            "event_count":
                safe_int(
                    rolling_hotspot.get(
                        "event_count",
                        0
                    )
                )
        })

    if not labels:

        summary = normalize_summary(
            scored
        )

        current_date = (
            datetime.now(
                timezone.utc
            )
            .date()
            .isoformat()
        )

        labels = [
            current_date
        ]

        daily_threat_index = [
            summary[
                "threat_index"
            ]
        ]

        daily_level = [
            summary[
                "threat_level"
            ]
        ]

        rolling_threat_index = [
            summary[
                "threat_index"
            ]
        ]

        rolling_level = [
            summary[
                "threat_level"
            ]
        ]

        incident_count = [
            summary[
                "incident_count"
            ]
        ]

        activity_count = [
            summary[
                "activity_count"
            ]
        ]

        indicator_count = [
            summary[
                "indicator_count"
            ]
        ]

        assessment_count = [
            summary[
                "assessment_count"
            ]
        ]

        cards = build_country_cards(
            scored
        )

        for country in country_scores:

            score = next(
                (
                    card[
                        "average_score"
                    ]
                    for card in cards
                    if card[
                        "country"
                    ] == country
                ),
                0
            )

            country_scores[
                country
            ] = [
                score
            ]

            rolling_country_scores[
                country
            ] = [
                score
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

    return {
        "labels":
            labels,

        "threat_index":
            daily_threat_index,

        "daily_threat_index":
            daily_threat_index,

        "daily_level":
            daily_level,

        "rolling_threat_index":
            rolling_threat_index,

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
            (
                history
                .get(
                    "method",
                    {}
                )
                .get(
                    "rolling_days",
                    14
                )
                if isinstance(
                    history,
                    dict
                )
                else 14
            )
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
            "Baltic Dashboard Data v1.3",

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
                "Historical daily activity calculation",
                "14-day rolling threat calculation",
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
                        "Exact calendar-day activity calculated "
                        "from events published on that date."
                    ),

                "rolling_threat":
                    (
                        "Fourteen-day rolling threat environment "
                        "ending on each calendar date."
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
