import json
import re
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


# ============================================================
# BALTIC HYBRID MONITOR
# Threat Score Engine v3.2
# ============================================================

ENGINE_VERSION = "threat_score_v3_2_current_historical_split"
CURRENT_WINDOW_DAYS = 14


ROOT = Path(__file__).resolve().parents[1]

INPUT_FILE = ROOT / "data" / "baltic_hybrid_clustered_events.json"
OUTPUT_FILE = ROOT / "data" / "baltic_hybrid_scored_news.json"
DOCS_OUTPUT_FILE = ROOT / "docs" / "data" / "baltic_hybrid_scored_news.json"


# ============================================================
# THREAT LEVELS
# ============================================================

THREAT_LEVELS = {
    "low": (0, 19),
    "guarded": (20, 39),
    "elevated": (40, 59),
    "high": (60, 79),
    "critical": (80, 100),
}


# ============================================================
# CATEGORY WEIGHTS
# ============================================================

CATEGORY_WEIGHTS = {
    "sabotage": 18,
    "critical_infrastructure": 17,
    "drone_incident": 16,
    "gps_interference": 15,
    "cyber": 14,
    "espionage": 13,
    "military_provocation": 12,
    "border_pressure": 10,
    "migration_pressure": 8,
    "disinformation": 7,
}


# ============================================================
# SUBTYPE WEIGHTS
# ============================================================

SUBTYPE_WEIGHTS = {
    "incident": 1.00,
    "activity": 0.60,
    "indicator": 0.30,
    "assessment": 0.00,
}


# ============================================================
# CONFIDENCE MULTIPLIERS
# ============================================================

CONFIDENCE_MULTIPLIERS = {
    "very_high": 1.15,
    "high": 1.08,
    "medium": 1.00,
    "low": 0.88,
}


# ============================================================
# ACTOR WEIGHTS
# ============================================================

ACTOR_WEIGHTS = {
    "Russia": 8,
    "Belarus": 6,
    "GRU": 9,
    "FSB": 9,
    "Sandworm": 9,
    "NATO": 3,
    "EU": 1,
}


# ============================================================
# LOCATION WEIGHTS
# ============================================================

LOCATION_WEIGHTS = {
    "Kaliningrad": 8,
    "Suwalki Gap": 9,
    "Baltic Sea": 6,
    "Belarus Border": 7,
    "Poland-Belarus Border": 8,
    "Narva": 5,
    "Riga": 3,
    "Tallinn": 3,
    "Vilnius": 3,
    "Klaipeda": 4,
    "Gdansk": 4,
}


# ============================================================
# GEOGRAPHIC MULTIPLIERS
# ============================================================

GEOGRAPHIC_MULTIPLIERS = {
    "direct": 1.00,
    "regional_direct": 0.85,
    "external_context": 0.55,
}


DIRECT_COUNTRIES = {
    "Estonia",
    "Latvia",
    "Lithuania",
    "Poland",
}


STRATEGIC_REGIONAL_LOCATIONS = {
    "Kaliningrad",
    "Suwalki Gap",
    "Baltic Sea",
    "Belarus Border",
    "Poland-Belarus Border",
    "Narva",
    "Riga",
    "Tallinn",
    "Vilnius",
    "Klaipeda",
    "Gdansk",
}


BALTIC_CONTEXT_TERMS = [
    "baltic",
    "baltic sea",
    "baltic states",
    "estonia",
    "estonian",
    "latvia",
    "latvian",
    "lithuania",
    "lithuanian",
    "poland",
    "polish",
    "kaliningrad",
    "suwalki",
    "suwałki",
    "eastern flank",
]


EXTERNAL_CONTEXT_TERMS = [
    "romania",
    "romanian",
    "germany",
    "german",
    "france",
    "french",
    "italy",
    "italian",
    "spain",
    "spanish",
    "netherlands",
    "dutch",
    "belgium",
    "belgian",
    "united kingdom",
    "british",
    "sweden",
    "swedish",
    "finland",
    "finnish",
    "across europe",
    "throughout europe",
    "in europe",
]


# ============================================================
# ESCALATION TERMS
# ============================================================

CRITICAL_TERMS = [
    "airspace violation",
    "missile incursion",
    "missile strike",
    "drone attack",
    "hybrid attack",
    "arson attack",
    "explosive device",
    "pipeline explosion",
    "undersea cable attack",
    "subsea cable attack",
    "ransomware attack",
    "wiper attack",
]


HIGH_TERMS = [
    "cyberattack",
    "cyber attack",
    "ddos attack",
    "gps jamming",
    "gnss jamming",
    "gps spoofing",
    "gnss spoofing",
    "border breach",
    "border incident",
    "military provocation",
    "airspace incursion",
    "fighter jet interception",
    "sabotage attack",
    "sabotage operation",
    "disinformation campaign",
]


MEDIUM_TERMS = [
    "warning",
    "warns",
    "warned",
    "threat",
    "risk",
    "false flag",
    "military exercise",
    "military drills",
    "preparedness",
    "raised readiness",
    "eastern flank",
]


# ============================================================
# PRECAUTIONARY / NO-INCIDENT TERMS
# ============================================================

NO_INCIDENT_TERMS = [
    "no airspace violation",
    "no violation reported",
    "no airspace incursion",
    "no incursion reported",
    "did not violate polish airspace",
    "did not enter polish airspace",
    "without entering polish airspace",
    "no border violation",
    "no increased threat",
    "no immediate military threat",
    "no signs of attack",
]


PRECAUTIONARY_TERMS = [
    "scrambles fighter jets",
    "scrambled fighter jets",
    "fighter jets scrambled",
    "aircraft were scrambled",
    "raised readiness",
    "increased readiness",
    "precautionary deployment",
    "precautionary measure",
]


# ============================================================
# ATTRIBUTION TERMS
# ============================================================

ATTRIBUTION_CONFIRMED_TERMS = [
    "attributed to russia",
    "attributed to belarus",
    "blames russia",
    "blamed russia",
    "blames belarus",
    "blamed belarus",
    "confirmed russian",
    "confirmed belarusian",
]


ATTRIBUTION_LIKELY_TERMS = [
    "highly likely",
    "likely russian",
    "russian-linked",
    "russia-linked",
    "belarus-linked",
]


ATTRIBUTION_POSSIBLE_TERMS = [
    "suspected russian",
    "possible russian",
    "possibly russian",
    "may be russian",
    "could be russian",
    "suspected involvement",
    "possible involvement",
]


# ============================================================
# BASIC HELPERS
# ============================================================

def normalize(text: Any) -> str:
    value = str(text or "").lower()

    value = re.sub(
        r"[^a-z0-9áéíóöőúüűąćęłńśźż\- /]+",
        " ",
        value,
    )

    value = re.sub(
        r"\s+",
        " ",
        value,
    )

    return value.strip()


def contains_term(text: str, term: str) -> bool:
    normalized_text = normalize(text)
    normalized_term = normalize(term)

    if not normalized_term:
        return False

    pattern = (
        r"(?<!\w)"
        + re.escape(normalized_term)
        + r"(?!\w)"
    )

    return bool(
        re.search(
            pattern,
            normalized_text,
            flags=re.UNICODE,
        )
    )


def contains_any(text: str, terms: List[str]) -> bool:
    return any(
        contains_term(text, term)
        for term in terms
    )


def parse_datetime(value: Any) -> Optional[datetime]:
    if not value:
        return None

    text = str(value).strip()

    if not text:
        return None

    try:
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"

        parsed = datetime.fromisoformat(text)

        if parsed.tzinfo is None:
            parsed = parsed.replace(
                tzinfo=timezone.utc
            )

        return parsed.astimezone(timezone.utc)

    except (TypeError, ValueError):
        return None


def natural_text(event: Dict[str, Any]) -> str:
    return " ".join(
        [
            str(event.get("title", "")),
            str(event.get("summary", "")),
        ]
    )


def classify_level(score: float) -> str:
    if score >= 80:
        return "critical"

    if score >= 60:
        return "high"

    if score >= 40:
        return "elevated"

    if score >= 20:
        return "guarded"

    return "low"


# ============================================================
# INPUT / OUTPUT
# ============================================================

def load_input() -> Dict[str, Any]:
    if not INPUT_FILE.exists():
        raise FileNotFoundError(
            f"Input file not found: {INPUT_FILE}"
        )

    with INPUT_FILE.open(
        "r",
        encoding="utf-8",
    ) as handle:
        return json.load(handle)


def save_json(
    path: Path,
    payload: Dict[str, Any],
) -> None:
    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with path.open(
        "w",
        encoding="utf-8",
    ) as handle:
        json.dump(
            payload,
            handle,
            ensure_ascii=False,
            indent=2,
        )


# ============================================================
# SCORE COMPONENTS
# ============================================================

def calculate_keyword_score(text: str) -> int:
    score = 0

    for term in CRITICAL_TERMS:
        if contains_term(text, term):
            score += 8

    for term in HIGH_TERMS:
        if contains_term(text, term):
            score += 5

    for term in MEDIUM_TERMS:
        if contains_term(text, term):
            score += 2

    return score


def calculate_category_score(categories: List[str]) -> int:
    return sum(
        CATEGORY_WEIGHTS.get(category, 0)
        for category in categories
    )


def calculate_actor_score(actors: List[str]) -> int:
    return sum(
        ACTOR_WEIGHTS.get(actor, 0)
        for actor in actors
    )


def calculate_location_score(locations: List[str]) -> int:
    return sum(
        LOCATION_WEIGHTS.get(location, 0)
        for location in locations
    )


def calculate_source_confirmation(
    event: Dict[str, Any],
) -> int:
    source_count = int(
        event.get("source_count", 1) or 1
    )

    related_count = int(
        event.get("related_item_count", 1) or 1
    )

    confidence_score = int(
        event.get("confidence_score", 0) or 0
    )

    groups = event.get("source_groups", [])

    if not isinstance(groups, list):
        groups = []

    normalized_groups = {
        str(group)
        for group in groups
        if group is not None
    }

    score = min(source_count, 5) * 3

    if related_count >= 2:
        score += 1

    if related_count >= 4:
        score += 1

    if related_count >= 7:
        score += 1

    if len(normalized_groups) >= 2:
        score += 2

    if len(normalized_groups) >= 3:
        score += 2

    if confidence_score >= 80:
        score += 6

    elif confidence_score >= 65:
        score += 4

    elif confidence_score >= 50:
        score += 2

    return score


def calculate_strategic_modifier(
    event: Dict[str, Any],
) -> int:
    categories = set(
        event.get("categories", [])
    )

    actors = set(
        event.get("actors", [])
    )

    locations = set(
        event.get("locations", [])
    )

    modifier = 0

    if "Russia" in actors and "NATO" in actors:
        modifier += 5

    if (
        "Belarus" in actors
        and (
            "border_pressure" in categories
            or "migration_pressure" in categories
        )
    ):
        modifier += 5

    if (
        "Kaliningrad" in locations
        and "gps_interference" in categories
    ):
        modifier += 6

    if "Suwalki Gap" in locations:
        modifier += 7

    if (
        "Baltic Sea" in locations
        and "critical_infrastructure" in categories
    ):
        modifier += 6

    if (
        "cyber" in categories
        and "critical_infrastructure" in categories
    ):
        modifier += 5

    return modifier


# ============================================================
# GEOGRAPHIC SCOPE
# ============================================================

def determine_geographic_scope(
    event: Dict[str, Any],
) -> str:
    primary_country = str(
        event.get(
            "primary_country",
            "Regional",
        )
    )

    countries = set(
        event.get("countries", [])
    )

    locations = set(
        event.get("locations", [])
    )

    text = natural_text(event)

    if primary_country in DIRECT_COUNTRIES:
        return "direct"

    if countries & DIRECT_COUNTRIES:
        return "direct"

    if locations & STRATEGIC_REGIONAL_LOCATIONS:
        return "regional_direct"

    if contains_any(
        text,
        BALTIC_CONTEXT_TERMS,
    ):
        return "regional_direct"

    if contains_any(
        text,
        EXTERNAL_CONTEXT_TERMS,
    ):
        return "external_context"

    return "external_context"


# ============================================================
# INCIDENT CONTEXT
# ============================================================

def calculate_incident_context_multiplier(
    event: Dict[str, Any],
) -> Tuple[float, List[str]]:
    text = natural_text(event)

    multiplier = 1.0
    reasons: List[str] = []

    no_incident = contains_any(
        text,
        NO_INCIDENT_TERMS,
    )

    precautionary = contains_any(
        text,
        PRECAUTIONARY_TERMS,
    )

    if no_incident:
        multiplier *= 0.70
        reasons.append(
            "explicit_no_confirmed_incident"
        )

    if precautionary and no_incident:
        multiplier *= 0.70
        reasons.append(
            "precautionary_response_without_incident"
        )

    elif precautionary:
        multiplier *= 0.90
        reasons.append(
            "precautionary_response"
        )

    return round(multiplier, 3), reasons


# ============================================================
# ATTRIBUTION
# ============================================================

def determine_attribution(
    event: Dict[str, Any],
) -> Dict[str, Any]:
    text = natural_text(event)

    actors = set(
        event.get("actors", [])
    )

    hostile_actors = actors & {
        "Russia",
        "Belarus",
        "GRU",
        "FSB",
        "Sandworm",
    }

    if not hostile_actors:
        return {
            "status": "unattributed",
            "actors": [],
            "confidence": 0.0,
        }

    if contains_any(
        text,
        ATTRIBUTION_CONFIRMED_TERMS,
    ):
        return {
            "status": "confirmed",
            "actors": sorted(hostile_actors),
            "confidence": 1.0,
        }

    if contains_any(
        text,
        ATTRIBUTION_LIKELY_TERMS,
    ):
        return {
            "status": "highly_likely",
            "actors": sorted(hostile_actors),
            "confidence": 0.9,
        }

    if contains_any(
        text,
        ATTRIBUTION_POSSIBLE_TERMS,
    ):
        return {
            "status": "possible",
            "actors": sorted(hostile_actors),
            "confidence": 0.6,
        }

    return {
        "status": "probable",
        "actors": sorted(hostile_actors),
        "confidence": 0.75,
    }


# ============================================================
# EVENT SCORING
# ============================================================

def score_event(
    original_event: Dict[str, Any],
) -> Dict[str, Any]:
    event = dict(original_event)

    text = natural_text(event)

    subtype = str(
        event.get(
            "event_subtype",
            "assessment",
        )
    )

    confidence = str(
        event.get(
            "confidence",
            "low",
        )
    )

    relevance_score = int(
        round(
            float(
                event.get(
                    "relevance_score",
                    0,
                )
                or 0
            )
        )
    )

    keyword_score = calculate_keyword_score(text)

    category_score = calculate_category_score(
        event.get("categories", [])
    )

    actor_score = calculate_actor_score(
        event.get("actors", [])
    )

    location_score = calculate_location_score(
        event.get("locations", [])
    )

    confirmation_score = calculate_source_confirmation(
        event
    )

    strategic_modifier = calculate_strategic_modifier(
        event
    )

    raw_base_score = (
        relevance_score
        + keyword_score
        + category_score
        + actor_score
        + location_score
        + confirmation_score
        + strategic_modifier
    )

    raw_base_score = max(
        raw_base_score,
        0,
    )

    subtype_weight = SUBTYPE_WEIGHTS.get(
        subtype,
        0.0,
    )

    confidence_multiplier = (
        CONFIDENCE_MULTIPLIERS.get(
            confidence,
            0.88,
        )
    )

    geographic_scope = determine_geographic_scope(
        event
    )

    geographic_multiplier = (
        GEOGRAPHIC_MULTIPLIERS.get(
            geographic_scope,
            0.55,
        )
    )

    (
        context_multiplier,
        context_reasons,
    ) = calculate_incident_context_multiplier(
        event
    )

    weighted_score = (
        raw_base_score
        * subtype_weight
        * confidence_multiplier
        * geographic_multiplier
        * context_multiplier
    )

    if subtype == "assessment":
        weighted_score = 0.0

    weighted_score = min(
        max(weighted_score, 0.0),
        100.0,
    )

    final_score = int(
        round(weighted_score)
    )

    attribution = determine_attribution(
        event
    )

    event["geographic_scope"] = geographic_scope
    event["geographic_multiplier"] = geographic_multiplier
    event["attribution"] = attribution
    event["hybrid_threat_score"] = final_score
    event["hybrid_threat_level"] = classify_level(
        final_score
    )

    event["score_breakdown"] = {
        "raw_base_score": raw_base_score,
        "relevance": relevance_score,
        "keywords": keyword_score,
        "categories": category_score,
        "actors": actor_score,
        "locations": location_score,
        "source_confirmation": confirmation_score,
        "strategic_modifier": strategic_modifier,
        "event_subtype": subtype,
        "subtype_weight": subtype_weight,
        "confidence": confidence,
        "confidence_multiplier": confidence_multiplier,
        "geographic_scope": geographic_scope,
        "geographic_multiplier": geographic_multiplier,
        "incident_context_multiplier": context_multiplier,
        "incident_context_reasons": context_reasons,
        "attribution": attribution,
        "weighted_score": round(
            weighted_score,
            2,
        ),
    }

    return event


# ============================================================
# CURRENT WINDOW
# ============================================================

def get_current_window_bounds(
    reference_datetime: datetime,
) -> Tuple[datetime, datetime]:
    reference_date = (
        reference_datetime
        .astimezone(timezone.utc)
        .date()
    )

    start_date = (
        reference_date
        - timedelta(
            days=CURRENT_WINDOW_DAYS - 1
        )
    )

    start_datetime = datetime(
        start_date.year,
        start_date.month,
        start_date.day,
        0,
        0,
        0,
        tzinfo=timezone.utc,
    )

    end_datetime = datetime(
        reference_date.year,
        reference_date.month,
        reference_date.day,
        23,
        59,
        59,
        999999,
        tzinfo=timezone.utc,
    )

    return start_datetime, end_datetime


def filter_current_window(
    events: List[Dict[str, Any]],
    reference_datetime: datetime,
) -> List[Dict[str, Any]]:
    (
        start_datetime,
        end_datetime,
    ) = get_current_window_bounds(
        reference_datetime
    )

    current_events = []

    for event in events:
        published_at = parse_datetime(
            event.get("published_at")
        )

        if published_at is None:
            continue

        if (
            start_datetime
            <= published_at
            <= end_datetime
        ):
            current_events.append(
                event
            )

    return current_events


# ============================================================
# INDEX
# ============================================================

def average_top_scores(
    events: List[Dict[str, Any]],
    limit: int,
) -> float:
    if not events:
        return 0.0

    scores = sorted(
        [
            int(
                event.get(
                    "hybrid_threat_score",
                    0,
                )
            )
            for event in events
        ],
        reverse=True,
    )

    selected = scores[:limit]

    if not selected:
        return 0.0

    return round(
        sum(selected) / len(selected),
        2,
    )


def build_current_summary(
    events: List[Dict[str, Any]],
) -> Dict[str, Any]:
    incidents = [
        event
        for event in events
        if event.get("event_subtype") == "incident"
    ]

    activities = [
        event
        for event in events
        if event.get("event_subtype") == "activity"
    ]

    indicators = [
        event
        for event in events
        if event.get("event_subtype") == "indicator"
    ]

    assessments = [
        event
        for event in events
        if event.get("event_subtype") == "assessment"
    ]

    operational_events = (
        incidents
        + activities
    )

    operational_index = average_top_scores(
        operational_events,
        5,
    )

    early_warning_index = average_top_scores(
        indicators,
        8,
    )

    if operational_events:
        threat_index = round(
            operational_index * 0.80
            + early_warning_index * 0.20,
            2,
        )
    else:
        threat_index = round(
            early_warning_index,
            2,
        )

    threat_index = min(
        max(threat_index, 0),
        100,
    )

    scored_events = [
        event
        for event in events
        if event.get("event_subtype")
        != "assessment"
    ]

    score_total = sum(
        int(
            event.get(
                "hybrid_threat_score",
                0,
            )
        )
        for event in events
    )

    average_score = (
        round(
            sum(
                int(
                    event.get(
                        "hybrid_threat_score",
                        0,
                    )
                )
                for event in scored_events
            )
            / len(scored_events),
            2,
        )
        if scored_events
        else 0.0
    )

    highest_score = max(
        [
            int(
                event.get(
                    "hybrid_threat_score",
                    0,
                )
            )
            for event in events
        ],
        default=0,
    )

    return {
        "event_count": len(events),
        "incident_count": len(incidents),
        "activity_count": len(activities),
        "indicator_count": len(indicators),
        "assessment_count": len(assessments),
        "score_total": score_total,
        "average_score": average_score,
        "highest_score": highest_score,
        "operational_index": operational_index,
        "early_warning_index": early_warning_index,
        "threat_index": threat_index,
        "overall_level": classify_level(
            threat_index
        ),
    }


def build_historical_summary(
    events: List[Dict[str, Any]],
) -> Dict[str, Any]:
    incident_count = 0
    activity_count = 0
    indicator_count = 0
    assessment_count = 0

    score_total = 0
    highest_score = 0
    scored_count = 0

    for event in events:
        subtype = event.get(
            "event_subtype"
        )

        score = int(
            event.get(
                "hybrid_threat_score",
                0,
            )
        )

        score_total += score
        highest_score = max(
            highest_score,
            score,
        )

        if subtype == "incident":
            incident_count += 1
            scored_count += 1

        elif subtype == "activity":
            activity_count += 1
            scored_count += 1

        elif subtype == "indicator":
            indicator_count += 1
            scored_count += 1

        else:
            assessment_count += 1

    average_score = (
        round(
            score_total / scored_count,
            2,
        )
        if scored_count
        else 0.0
    )

    return {
        "event_count": len(events),
        "incident_count": incident_count,
        "activity_count": activity_count,
        "indicator_count": indicator_count,
        "assessment_count": assessment_count,
        "score_total": score_total,
        "average_score": average_score,
        "highest_score": highest_score,
    }


# ============================================================
# SUMMARY BUILDERS
# ============================================================

def build_country_summary(
    events: List[Dict[str, Any]],
) -> Dict[str, Any]:
    countries = [
        "Estonia",
        "Latvia",
        "Lithuania",
        "Poland",
        "Regional",
    ]

    summary = {}

    for country in countries:
        summary[country] = {
            "country": country,
            "event_count": 0,
            "incident_count": 0,
            "activity_count": 0,
            "indicator_count": 0,
            "assessment_count": 0,
            "score_total": 0,
            "average_score": 0.0,
            "highest_score": 0,
            "level": "low",
            "categories": {},
            "actors": {},
        }

    for event in events:
        country = event.get(
            "primary_country",
            "Regional",
        )

        if country not in summary:
            country = "Regional"

        data = summary[country]

        subtype = event.get(
            "event_subtype",
            "assessment",
        )

        score = int(
            event.get(
                "hybrid_threat_score",
                0,
            )
        )

        data["event_count"] += 1
        data["score_total"] += score
        data["highest_score"] = max(
            data["highest_score"],
            score,
        )

        key = (
            subtype + "_count"
            if subtype in {
                "incident",
                "activity",
                "indicator",
                "assessment",
            }
            else "assessment_count"
        )

        data[key] += 1

        for category in event.get(
            "categories",
            [],
        ):
            data["categories"][category] = (
                data["categories"].get(
                    category,
                    0,
                )
                + 1
            )

        for actor in event.get(
            "actors",
            [],
        ):
            data["actors"][actor] = (
                data["actors"].get(
                    actor,
                    0,
                )
                + 1
            )

    for data in summary.values():
        scored_count = (
            data["incident_count"]
            + data["activity_count"]
            + data["indicator_count"]
        )

        if scored_count:
            data["average_score"] = round(
                data["score_total"]
                / scored_count,
                2,
            )

        data["level"] = classify_level(
            data["average_score"]
        )

    return summary


def build_category_summary(
    events: List[Dict[str, Any]],
) -> Dict[str, Any]:
    summary = {}

    for event in events:
        score = int(
            event.get(
                "hybrid_threat_score",
                0,
            )
        )

        for category in event.get(
            "categories",
            [],
        ):
            if category not in summary:
                summary[category] = {
                    "category": category,
                    "event_count": 0,
                    "score_total": 0,
                    "average_score": 0.0,
                    "highest_score": 0,
                }

            data = summary[category]

            data["event_count"] += 1
            data["score_total"] += score
            data["highest_score"] = max(
                data["highest_score"],
                score,
            )

    for data in summary.values():
        if data["event_count"]:
            data["average_score"] = round(
                data["score_total"]
                / data["event_count"],
                2,
            )

    return dict(
        sorted(
            summary.items(),
            key=lambda item: item[1][
                "score_total"
            ],
            reverse=True,
        )
    )


def build_actor_summary(
    events: List[Dict[str, Any]],
) -> Dict[str, Any]:
    summary = {}

    for event in events:
        score = int(
            event.get(
                "hybrid_threat_score",
                0,
            )
        )

        for actor in event.get(
            "actors",
            [],
        ):
            if actor not in summary:
                summary[actor] = {
                    "actor": actor,
                    "event_count": 0,
                    "score_total": 0,
                    "average_score": 0.0,
                    "highest_score": 0,
                }

            data = summary[actor]

            data["event_count"] += 1
            data["score_total"] += score
            data["highest_score"] = max(
                data["highest_score"],
                score,
            )

    for data in summary.values():
        if data["event_count"]:
            data["average_score"] = round(
                data["score_total"]
                / data["event_count"],
                2,
            )

    return dict(
        sorted(
            summary.items(),
            key=lambda item: item[1][
                "score_total"
            ],
            reverse=True,
        )
    )


def build_subtype_summary(
    events: List[Dict[str, Any]],
) -> Dict[str, Any]:
    summary = {
        "incident": {
            "event_count": 0,
            "score_total": 0,
            "average_score": 0.0,
        },
        "activity": {
            "event_count": 0,
            "score_total": 0,
            "average_score": 0.0,
        },
        "indicator": {
            "event_count": 0,
            "score_total": 0,
            "average_score": 0.0,
        },
        "assessment": {
            "event_count": 0,
            "score_total": 0,
            "average_score": 0.0,
        },
    }

    for event in events:
        subtype = event.get(
            "event_subtype",
            "assessment",
        )

        if subtype not in summary:
            subtype = "assessment"

        score = int(
            event.get(
                "hybrid_threat_score",
                0,
            )
        )

        summary[subtype][
            "event_count"
        ] += 1

        summary[subtype][
            "score_total"
        ] += score

    for data in summary.values():
        if data["event_count"]:
            data["average_score"] = round(
                data["score_total"]
                / data["event_count"],
                2,
            )

    return summary


def build_scope_summary(
    events: List[Dict[str, Any]],
) -> Dict[str, Any]:
    summary = {
        "direct": {
            "event_count": 0,
            "score_total": 0,
            "average_score": 0.0,
        },
        "regional_direct": {
            "event_count": 0,
            "score_total": 0,
            "average_score": 0.0,
        },
        "external_context": {
            "event_count": 0,
            "score_total": 0,
            "average_score": 0.0,
        },
    }

    for event in events:
        scope = event.get(
            "geographic_scope",
            "external_context",
        )

        if scope not in summary:
            scope = "external_context"

        score = int(
            event.get(
                "hybrid_threat_score",
                0,
            )
        )

        summary[scope][
            "event_count"
        ] += 1

        summary[scope][
            "score_total"
        ] += score

    for data in summary.values():
        if data["event_count"]:
            data["average_score"] = round(
                data["score_total"]
                / data["event_count"],
                2,
            )

    return summary


# ============================================================
# MAIN
# ============================================================

def main() -> None:
    print(
        f"Threat Score Engine: "
        f"{ENGINE_VERSION}"
    )

    source_data = load_input()

    source_events = source_data.get(
        "events",
        [],
    )

    if not isinstance(
        source_events,
        list,
    ):
        raise ValueError(
            "Input JSON field 'events' "
            "must be a list."
        )

    scored_events = [
        score_event(event)
        for event in source_events
    ]

    scored_events.sort(
        key=lambda event: (
            int(
                event.get(
                    "hybrid_threat_score",
                    0,
                )
            ),
            int(
                event.get(
                    "confidence_score",
                    0,
                )
            ),
            str(
                event.get(
                    "published_at",
                    "",
                )
            ),
        ),
        reverse=True,
    )

    reference_datetime = datetime.now(
        timezone.utc
    )

    (
        window_start,
        window_end,
    ) = get_current_window_bounds(
        reference_datetime
    )

    current_events = filter_current_window(
        scored_events,
        reference_datetime,
    )

    current_summary = build_current_summary(
        current_events
    )

    historical_summary = build_historical_summary(
        scored_events
    )

    current_country_summary = build_country_summary(
        current_events
    )

    current_category_summary = build_category_summary(
        current_events
    )

    current_actor_summary = build_actor_summary(
        current_events
    )

    current_subtype_summary = build_subtype_summary(
        current_events
    )

    current_scope_summary = build_scope_summary(
        current_events
    )

    historical_summaries = {
        "country_summary": build_country_summary(
            scored_events
        ),
        "category_summary": build_category_summary(
            scored_events
        ),
        "actor_summary": build_actor_summary(
            scored_events
        ),
        "subtype_summary": build_subtype_summary(
            scored_events
        ),
        "scope_summary": build_scope_summary(
            scored_events
        ),
    }

    payload = {
        "project": source_data.get(
            "project",
            "baltic-hybrid-monitor",
        ),

        "region": source_data.get(
            "region",
            "Baltic states and Poland",
        ),

        "generated_at": reference_datetime.isoformat(),

        "input_generated_at": source_data.get(
            "generated_at"
        ),

        "raw_item_count": source_data.get(
            "raw_item_count"
        ),

        "filtered_item_count": source_data.get(
            "filtered_item_count"
        ),

        "clustered_event_count": source_data.get(
            "event_count",
            len(source_events),
        ),

        "merged_item_count": source_data.get(
            "merged_item_count"
        ),

        "engine_version": ENGINE_VERSION,

        "current_threat_window": {
            "window_days": CURRENT_WINDOW_DAYS,
            "window_type": "calendar_days",
            "reference_date": (
                reference_datetime
                .date()
                .isoformat()
            ),
            "start_date": (
                window_start
                .date()
                .isoformat()
            ),
            "end_date": (
                window_end
                .date()
                .isoformat()
            ),
            "event_count": len(
                current_events
            ),
            "rule": (
                "Current threat indices and current "
                "summary blocks use only events "
                "published inside the latest 14 UTC "
                "calendar days. Historical events "
                "remain scored and stored separately."
            ),
        },

        "method": {
            "description": (
                "Threat Score Engine v3.2. "
                "All clustered events are scored and "
                "preserved historically. Current threat "
                "indices and top-level summaries use "
                "only the latest 14 UTC calendar days. "
                "Full-history summaries are stored in "
                "historical_summaries."
            ),

            "classification_version": ENGINE_VERSION,

            "input": (
                "data/"
                "baltic_hybrid_clustered_events.json"
            ),

            "current_window_days": CURRENT_WINDOW_DAYS,

            "score_components": [
                "event relevance score",
                "natural-text escalation keywords",
                "threat category weights",
                "actor weights",
                "strategic location weights",
                "independent source confirmation",
                "strategic modifiers",
                "event subtype weighting",
                "confidence multiplier",
                "geographic scope multiplier",
                "precautionary-response correction",
            ],

            "index_method": {
                "time_scope": (
                    "Latest 14 UTC calendar days."
                ),
                "operational_index": (
                    "Average of the five highest "
                    "scoring current incident/activity "
                    "events."
                ),
                "early_warning_index": (
                    "Average of the eight highest "
                    "scoring current indicator events."
                ),
                "threat_index": (
                    "80% Operational Index + 20% "
                    "Early Warning Index when current "
                    "operational events exist. "
                    "Otherwise the Early Warning Index."
                ),
                "current_summaries": (
                    "Top-level country, category, actor, "
                    "subtype and scope summaries use the "
                    "same current 14-day event window."
                ),
                "historical_retention": (
                    "Historical events remain in the "
                    "scored dataset and historical "
                    "summaries without retention loss."
                ),
            },

            "subtype_weights": SUBTYPE_WEIGHTS,
            "confidence_multipliers": (
                CONFIDENCE_MULTIPLIERS
            ),
            "geographic_multipliers": (
                GEOGRAPHIC_MULTIPLIERS
            ),

            "levels": {
                "low": "0-19",
                "guarded": "20-39",
                "elevated": "40-59",
                "high": "60-79",
                "critical": "80+",
            },
        },

        # CURRENT 14-DAY DATA
        "overall_summary": current_summary,

        "country_summary": (
            current_country_summary
        ),

        "category_summary": (
            current_category_summary
        ),

        "actor_summary": (
            current_actor_summary
        ),

        "subtype_summary": (
            current_subtype_summary
        ),

        "scope_summary": (
            current_scope_summary
        ),

        # HISTORICAL DATA
        "historical_summary": (
            historical_summary
        ),

        "historical_summaries": (
            historical_summaries
        ),

        # CURRENT EVENTS
        "current_events": (
            current_events
        ),

        # COMPLETE HISTORICAL EVENT STORE
        "items": (
            scored_events
        ),

        "events": (
            scored_events
        ),
    }

    save_json(
        OUTPUT_FILE,
        payload,
    )

    save_json(
        DOCS_OUTPUT_FILE,
        payload,
    )

    print(
        f"Historical events scored: "
        f"{len(scored_events)}"
    )

    print(
        f"Current {CURRENT_WINDOW_DAYS}-day "
        f"events: {len(current_events)}"
    )

    print(
        "Current window: "
        f"{window_start.date().isoformat()} "
        "to "
        f"{window_end.date().isoformat()}"
    )

    print(
        "Operational index: "
        f"{current_summary['operational_index']}"
    )

    print(
        "Early-warning index: "
        f"{current_summary['early_warning_index']}"
    )

    print(
        "Threat index: "
        f"{current_summary['threat_index']}"
    )

    print(
        "Overall level: "
        f"{current_summary['overall_level']}"
    )

    print(
        "Current summaries: "
        f"{len(current_events)} events"
    )

    print(
        "Historical summaries: "
        f"{len(scored_events)} events"
    )

    print(
        f"Saved: {OUTPUT_FILE}"
    )

    print(
        f"Saved: {DOCS_OUTPUT_FILE}"
    )


if __name__ == "__main__":
    main()
