import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Any, Tuple


ROOT = Path(__file__).resolve().parents[1]

CLUSTERED_INPUT = ROOT / "data" / "baltic_hybrid_clustered_events.json"
SCORED_OUTPUT = ROOT / "data" / "baltic_hybrid_scored_news.json"
DOCS_OUTPUT = ROOT / "docs" / "data" / "baltic_hybrid_scored_news.json"


# ---------------------------------------------------------------------
# THREAT SCORE ENGINE v3.0
#
# Design goals:
#
# 1. Keep operational incidents separate from early-warning indicators.
# 2. Avoid double-counting categories as both category and keyword score.
# 3. Give direct Baltic / Polish events more weight than external context.
# 4. Preserve strategically relevant European warning signals.
# 5. Reduce scores for precautionary military reactions where no actual
#    territorial / airspace incident occurred.
# 6. Keep the existing hybrid_threat_score field for dashboard
#    compatibility.
# 7. Add separate operational and early-warning indices.
# ---------------------------------------------------------------------


COUNTRIES = [
    "Estonia",
    "Latvia",
    "Lithuania",
    "Poland",
    "Regional"
]


DIRECT_COUNTRIES = {
    "Estonia",
    "Latvia",
    "Lithuania",
    "Poland"
}


# ---------------------------------------------------------------------
# CATEGORY WEIGHTS
# ---------------------------------------------------------------------


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
    "disinformation": 7
}


# ---------------------------------------------------------------------
# EVENT SUBTYPE WEIGHTS
#
# Indicator remains deliberately much weaker than a confirmed incident.
# Activity represents concrete military/security behaviour but normally
# below a confirmed hostile incident.
# ---------------------------------------------------------------------


SUBTYPE_WEIGHTS = {
    "incident": 1.00,
    "activity": 0.60,
    "indicator": 0.30,
    "assessment": 0.00
}


# ---------------------------------------------------------------------
# CONFIDENCE
# ---------------------------------------------------------------------


CONFIDENCE_MULTIPLIERS = {
    "very_high": 1.15,
    "high": 1.08,
    "medium": 1.00,
    "low": 0.88
}


# ---------------------------------------------------------------------
# ACTORS
#
# NATO and EU remain low-value context actors.
# Hostile-state / intelligence actors receive stronger weighting.
# ---------------------------------------------------------------------


ACTOR_WEIGHTS = {
    "Russia": 8,
    "Belarus": 6,
    "GRU": 9,
    "FSB": 9,
    "Sandworm": 9,
    "NATO": 3,
    "EU": 1
}


# ---------------------------------------------------------------------
# STRATEGIC LOCATIONS
# ---------------------------------------------------------------------


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
    "Gdansk": 4
}


# ---------------------------------------------------------------------
# GEOGRAPHIC SCOPE
#
# direct:
#   concrete Estonia / Latvia / Lithuania / Poland event
#
# regional_direct:
#   Baltic-wide / eastern-flank event without one primary country
#
# external_context:
#   event outside the monitored theatre, useful as warning context
# ---------------------------------------------------------------------


GEOGRAPHIC_MULTIPLIERS = {
    "direct": 1.00,
    "regional_direct": 0.85,
    "external_context": 0.55
}


BALTIC_CONTEXT_TERMS = [
    "baltic",
    "baltics",
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
    "belarus border",
    "belarusian border"
]


EXTERNAL_CONTEXT_TERMS = [
    "romania",
    "romanian",
    "sweden",
    "swedish",
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
    "britain",
    "british",
    "europe",
    "european weapons factories",
    "across europe"
]


# ---------------------------------------------------------------------
# ESCALATION LANGUAGE
#
# IMPORTANT:
# These terms are searched only in the natural title + summary.
# Categories, actors and locations are NOT injected into the keyword
# text. This prevents double-counting.
# ---------------------------------------------------------------------


ESCALATION_TERMS = {
    "critical": [
        "explosion",
        "airspace violation",
        "undersea cable",
        "subsea cable",
        "pipeline explosion",
        "ransomware attack",
        "wiper attack",
        "missile strike",
        "missile incursion",
        "drone attack",
        "hybrid attack",
        "arson attack",
        "explosive device"
    ],

    "high": [
        "cyberattack",
        "cyber attack",
        "ddos attack",
        "gps jamming",
        "gnss jamming",
        "gps spoofing",
        "gnss spoofing",
        "border incident",
        "border breach",
        "military provocation",
        "fighter jet interception",
        "airspace incursion",
        "migration pressure",
        "disinformation campaign",
        "sabotage attack",
        "sabotage operation"
    ],

    "medium": [
        "warning",
        "warns",
        "warned",
        "threat",
        "risk",
        "preparedness",
        "military exercise",
        "military drills",
        "eastern flank",
        "air policing",
        "false flag"
    ]
}


# ---------------------------------------------------------------------
# DE-ESCALATION / PRECAUTIONARY LANGUAGE
# ---------------------------------------------------------------------


NO_INCIDENT_TERMS = [
    "no airspace violation",
    "no violation reported",
    "without entering polish airspace",
    "did not enter polish airspace",
    "did not violate polish airspace",
    "no border violation",
    "no incursion reported",
    "no signs of attack",
    "no signs of russian attack",
    "no immediate military threat",
    "no increased threat",
    "full-scale war is not imminent"
]


PRECAUTIONARY_RESPONSE_TERMS = [
    "scrambles fighter jets",
    "scrambled fighter jets",
    "fighter jets scrambled",
    "aircraft were scrambled",
    "air policing response",
    "precautionary deployment",
    "precautionary measure",
    "raised readiness",
    "increased readiness"
]


# ---------------------------------------------------------------------
# ATTRIBUTION
#
# Attribution is currently informational and deliberately conservative.
# It does not directly erase the severity of a real physical incident.
# ---------------------------------------------------------------------


ATTRIBUTION_UNCERTAIN_TERMS = [
    "suspected russian",
    "possible russian",
    "possibly russian",
    "may be russian",
    "could be russian",
    "alleged russian",
    "russia may",
    "russia could",
    "possible involvement",
    "suspected involvement",
    "sabotage theory"
]


ATTRIBUTION_STRONG_TERMS = [
    "attributed to russia",
    "attributed to belarus",
    "blames russia",
    "blamed russia",
    "blames belarus",
    "blamed belarus",
    "russia carried out",
    "belarus carried out",
    "russian authorities carried out",
    "russian intelligence carried out",
    "confirmed russian",
    "confirmed belarusian"
]


ATTRIBUTION_LIKELY_TERMS = [
    "highly likely",
    "likely russian",
    "likely linked to russia",
    "likely linked to belarus",
    "russian-linked",
    "russia-linked",
    "belarus-linked"
]


# ---------------------------------------------------------------------
# BASIC IO
# ---------------------------------------------------------------------


def load_clustered_data() -> Dict[str, Any]:

    if not CLUSTERED_INPUT.exists():

        raise FileNotFoundError(
            f"Missing clustered input file: {CLUSTERED_INPUT}. "
            "Run scripts/fetch_baltic_hybrid_news.py, "
            "scripts/filter_baltic_hybrid_news.py and "
            "scripts/cluster_baltic_hybrid_events.py first."
        )

    return json.loads(
        CLUSTERED_INPUT.read_text(
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
# TEXT NORMALISATION
# ---------------------------------------------------------------------


def normalize(
    text: str
) -> str:

    text = str(
        text
    ).lower()

    text = re.sub(
        r"[^a-z0-9áéíóöőúüűąćęłńóśźż\- /]+",
        " ",
        text
    )

    text = re.sub(
        r"\s+",
        " ",
        text
    )

    return text.strip()


def contains_term(
    text: str,
    term: str
) -> bool:

    normalized_text = normalize(
        text
    )

    normalized_term = normalize(
        term
    )

    if not normalized_term:
        return False

    pattern = (
        r"(?<!\w)"
        + re.escape(
            normalized_term
        )
        + r"(?!\w)"
    )

    return (
        re.search(
            pattern,
            normalized_text,
            flags=re.UNICODE
        )
        is not None
    )


def contains_any(
    text: str,
    terms: List[str]
) -> bool:

    return any(
        contains_term(
            text,
            term
        )
        for term in terms
    )


# ---------------------------------------------------------------------
# NATURAL EVENT TEXT
#
# Categories / actors / locations deliberately excluded.
# ---------------------------------------------------------------------


def natural_text_blob(
    event: Dict[str, Any]
) -> str:

    return " ".join([
        str(
            event.get(
                "title",
                ""
            )
        ),
        str(
            event.get(
                "summary",
                ""
            )
        )
    ])


# ---------------------------------------------------------------------
# KEYWORD SCORE
# ---------------------------------------------------------------------


def keyword_score(
    text: str
) -> int:

    score = 0

    for term in ESCALATION_TERMS[
        "critical"
    ]:

        if contains_term(
            text,
            term
        ):

            score += 8

    for term in ESCALATION_TERMS[
        "high"
    ]:

        if contains_term(
            text,
            term
        ):

            score += 5

    for term in ESCALATION_TERMS[
        "medium"
    ]:

        if contains_term(
            text,
            term
        ):

            score += 2

    return score


# ---------------------------------------------------------------------
# COMPONENT SCORES
# ---------------------------------------------------------------------


def category_score(
    categories: List[str]
) -> int:

    return sum(
        CATEGORY_WEIGHTS.get(
            category,
            0
        )
        for category
        in categories
    )


def actor_score(
    actors: List[str]
) -> int:

    return sum(
        ACTOR_WEIGHTS.get(
            actor,
            0
        )
        for actor
        in actors
    )


def location_score(
    locations: List[str]
) -> int:

    return sum(
        LOCATION_WEIGHTS.get(
            location,
            0
        )
        for location
        in locations
    )


# ---------------------------------------------------------------------
# SOURCE CONFIRMATION
#
# Multiple distinct sources matter more than multiple related titles
# from the same search/feed.
# ---------------------------------------------------------------------


def source_confirmation_score(
    event: Dict[str, Any]
) -> int:

    source_count = int(
        event.get(
            "source_count",
            1
        )
    )

    related_item_count = int(
        event.get(
            "related_item_count",
            1
        )
    )

    source_groups = event.get(
        "source_groups",
        []
    )

    confidence_score = int(
        event.get(
            "confidence_score",
            0
        )
    )

    score = 0

    # Distinct sources are the strongest confirmation signal.
    score += min(
        source_count,
        5
    ) * 3

    # Related coverage helps, but much less than independent sources.
    if related_item_count >= 2:
        score += 1

    if related_item_count >= 4:
        score += 1

    if related_item_count >= 7:
        score += 1

    # Source-group diversity.
    distinct_groups = len(
        set(
            source_groups
        )
    )

    if distinct_groups >= 2:
        score += 2

    if distinct_groups >= 3:
        score += 2

    # Existing cluster confidence.
    if confidence_score >= 80:

        score += 6

    elif confidence_score >= 65:

        score += 4

    elif confidence_score >= 50:

        score += 2

    return score


# ---------------------------------------------------------------------
# STRATEGIC MODIFIER
# ---------------------------------------------------------------------


def strategic_modifier(
    event: Dict[str, Any]
) -> int:

    categories = set(
        event.get(
            "categories",
            []
        )
    )

    actors = set(
        event.get(
            "actors",
            []
        )
    )

    locations = set(
        event.get(
            "locations",
            []
        )
    )

    modifier = 0

    if (
        "Russia" in actors
        and "NATO" in actors
    ):

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

    if (
        "drone_incident" in categories
        and "military_provocation" in categories
    ):

        modifier += 4

    return modifier


# ---------------------------------------------------------------------
# GEOGRAPHIC SCOPE
# ---------------------------------------------------------------------


def determine_geographic_scope(
    event: Dict[str, Any]
) -> str:

    primary_country = event.get(
        "primary_country",
        "Regional"
    )

    countries = set(
        event.get(
            "countries",
            []
        )
    )

    locations = set(
        event.get(
            "locations",
            []
        )
    )

    text = natural_text_blob(
        event
    )

    # Explicit country assignment is the strongest direct signal.
    if primary_country in DIRECT_COUNTRIES:

        return "direct"

    if countries & DIRECT_COUNTRIES:

        return "direct"

    # Strategic Baltic locations count as direct regional relevance.
    if locations & {
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
        "Gdansk"
    }:

        return "regional_direct"

    # Baltic-wide language without a specific country.
    if contains_any(
        text,
        BALTIC_CONTEXT_TERMS
    ):

        return "regional_direct"

    # Explicit external location/context.
    if contains_any(
        text,
        EXTERNAL_CONTEXT_TERMS
    ):

        return "external_context"

    # Unlocated Regional events remain context rather than direct events.
    if primary_country == "Regional":

        return "external_context"

    return "regional_direct"


# ---------------------------------------------------------------------
# PRECAUTIONARY / NON-INCIDENT MODIFIER
# ---------------------------------------------------------------------


def incident_context_multiplier(
    event: Dict[str, Any]
) -> Tuple[float, List[str]]:

    text = natural_text_blob(
        event
    )

    reasons = []

    multiplier = 1.0

    no_incident = contains_any(
        text,
        NO_INCIDENT_TERMS
    )

    precautionary = contains_any(
        text,
        PRECAUTIONARY_RESPONSE_TERMS
    )

    if no_incident:

        multiplier *= 0.70

        reasons.append(
            "explicit_no_confirmed_incident"
        )

    if (
        precautionary
        and no_incident
    ):

        multiplier *= 0.70

        reasons.append(
            "precautionary_response_without_incursion"
        )

    elif precautionary:

        multiplier *= 0.90

        reasons.append(
            "precautionary_response"
        )

    return (
        round(
            multiplier,
            3
        ),
        reasons
    )


# ---------------------------------------------------------------------
# ATTRIBUTION ASSESSMENT
# ---------------------------------------------------------------------


def assess_attribution(
    event: Dict[str, Any]
) -> Dict[str, Any]:

    text = natural_text_blob(
        event
    )

    actors = set(
        event.get(
            "actors",
            []
        )
    )

    hostile_actors = actors & {
        "Russia",
        "Belarus",
        "GRU",
        "FSB",
        "Sandworm"
    }

    if not hostile_actors:

        return {
            "status":
                "unattributed",

            "actors":
                [],

            "confidence":
                0.0
        }

    if contains_any(
        text,
        ATTRIBUTION_STRONG_TERMS
    ):

        return {
            "status":
                "confirmed",

            "actors":
                sorted(
                    hostile_actors
                ),

            "confidence":
                1.0
        }

    if contains_any(
        text,
        ATTRIBUTION_LIKELY_TERMS
    ):

        return {
            "status":
                "highly_likely",

            "actors":
                sorted(
                    hostile_actors
                ),

            "confidence":
                0.9
        }

    if contains_any(
        text,
        ATTRIBUTION_UNCERTAIN_TERMS
    ):

        return {
            "status":
                "possible",

            "actors":
                sorted(
                    hostile_actors
                ),

            "confidence":
                0.6
        }

    return {
        "status":
            "probable",

        "actors":
            sorted(
                hostile_actors
            ),

        "confidence":
            0.75
    }


# ---------------------------------------------------------------------
# LEVELS
# ---------------------------------------------------------------------


def classify_level(
    score: int
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


# ---------------------------------------------------------------------
# EVENT SCORING
# ---------------------------------------------------------------------


def score_event(
    event: Dict[str, Any]
) -> Dict[str, Any]:

    text = natural_text_blob(
        event
    )

    subtype = event.get(
        "event_subtype",
        "assessment"
    )

    confidence = event.get(
        "confidence",
        "low"
    )

    relevance_component = int(
        round(
            float(
                event.get(
                    "relevance_score",
                    0
                )
            )
        )
    )

    keyword_component = keyword_score(
        text
    )

    category_component = category_score(
        event.get(
            "categories",
            []
        )
    )

    actor_component = actor_score(
        event.get(
            "actors",
            []
        )
    )

    location_component = location_score(
        event.get(
            "locations",
            []
        )
    )

    source_component = source_confirmation_score(
        event
    )

    strategic_component = strategic_modifier(
        event
    )

    base_score = (
        relevance_component
        + keyword_component
        + category_component
        + actor_component
        + location_component
        + source_component
        + strategic_component
    )

    if base_score < 0:

        base_score = 0

    subtype_weight = SUBTYPE_WEIGHTS.get(
        subtype,
        0.0
    )

    confidence_multiplier = CONFIDENCE_MULTIPLIERS.get(
        confidence,
        0.88
    )

    geographic_scope = determine_geographic_scope(
        event
    )

    geographic_multiplier = GEOGRAPHIC_MULTIPLIERS.get(
        geographic_scope,
        0.55
    )

    context_multiplier, context_reasons = (
        incident_context_multiplier(
            event
        )
    )

    weighted_score = (
        base_score
        * subtype_weight
        * confidence_multiplier
        * geographic_multiplier
        * context_multiplier
    )

    weighted_score = round(
        weighted_score,
        2
    )

    if subtype == "assessment":

        weighted_score = 0

    # Individual event score remains on a 0-100 scale.
    weighted_score = min(
        weighted_score,
        100
    )

    final_score = int(
        round(
            weighted_score
        )
    )

    attribution = assess_attribution(
        event
    )

    event[
        "geographic_scope"
    ] = geographic_scope

    event[
        "geographic_multiplier"
    ] = geographic_multiplier

    event[
        "attribution"
    ] = attribution

    event[
        "hybrid_threat_score"
    ] = final_score

    event[
        "hybrid_threat_level"
    ] = classify_level(
        final_score
    )

    event[
        "score_breakdown"
    ] = {
        "raw_base_score":
            base_score,

        "relevance":
            relevance_component,

        "keywords":
            keyword_component,

        "categories":
            category_component,

        "actors":
            actor_component,

        "locations":
            location_component,

        "source_confirmation":
            source_component,

        "strategic_modifier":
            strategic_component,

        "event_subtype":
            subtype,

        "subtype_weight":
            subtype_weight,

        "confidence":
            confidence,

        "confidence_multiplier":
            confidence_multiplier,

        "geographic_scope":
            geographic_scope,

        "geographic_multiplier":
            geographic_multiplier,

        "incident_context_multiplier":
            context_multiplier,

        "incident_context_reasons":
            context_reasons,

        "attribution":
            attribution,

        "weighted_score":
            weighted_score
    }

    return event


# ---------------------------------------------------------------------
# COUNTRY SUMMARY
# ---------------------------------------------------------------------


def build_country_summary(
    events: List[Dict[str, Any]]
) -> Dict[str, Any]:

    summary = {
        country: {
            "country":
                country,

            "event_count":
                0,

            "incident_count":
                0,

            "activity_count":
                0,

            "indicator_count":
                0,

            "assessment_count":
                0,

            "score_total":
                0,

            "average_score":
                0,

            "highest_score":
                0,

            "level":
                "low",

            "categories":
                {},

            "actors":
                {}
        }

        for country
        in COUNTRIES
    }

    for event in events:

        primary_country = event.get(
            "primary_country",
            "Regional"
        )

        if primary_country not in summary:

            primary_country = "Regional"

        subtype = event.get(
            "event_subtype",
            "assessment"
        )

        score = int(
            event.get(
                "hybrid_threat_score",
                0
            )
        )

        data = summary[
            primary_country
        ]

        data[
            "event_count"
        ] += 1

        data[
            "score_total"
        ] += score

        data[
            "highest_score"
        ] = max(
            data[
                "highest_score"
            ],
            score
        )

        if subtype == "incident":

            data[
                "incident_count"
            ] += 1

        elif subtype == "activity":

            data[
                "activity_count"
            ] += 1

        elif subtype == "indicator":

            data[
                "indicator_count"
            ] += 1

        else:

            data[
                "assessment_count"
            ] += 1

        for category in event.get(
            "categories",
            []
        ):

            data[
                "categories"
            ][
                category
            ] = (
                data[
                    "categories"
                ].get(
                    category,
                    0
                )
                + 1
            )

        for actor in event.get(
            "actors",
            []
        ):

            data[
                "actors"
            ][
                actor
            ] = (
                data[
                    "actors"
                ].get(
                    actor,
                    0
                )
                + 1
            )

    for country, data in summary.items():

        scored_events = (
            data[
                "incident_count"
            ]
            + data[
                "activity_count"
            ]
            + data[
                "indicator_count"
            ]
        )

        if scored_events > 0:

            data[
                "average_score"
            ] = round(
                data[
                    "score_total"
                ]
                / scored_events,
                2
            )

        data[
            "level"
        ] = classify_level(
            int(
                data[
                    "average_score"
                ]
            )
        )

    return summary


# ---------------------------------------------------------------------
# CATEGORY SUMMARY
# ---------------------------------------------------------------------


def build_category_summary(
    events: List[Dict[str, Any]]
) -> Dict[str, Any]:

    summary: Dict[
        str,
        Any
    ] = {}

    for event in events:

        score = int(
            event.get(
                "hybrid_threat_score",
                0
            )
        )

        for category in event.get(
            "categories",
            []
        ):

            if category not in summary:

                summary[
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

            summary[
                category
            ][
                "event_count"
            ] += 1

            summary[
                category
            ][
                "score_total"
            ] += score

            summary[
                category
            ][
                "highest_score"
            ] = max(
                summary[
                    category
                ][
                    "highest_score"
                ],
                score
            )

    for category, data in summary.items():

        if data[
            "event_count"
        ] > 0:

            data[
                "average_score"
            ] = round(
                data[
                    "score_total"
                ]
                / data[
                    "event_count"
                ],
                2
            )

    return dict(
        sorted(
            summary.items(),
            key=lambda pair:
                pair[
                    1
                ][
                    "score_total"
                ],
            reverse=True
        )
    )


# ---------------------------------------------------------------------
# ACTOR SUMMARY
# ---------------------------------------------------------------------


def build_actor_summary(
    events: List[Dict[str, Any]]
) -> Dict[str, Any]:

    summary: Dict[
        str,
        Any
    ] = {}

    for event in events:

        score = int(
            event.get(
                "hybrid_threat_score",
                0
            )
        )

        for actor in event.get(
            "actors",
            []
        ):

            if actor not in summary:

                summary[
                    actor
                ] = {
                    "actor":
                        actor,

                    "event_count":
                        0,

                    "score_total":
                        0,

                    "average_score":
                        0,

                    "highest_score":
                        0
                }

            summary[
                actor
            ][
                "event_count"
            ] += 1

            summary[
                actor
            ][
                "score_total"
            ] += score

            summary[
                actor
            ][
                "highest_score"
            ] = max(
                summary[
                    actor
                ][
                    "highest_score"
                ],
                score
            )

    for actor, data in summary.items():

        if data[
            "event_count"
        ] > 0:

            data[
                "average_score"
            ] = round(
                data[
                    "score_total"
                ]
                / data[
                    "event_count"
                ],
                2
            )

    return dict(
        sorted(
            summary.items(),
            key=lambda pair:
                pair[
                    1
                ][
                    "score_total"
                ],
            reverse=True
        )
    )


# ---------------------------------------------------------------------
# SUBTYPE SUMMARY
# ---------------------------------------------------------------------


def build_subtype_summary(
    events: List[Dict[str, Any]]
) -> Dict[str, Any]:

    summary = {
        "incident": {
            "event_count": 0,
            "score_total": 0,
            "average_score": 0
        },

        "activity": {
            "event_count": 0,
            "score_total": 0,
            "average_score": 0
        },

        "indicator": {
            "event_count": 0,
            "score_total": 0,
            "average_score": 0
        },

        "assessment": {
            "event_count": 0,
            "score_total": 0,
            "average_score": 0
        }
    }

    for event in events:

        subtype = event.get(
            "event_subtype",
            "assessment"
        )

        if subtype not in summary:

            subtype = "assessment"

        score = int(
            event.get(
                "hybrid_threat_score",
                0
            )
        )

        summary[
            subtype
        ][
            "event_count"
        ] += 1

        summary[
            subtype
        ][
            "score_total"
        ] += score

    for subtype, data in summary.items():

        if data[
            "event_count"
        ] > 0:

            data[
                "average_score"
            ] = round(
                data[
                    "score_total"
                ]
                / data[
                    "event_count"
                ],
                2
            )

    return summary


# ---------------------------------------------------------------------
# INDEX HELPERS
#
# We intentionally use the highest-value events rather than averaging
# every item. Otherwise large volumes of weak warnings dilute a small
# number of real operational incidents.
# ---------------------------------------------------------------------


def top_score_average(
    events: List[Dict[str, Any]],
    limit: int
) -> float:

    if not events:

        return 0.0

    scores = sorted(
        [
            int(
                event.get(
                    "hybrid_threat_score",
                    0
                )
            )
            for event
            in events
        ],
        reverse=True
    )

    selected = scores[
        :limit
    ]

    if not selected:

        return 0.0

    return round(
        sum(
            selected
        )
        / len(
            selected
        ),
        2
    )


# ---------------------------------------------------------------------
# OVERALL SUMMARY
# ---------------------------------------------------------------------


def build_overall_summary(
    events: List[Dict[str, Any]]
) -> Dict[str, Any]:

    if not events:

        return {
            "event_count":
                0,

            "incident_count":
                0,

            "activity_count":
                0,

            "indicator_count":
                0,

            "assessment_count":
                0,

            "score_total":
                0,

            "average_score":
                0,

            "highest_score":
                0,

            "operational_index":
                0,

            "early_warning_index":
                0,

            "threat_index":
                0,

            "overall_level":
                "low"
        }

    score_total = sum(
        int(
            event.get(
                "hybrid_threat_score",
                0
            )
        )
        for event
        in events
    )

    highest_score = max(
        int(
            event.get(
                "hybrid_threat_score",
                0
            )
        )
        for event
        in events
    )

    scored_events = [
        event
        for event
        in events
        if event.get(
            "event_subtype"
        )
        != "assessment"
    ]

    if scored_events:

        average_score = round(
            sum(
                int(
                    event.get(
                        "hybrid_threat_score",
                        0
                    )
                )
                for event
                in scored_events
            )
            / len(
                scored_events
            ),
            2
        )

    else:

        average_score = 0

    incident_count = sum(
        1
        for event
        in events
        if event.get(
            "event_subtype"
        )
        == "incident"
    )

    activity_count = sum(
        1
        for event
        in events
        if event.get(
            "event_subtype"
        )
        == "activity"
    )

    indicator_count = sum(
        1
        for event
        in events
        if event.get(
            "event_subtype"
        )
        == "indicator"
    )

    assessment_count = sum(
        1
        for event
        in events
        if event.get(
            "event_subtype"
        )
        == "assessment"
    )

    # -------------------------------------------------------------
    # OPERATIONAL INDEX
    #
    # Incident + concrete activity only.
    # Top five prevent a large volume of low-value events from
    # diluting current operational intensity.
    # -------------------------------------------------------------

    operational_events = [
        event
        for event
        in events
        if event.get(
            "event_subtype"
        )
        in {
            "incident",
            "activity"
        }
    ]

    operational_index = top_score_average(
        operational_events,
        5
    )

    # -------------------------------------------------------------
    # EARLY WARNING INDEX
    #
    # Indicator events only.
    # -------------------------------------------------------------

    warning_events = [
        event
        for event
        in events
        if event.get(
            "event_subtype"
        )
        == "indicator"
    ]

    early_warning_index = top_score_average(
        warning_events,
        8
    )

    # -------------------------------------------------------------
    # THREAT INDEX
    #
    # If operational events exist:
    #   80% operational reality
    #   20% early-warning environment
    #
    # If no operational event exists:
    #   warnings become the main signal but remain warning-level
    #   evidence rather than fabricated operational activity.
    # -------------------------------------------------------------

    if operational_events:

        threat_index = round(
            (
                operational_index
                * 0.80
            )
            + (
                early_warning_index
                * 0.20
            ),
            2
        )

    else:

        threat_index = round(
            early_warning_index,
            2
        )

    threat_index = min(
        threat_index,
        100
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

        "score_total":
            score_total,

        "average_score":
            average_score,

        "highest_score":
            highest_score,

        "operational_index":
            operational_index,

        "early_warning_index":
            early_warning_index,

        "threat_index":
            threat_index,

        "overall_level":
            classify_level(
                int(
                    threat_index
                )
            )
    }


# ---------------------------------------------------------------------
# GEOGRAPHIC SUMMARY
# ---------------------------------------------------------------------


def build_scope_summary(
    events: List[Dict[str, Any]]
) -> Dict[str, Any]:

    summary = {
        "direct": {
            "event_count": 0,
            "score_total": 0,
            "average_score": 0
        },

        "regional_direct": {
            "event_count": 0,
            "score_total": 0,
            "average_score": 0
        },

        "external_context": {
            "event_count": 0,
            "score_total": 0,
            "average_score": 0
        }
    }

    for event in events:

        scope = event.get(
            "geographic_scope",
            "external_context"
        )

        if scope not in summary:

            scope = "external_context"

        score = int(
            event.get(
                "hybrid_threat_score",
                0
            )
        )

        summary[
            scope
        ][
            "event_count"
        ] += 1

        summary[
            scope
        ][
            "score_total"
        ] += score

    for scope, data in summary.items():

        if data[
            "event_count"
        ]:

            data[
                "average_score"
            ] = round(
                data[
                    "score_total"
                ]
                / data[
                    "event_count"
                ],
                2
            )

    return summary


# ---------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------


def main() -> None:

    clustered = load_clustered_data()

    events = clustered.get(
        "events",
        []
    )

    scored_events = [
        score_event(
            event
        )
        for event
        in events
    ]

    scored_events = sorted(
        scored_events,
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

    payload = {
        "project":
            clustered.get(
                "project",
                "baltic-hybrid-monitor"
            ),

        "region":
            clustered.get(
                "region",
                "Baltic states and Poland"
            ),

        "generated_at":
            datetime.now(
                timezone.utc
            ).isoformat(),

        "input_generated_at":
            clustered.get(
                "generated_at"
            ),

        "raw_item_count":
            clustered.get(
                "raw_item_count"
            ),

        "filtered_item_count":
            clustered.get(
                "filtered_item_count"
            ),

        "clustered_event_count":
            clustered.get(
                "event_count"
            ),

        "merged_item_count":
            clustered.get(
                "merged_item_count"
            ),

        "method": {
            "description":
                (
                    "Threat Score Engine v3.0 using clustered events, "
                    "event ontology, geographic scope and separate "
                    "operational / early-warning indices."
                ),

            "classification_version":
                "threat_score_v3_0_scope_separated",

            "input":
                "data/baltic_hybrid_clustered_events.json",

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
                "precautionary-response correction"
            ],

            "index_method": {
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
                        "80% operational index + 20% early-warning "
                        "index when operational events exist; otherwise "
                        "the early-warning index."
                    )
            },

            "subtype_weights":
                SUBTYPE_WEIGHTS,

            "confidence_multipliers":
                CONFIDENCE_MULTIPLIERS,

            "geographic_multipliers":
                GEOGRAPHIC_MULTIPLIERS,

            "levels": {
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
            }
        },

        "overall_summary":
            build_overall_summary(
                scored_events
            ),

        "country_summary":
            build_country_summary(
                scored_events
            ),

        "category_summary":
            build_category_summary(
                scored_events
            ),

        "actor_summary":
            build_actor_summary(
                scored_events
            ),

        "subtype_summary":
            build_subtype_summary(
                scored_events
            ),

        "scope_summary":
            build_scope_summary(
                scored_events
            ),

        "items":
            scored_events,

        "events":
            scored_events
    }

    save_json(
        SCORED_OUTPUT,
        payload
    )

    save_json(
        DOCS_OUTPUT,
        payload
    )

    print(
        f"Saved scored event data to "
        f"{SCORED_OUTPUT}"
    )

    print(
        f"Saved public scored event data to "
        f"{DOCS_OUTPUT}"
    )

    print(
        f"Events scored: "
        f"{len(scored_events)}"
    )

    print(
        "Operational index: "
        f"{payload['overall_summary']['operational_index']}"
    )

    print(
        "Early-warning index: "
        f"{payload['overall_summary']['early_warning_index']}"
    )

    print(
        "Threat index: "
        f"{payload['overall_summary']['threat_index']}"
    )

    print(
        "Overall level: "
        f"{payload['overall_summary']['overall_level']}"
    )


if __name__ == "__main__":
    main()
