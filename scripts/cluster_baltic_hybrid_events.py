import json
import re
import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, List, Set


ROOT = Path(__file__).resolve().parents[1]

FILTERED_INPUT = ROOT / "data" / "baltic_hybrid_filtered_news.json"
CLUSTERED_OUTPUT = ROOT / "data" / "baltic_hybrid_clustered_events.json"
DOCS_CLUSTERED_OUTPUT = ROOT / "docs" / "data" / "baltic_hybrid_clustered_events.json"


COUNTRY_TERMS = {
    "Estonia": [
        "estonia",
        "estonian",
        "tallinn",
        "narva",
        "tartu"
    ],
    "Latvia": [
        "latvia",
        "latvian",
        "riga",
        "daugavpils",
        "latgale"
    ],
    "Lithuania": [
        "lithuania",
        "lithuanian",
        "vilnius",
        "kaunas",
        "klaipeda",
        "klaipėda"
    ],
    "Poland": [
        "poland",
        "polish",
        "warsaw",
        "bialystok",
        "białystok",
        "gdansk",
        "gdańsk",
        "suwalki",
        "suwałki"
    ]
}


LOCATION_COUNTRY_HINTS = {
    "Kaliningrad": [
        "Poland",
        "Lithuania"
    ],
    "Suwalki Gap": [
        "Poland",
        "Lithuania"
    ],
    "Belarus Border": [
        "Poland",
        "Lithuania",
        "Latvia"
    ],
    "Poland-Belarus Border": [
        "Poland"
    ],
    "Narva": [
        "Estonia"
    ],
    "Riga": [
        "Latvia"
    ],
    "Tallinn": [
        "Estonia"
    ],
    "Vilnius": [
        "Lithuania"
    ],
    "Klaipeda": [
        "Lithuania"
    ],
    "Gdansk": [
        "Poland"
    ],
    "Baltic Sea": [
        "Estonia",
        "Latvia",
        "Lithuania",
        "Poland"
    ]
}


STOPWORDS = {
    "the",
    "and",
    "for",
    "with",
    "from",
    "that",
    "this",
    "into",
    "over",
    "after",
    "before",
    "about",
    "amid",
    "says",
    "said",
    "new",
    "latest",
    "update",
    "updated",
    "report",
    "reports",
    "article",
    "news",
    "live",
    "will",
    "have",
    "has",
    "are",
    "was",
    "were",
    "its",
    "their"
}


# ---------------------------------------------------------------------
# EVENT ONTOLOGY
#
# INCIDENT
#   Concrete event that happened or is happening.
#
# ACTIVITY
#   Concrete military/security activity.
#
# INDICATOR
#   Warning, precursor, forecast, possible future incident,
#   information/influence signal.
#
# ASSESSMENT
#   Analysis, policy, preparedness, procurement, investment,
#   capability development or institutional background.
# ---------------------------------------------------------------------


STRONG_INCIDENT_TERMS = [
    "drone crash",
    "drone crashed",
    "drone shot down",
    "drone was shot down",
    "drone entered",
    "drone crossed",
    "drone attack",
    "airspace violation",
    "airspace incursion",
    "violated airspace",
    "entered airspace",
    "gps jamming",
    "gnss jamming",
    "gps interference",
    "gnss interference",
    "navigation interference",
    "spoofing detected",
    "cable damaged",
    "cable damage",
    "cable cut",
    "undersea cable damaged",
    "subsea cable damaged",
    "pipeline damaged",
    "pipeline damage",
    "explosion",
    "exploded",
    "arson",
    "set fire",
    "set on fire",
    "cyberattack",
    "cyber attack",
    "ddos attack",
    "malware attack",
    "ransomware attack",
    "wiper attack",
    "systems breached",
    "network breached",
    "data breach",
    "arrested spy",
    "spy arrested",
    "espionage arrest",
    "arrested for espionage",
    "border breach",
    "illegal border crossing",
    "border crossing detected",
    "fighter jets scrambled",
    "scrambles fighter jets",
    "scrambled fighter jets",
    "missile entered",
    "missile crossed",
    "missile strike",
    "critical infrastructure attack",
    "sabotage attack",
    "sabotage incident",
    "sabotage operation",
    "sabotage attempt"
]


ACTIVITY_TERMS = [
    "military exercise",
    "joint exercise",
    "military drills",
    "military drill",
    "air policing",
    "patrol",
    "deployment",
    "troop deployment",
    "troop movement",
    "force movement",
    "mobilisation",
    "mobilization",
    "readiness",
    "deterrence",
    "border guard deployment",
    "border protection operation",
    "military buildup",
    "military build-up",
    "reinforcement",
    "reinforcements",
    "security operation"
]


WARNING_TERMS = [
    "warning",
    "warns",
    "warned",
    "warning of",
    "warned of",
    "warned that",
    "could attack",
    "could stage",
    "could launch",
    "could target",
    "could strike",
    "could sabotage",
    "could disrupt",
    "could interfere",
    "may attack",
    "may stage",
    "may launch",
    "may target",
    "may strike",
    "may sabotage",
    "might attack",
    "might stage",
    "might target",
    "possible attack",
    "possible attacks",
    "possible sabotage",
    "possible incident",
    "possible operation",
    "risk of attack",
    "risk of sabotage",
    "risk of escalation",
    "threat of attack",
    "threat of sabotage",
    "threat assessment",
    "intelligence warning",
    "security warning",
    "cyber warning",
    "gps warning",
    "preparedness warning",
    "concern over",
    "concerns over",
    "fear of attack",
    "fears of attack",
    "expected attack",
    "potential attack",
    "potential sabotage",
    "potential threat",
    "likely attack",
    "hybrid threat",
    "russia threatens",
    "kremlin threat"
]


INFORMATION_INDICATOR_TERMS = [
    "disinformation campaign",
    "propaganda campaign",
    "influence operation",
    "information operation",
    "information campaign",
    "influence campaign",
    "coordinated disinformation",
    "foreign information manipulation",
    "foreign influence operation"
]


# ---------------------------------------------------------------------
# CAPABILITY / DEVELOPMENT OVERRIDE
#
# These describe the subject of the article as preparation,
# procurement or capability development rather than a hostile event.
# ---------------------------------------------------------------------

DEVELOPMENT_TERMS = [
    "to install",
    "will install",
    "plans to install",
    "plan to install",
    "to deploy",
    "will deploy",
    "plans to deploy",
    "plan to deploy",
    "to build",
    "will build",
    "plans to build",
    "plan to build",
    "being built",
    "being constructed",
    "under construction",
    "construction of",
    "set up a production facility",
    "plans to set up",
    "plan to set up",
    "production set to begin",
    "production facility",
    "manufacturing facility",
    "new factory",
    "new plant",
    "factory construction",
    "plant construction",
    "drone detection system",
    "drone-detection system",
    "air defence system",
    "air defense system",
    "detection system",
    "surveillance system",
    "procurement",
    "procure",
    "acquisition",
    "purchase of",
    "investment",
    "investing",
    "invests",
    "modernisation",
    "modernization",
    "capability development",
    "capability upgrade",
    "defence industry",
    "defense industry",
    "production capacity",
    "security upgrade",
    "infrastructure upgrade"
]


ASSESSMENT_TERMS = [
    "framework",
    "strategy",
    "strategic",
    "analysis",
    "assessment",
    "threat assessment",
    "report",
    "study",
    "white paper",
    "ecosystem",
    "capabilities",
    "capability",
    "maturity",
    "training",
    "awareness",
    "cyber hygiene",
    "conference",
    "policy",
    "guidance",
    "implementation",
    "preparedness",
    "readiness plan",
    "defence package",
    "defense package",
    "military aid",
    "security package",
    "investment",
    "reserve",
    "certification",
    "resilience act",
    "cyber resilience",
    "challenge",
    "competition",
    "conference",
    "exercise scenario",
    "procurement",
    "acquisition",
    "modernisation",
    "modernization"
]


POLITICAL_STATEMENT_TERMS = [
    "says russia will",
    "says russia won't",
    "says russia will not",
    "said russia will",
    "said russia will not",
    "says nato will",
    "said nato will",
    "comments on",
    "commented on",
    "discusses",
    "discussed",
    "calls for",
    "called for",
    "urges",
    "urged",
    "believes",
    "said he believes",
    "said she believes",
    "according to minister",
    "foreign minister says",
    "president says",
    "prime minister says"
]


CONFIRMED_ACTION_TERMS = [
    "confirmed",
    "detected",
    "discovered",
    "found",
    "arrested",
    "detained",
    "charged",
    "convicted",
    "breached",
    "damaged",
    "destroyed",
    "disrupted",
    "shot down",
    "intercepted",
    "scrambled",
    "crossed",
    "entered",
    "violated",
    "attacked",
    "struck",
    "hit",
    "exploded",
    "burned",
    "burnt"
]


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

def load_json(path: Path) -> Dict[str, Any]:

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
# TEXT NORMALIZATION
# ---------------------------------------------------------------------

def normalize(text: str) -> str:

    text = str(text).lower()

    text = re.sub(
        r"https?://\S+",
        " ",
        text
    )

    text = re.sub(
        r"[^a-z0-9áéíóöőúüűąćęłńóśźż\- ]+",
        " ",
        text
    )

    text = re.sub(
        r"\s+",
        " ",
        text
    )

    return text.strip()


# ---------------------------------------------------------------------
# SAFE TERM MATCHING
#
# Old behaviour:
#
#   term in text
#
# could incorrectly match:
#
#   "hit" inside "white"
#
# New behaviour requires real word / phrase boundaries.
# ---------------------------------------------------------------------

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


def tokenize(text: str) -> Set[str]:

    return {
        token
        for token in normalize(
            text
        ).split()
        if (
            len(token) >= 4
            and token not in STOPWORDS
        )
    }


def stable_id(
    value: str
) -> str:

    return hashlib.sha256(
        value.encode(
            "utf-8"
        )
    ).hexdigest()[:16]


def similarity(
    a: Set[str],
    b: Set[str]
) -> float:

    if not a or not b:
        return 0.0

    return (
        len(
            a & b
        )
        / len(
            a | b
        )
    )


# ---------------------------------------------------------------------
# CLUSTERING
# ---------------------------------------------------------------------

def shared_context(
    item: Dict[str, Any],
    event: Dict[str, Any]
) -> bool:

    item_countries = set(
        item.get(
            "countries",
            []
        )
    )

    event_countries = set(
        event.get(
            "countries",
            []
        )
    )

    item_categories = set(
        item.get(
            "categories",
            []
        )
    )

    event_categories = set(
        event.get(
            "categories",
            []
        )
    )

    item_actors = set(
        item.get(
            "actors",
            []
        )
    )

    event_actors = set(
        event.get(
            "actors",
            []
        )
    )

    if (
        item_actors
        and event_actors
        and item_actors & event_actors
    ):
        return True

    if (
        item_categories
        and event_categories
        and item_categories & event_categories
        and item_countries
        and event_countries
        and item_countries & event_countries
    ):
        return True

    return False


def should_merge(
    item: Dict[str, Any],
    event: Dict[str, Any]
) -> bool:

    title_score = similarity(
        tokenize(
            item.get(
                "title",
                ""
            )
        ),
        tokenize(
            event.get(
                "title",
                ""
            )
        )
    )

    if title_score >= 0.44:
        return True

    if (
        title_score >= 0.30
        and shared_context(
            item,
            event
        )
    ):
        return True

    return False


def unique_merge(
    existing: List[str],
    new_values: List[str]
) -> List[str]:

    output = list(
        existing
    )

    for value in new_values:

        if (
            value
            and value not in output
        ):

            output.append(
                value
            )

    return output


# ---------------------------------------------------------------------
# COUNTRY CLASSIFICATION
# ---------------------------------------------------------------------

def country_score_from_text(
    text: str,
    weight: int
) -> Dict[str, int]:

    scores = {
        country: 0
        for country in COUNTRY_TERMS
    }

    for country, terms in COUNTRY_TERMS.items():

        for term in terms:

            if contains_term(
                text,
                term
            ):

                scores[
                    country
                ] += weight

    return scores


def choose_primary_country_v2(
    event: Dict[str, Any]
) -> str:

    scores = {
        country: 0
        for country in COUNTRY_TERMS
    }

    title = event.get(
        "title",
        ""
    )

    summary = event.get(
        "summary",
        ""
    )

    url = event.get(
        "url",
        ""
    )

    for country, value in country_score_from_text(
        title,
        6
    ).items():

        scores[
            country
        ] += value

    for country, value in country_score_from_text(
        summary,
        3
    ).items():

        scores[
            country
        ] += value

    for country, value in country_score_from_text(
        url,
        2
    ).items():

        scores[
            country
        ] += value

    for item in event.get(
        "related_items",
        []
    ):

        for country in item.get(
            "countries",
            []
        ):

            if country in scores:

                scores[
                    country
                ] += 3

    for location in event.get(
        "locations",
        []
    ):

        for country in LOCATION_COUNTRY_HINTS.get(
            location,
            []
        ):

            if country in scores:

                scores[
                    country
                ] += 4

    text = normalize(
        f"{title} {summary} {url}"
    )

    if (
        contains_term(
            text,
            "poland-belarus border"
        )
        or contains_term(
            text,
            "polish-belarusian border"
        )
    ):

        scores[
            "Poland"
        ] += 8

    if (
        contains_term(
            text,
            "suwalki"
        )
        or contains_term(
            text,
            "suwałki"
        )
    ):

        scores[
            "Poland"
        ] += 6

        scores[
            "Lithuania"
        ] += 3

    if contains_term(
        text,
        "kaliningrad"
    ):

        scores[
            "Poland"
        ] += 3

        scores[
            "Lithuania"
        ] += 3

    if (
        contains_term(
            text,
            "baltic states"
        )
        or contains_term(
            text,
            "baltics"
        )
    ):

        scores[
            "Estonia"
        ] += 1

        scores[
            "Latvia"
        ] += 1

        scores[
            "Lithuania"
        ] += 1

    sorted_scores = sorted(
        scores.items(),
        key=lambda pair:
            pair[1],
        reverse=True
    )

    top_country, top_score = (
        sorted_scores[0]
    )

    if top_score <= 0:
        return "Regional"

    if len(
        sorted_scores
    ) > 1:

        second_score = (
            sorted_scores[1][1]
        )

        if (
            second_score > 0
            and (
                top_score
                - second_score
            ) <= 1
        ):

            return "Regional"

    return top_country


# ---------------------------------------------------------------------
# CONFIDENCE
# ---------------------------------------------------------------------

def calculate_confidence(
    source_count: int,
    source_group_count: int,
    source_names: List[str]
) -> Dict[str, Any]:

    official_sources = [
        "NATO",
        "ENISA",
        "EUvsDisinfo",
        "CERT",
        "Ministry",
        "MOD",
        "Border Guard",
        "Defence",
        "Defense"
    ]

    score = 25

    score += min(
        source_count,
        6
    ) * 8

    score += min(
        source_group_count,
        4
    ) * 5

    if any(
        any(
            key.lower()
            in source.lower()
            for key
            in official_sources
        )
        for source
        in source_names
    ):

        score += 10

    if (
        source_count >= 3
        and source_group_count >= 2
    ):

        score += 8

    score = min(
        score,
        100
    )

    if score >= 80:

        label = "very_high"

    elif score >= 65:

        label = "high"

    elif score >= 50:

        label = "medium"

    else:

        label = "low"

    return {
        "confidence":
            label,

        "confidence_score":
            score
    }


# ---------------------------------------------------------------------
# CLASSIFICATION TEXT
# ---------------------------------------------------------------------

def build_classification_text(
    event: Dict[str, Any]
) -> str:

    parts = [
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
    ]

    for related_title in event.get(
        "related_titles",
        []
    ):

        parts.append(
            str(
                related_title
            )
        )

    return normalize(
        " ".join(
            parts
        )
    )


def build_primary_classification_text(
    event: Dict[str, Any]
) -> str:

    return normalize(
        " ".join([
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
    )


# ---------------------------------------------------------------------
# SIGNAL HELPERS
# ---------------------------------------------------------------------

def has_strong_incident_signal(
    text: str
) -> bool:

    return contains_any(
        text,
        STRONG_INCIDENT_TERMS
    )


def has_confirmed_action_signal(
    text: str
) -> bool:

    return contains_any(
        text,
        CONFIRMED_ACTION_TERMS
    )


def has_warning_signal(
    text: str
) -> bool:

    return contains_any(
        text,
        WARNING_TERMS
    )


def has_assessment_signal(
    text: str
) -> bool:

    return contains_any(
        text,
        ASSESSMENT_TERMS
    )


def has_development_signal(
    text: str
) -> bool:

    return contains_any(
        text,
        DEVELOPMENT_TERMS
    )


def has_political_statement_signal(
    text: str
) -> bool:

    return contains_any(
        text,
        POLITICAL_STATEMENT_TERMS
    )


# ---------------------------------------------------------------------
# EVENT CLASSIFICATION
# ---------------------------------------------------------------------

def classify_event_subtype(
    event: Dict[str, Any]
) -> str:

    full_text = (
        build_classification_text(
            event
        )
    )

    primary_text = (
        build_primary_classification_text(
            event
        )
    )

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

    development_signal = (
        has_development_signal(
            primary_text
        )
    )

    warning_signal = (
        has_warning_signal(
            primary_text
        )
    )

    assessment_signal = (
        has_assessment_signal(
            primary_text
        )
    )

    political_statement = (
        has_political_statement_signal(
            primary_text
        )
    )

    strong_primary_incident = (
        has_strong_incident_signal(
            primary_text
        )
    )

    strong_full_incident = (
        has_strong_incident_signal(
            full_text
        )
    )

    confirmed_primary_action = (
        has_confirmed_action_signal(
            primary_text
        )
    )

    confirmed_full_action = (
        has_confirmed_action_signal(
            full_text
        )
    )

    # -------------------------------------------------------------
    # 1. CAPABILITY DEVELOPMENT / PROCUREMENT / INVESTMENT
    #
    # This intentionally comes before incident classification.
    #
    # Example:
    #
    # "Warsaw to install drone-detection system amid rise in
    # airspace incursions"
    #
    # The subject is the defensive system deployment, not the
    # historical incursions mentioned as context.
    # -------------------------------------------------------------

    if development_signal:

        return "assessment"

    # -------------------------------------------------------------
    # 2. WARNING / POSSIBLE FUTURE EVENT
    #
    # Warning language takes priority unless the primary title /
    # summary also explicitly describes a confirmed action.
    # -------------------------------------------------------------

    if (
        warning_signal
        and not confirmed_primary_action
    ):

        return "indicator"

    # -------------------------------------------------------------
    # 3. INFORMATION / INFLUENCE SIGNAL
    # -------------------------------------------------------------

    if (
        categories == {
            "disinformation"
        }
    ):

        return "indicator"

    if (
        "disinformation"
        in categories
        and not (
            categories
            & (
                OPERATIONAL_CATEGORIES
                - {
                    "disinformation"
                }
            )
        )
    ):

        return "indicator"

    if contains_any(
        primary_text,
        INFORMATION_INDICATOR_TERMS
    ):

        return "indicator"

    # -------------------------------------------------------------
    # 4. ASSESSMENT / POLICY / POLITICAL STATEMENT
    # -------------------------------------------------------------

    if (
        assessment_signal
        and not confirmed_primary_action
    ):

        return "assessment"

    if (
        political_statement
        and not confirmed_primary_action
    ):

        return "assessment"

    # -------------------------------------------------------------
    # 5. STRONG INCIDENT IN PRIMARY CONTENT
    #
    # Prefer the title + summary over related headlines.
    # -------------------------------------------------------------

    if strong_primary_incident:

        return "incident"

    # -------------------------------------------------------------
    # 6. CATEGORY-SUPPORTED CONFIRMED INCIDENT
    # -------------------------------------------------------------

    if (
        categories
        & {
            "drone_incident",
            "gps_interference",
            "sabotage",
            "espionage",
            "critical_infrastructure"
        }
        and confirmed_primary_action
    ):

        return "incident"

    if (
        "cyber"
        in categories
        and (
            confirmed_primary_action
            or contains_any(
                primary_text,
                [
                    "cyberattack",
                    "cyber attack",
                    "ddos attack",
                    "malware attack",
                    "ransomware attack",
                    "wiper attack",
                    "data breach",
                    "network breach",
                    "systems breached"
                ]
            )
        )
    ):

        return "incident"

    if (
        categories
        & {
            "border_pressure",
            "migration_pressure"
        }
        and (
            confirmed_primary_action
            or contains_any(
                primary_text,
                [
                    "border crossing",
                    "border breach",
                    "migrants crossed",
                    "tunnel discovered",
                    "tunnel found",
                    "illegal crossing"
                ]
            )
        )
    ):

        return "incident"

    # -------------------------------------------------------------
    # 7. CONCRETE MILITARY / SECURITY ACTIVITY
    # -------------------------------------------------------------

    if contains_any(
        primary_text,
        ACTIVITY_TERMS
    ):

        return "activity"

    # -------------------------------------------------------------
    # 8. RELATED-TITLE INCIDENT SUPPORT
    #
    # Related clustered titles can support classification, but they
    # are deliberately weaker than the primary article.
    # -------------------------------------------------------------

    if (
        strong_full_incident
        and confirmed_full_action
        and categories
        & OPERATIONAL_CATEGORIES
    ):

        return "incident"

    # -------------------------------------------------------------
    # 9. ACTOR-SUPPORTED THREAT SIGNAL
    # -------------------------------------------------------------

    if (
        (
            "Russia"
            in actors
            or "Belarus"
            in actors
        )
        and categories
    ):

        return "indicator"

    # -------------------------------------------------------------
    # 10. GENERIC CATEGORY SIGNAL
    #
    # A category is evidence of relevance, not evidence that an
    # incident happened.
    # -------------------------------------------------------------

    if categories:

        return "indicator"

    return "assessment"


# ---------------------------------------------------------------------
# EVENT TYPE
# ---------------------------------------------------------------------

def classify_event_type(
    event_subtype: str
) -> str:

    if event_subtype in {
        "incident",
        "activity"
    }:

        return "operational"

    if event_subtype == "indicator":

        return "warning"

    return "background"


# ---------------------------------------------------------------------
# ANALYTICAL LAYER
# ---------------------------------------------------------------------

def classify_analytical_layer(
    event: Dict[str, Any]
) -> str:

    subtype = event.get(
        "event_subtype",
        "assessment"
    )

    categories = set(
        event.get(
            "categories",
            []
        )
    )

    if subtype == "assessment":

        return "assessment"

    if subtype == "indicator":

        if (
            "disinformation"
            in categories
            and not (
                categories
                & (
                    OPERATIONAL_CATEGORIES
                    - {
                        "disinformation"
                    }
                )
            )
        ):

            return "information"

        return "early_warning"

    if subtype in {
        "incident",
        "activity"
    }:

        return "operational"

    return "assessment"


# ---------------------------------------------------------------------
# EVENT CREATION
# ---------------------------------------------------------------------

def create_event_from_item(
    item: Dict[str, Any]
) -> Dict[str, Any]:

    source_name = item.get(
        "source_name",
        "Unknown source"
    )

    source_group = item.get(
        "source_group",
        "unknown"
    )

    event_seed = (
        normalize(
            item.get(
                "title",
                ""
            )
        )
        + (
            item.get(
                "published_at"
            )
            or ""
        )[:10]
    )

    confidence = calculate_confidence(
        1,
        1,
        [
            source_name
        ]
    )

    event = {
        "event_id":
            stable_id(
                event_seed
            ),

        "title":
            item.get(
                "title",
                ""
            ),

        "summary":
            item.get(
                "summary",
                ""
            ),

        "url":
            item.get(
                "url",
                ""
            ),

        "published_at":
            item.get(
                "published_at"
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

        "relevance_score":
            float(
                item.get(
                    "relevance_score",
                    0
                )
            ),

        "source_count":
            1,

        "source_names":
            [
                source_name
            ],

        "source_groups":
            [
                source_group
            ],

        "related_item_count":
            1,

        "related_titles":
            [
                item.get(
                    "title",
                    ""
                )
            ],

        "related_urls":
            [
                item.get(
                    "url",
                    ""
                )
            ],

        "related_items":
            [
                item
            ],

        "confidence":
            confidence[
                "confidence"
            ],

        "confidence_score":
            confidence[
                "confidence_score"
            ],

        "collection_methods":
            [
                item.get(
                    "collection_method",
                    "rss"
                )
            ]
    }

    event[
        "primary_country"
    ] = choose_primary_country_v2(
        event
    )

    event[
        "event_subtype"
    ] = classify_event_subtype(
        event
    )

    event[
        "event_type"
    ] = classify_event_type(
        event[
            "event_subtype"
        ]
    )

    event[
        "analytical_layer"
    ] = classify_analytical_layer(
        event
    )

    return event


# ---------------------------------------------------------------------
# EVENT MERGE
# ---------------------------------------------------------------------

def merge_item_into_event(
    item: Dict[str, Any],
    event: Dict[str, Any]
) -> None:

    event[
        "related_items"
    ].append(
        item
    )

    event[
        "related_item_count"
    ] = len(
        event[
            "related_items"
        ]
    )

    event[
        "countries"
    ] = unique_merge(
        event.get(
            "countries",
            []
        ),
        item.get(
            "countries",
            []
        )
    )

    event[
        "categories"
    ] = unique_merge(
        event.get(
            "categories",
            []
        ),
        item.get(
            "categories",
            []
        )
    )

    event[
        "actors"
    ] = unique_merge(
        event.get(
            "actors",
            []
        ),
        item.get(
            "actors",
            []
        )
    )

    event[
        "locations"
    ] = unique_merge(
        event.get(
            "locations",
            []
        ),
        item.get(
            "locations",
            []
        )
    )

    source_name = item.get(
        "source_name",
        "Unknown source"
    )

    source_group = item.get(
        "source_group",
        "unknown"
    )

    method = item.get(
        "collection_method",
        "rss"
    )

    event[
        "source_names"
    ] = unique_merge(
        event.get(
            "source_names",
            []
        ),
        [
            source_name
        ]
    )

    event[
        "source_groups"
    ] = unique_merge(
        event.get(
            "source_groups",
            []
        ),
        [
            source_group
        ]
    )

    event[
        "collection_methods"
    ] = unique_merge(
        event.get(
            "collection_methods",
            []
        ),
        [
            method
        ]
    )

    event[
        "related_titles"
    ] = unique_merge(
        event.get(
            "related_titles",
            []
        ),
        [
            item.get(
                "title",
                ""
            )
        ]
    )

    event[
        "related_urls"
    ] = unique_merge(
        event.get(
            "related_urls",
            []
        ),
        [
            item.get(
                "url",
                ""
            )
        ]
    )

    event[
        "source_count"
    ] = len(
        event.get(
            "source_names",
            []
        )
    )

    event[
        "relevance_score"
    ] = round(
        sum(
            float(
                i.get(
                    "relevance_score",
                    0
                )
            )
            for i
            in event[
                "related_items"
            ]
        )
        / len(
            event[
                "related_items"
            ]
        ),
        2
    )

    confidence = calculate_confidence(
        event[
            "source_count"
        ],
        len(
            event.get(
                "source_groups",
                []
            )
        ),
        event.get(
            "source_names",
            []
        )
    )

    event[
        "confidence"
    ] = confidence[
        "confidence"
    ]

    event[
        "confidence_score"
    ] = confidence[
        "confidence_score"
    ]

    event[
        "primary_country"
    ] = choose_primary_country_v2(
        event
    )

    event[
        "event_subtype"
    ] = classify_event_subtype(
        event
    )

    event[
        "event_type"
    ] = classify_event_type(
        event[
            "event_subtype"
        ]
    )

    event[
        "analytical_layer"
    ] = classify_analytical_layer(
        event
    )


# ---------------------------------------------------------------------
# CLUSTER EXECUTION
# ---------------------------------------------------------------------

def cluster_items(
    items: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:

    events: List[
        Dict[str, Any]
    ] = []

    sorted_items = sorted(
        items,
        key=lambda item: (
            (
                item.get(
                    "published_at"
                )
                or ""
            ),
            float(
                item.get(
                    "relevance_score",
                    0
                )
            )
        ),
        reverse=True
    )

    for item in sorted_items:

        matched_event = None

        for event in events:

            if should_merge(
                item,
                event
            ):

                matched_event = event

                break

        if matched_event:

            merge_item_into_event(
                item,
                matched_event
            )

        else:

            events.append(
                create_event_from_item(
                    item
                )
            )

    return events


# ---------------------------------------------------------------------
# OUTPUT CLEANING
# ---------------------------------------------------------------------

def clean_event_for_output(
    event: Dict[str, Any]
) -> Dict[str, Any]:

    output = dict(
        event
    )

    output.pop(
        "related_items",
        None
    )

    output[
        "related_titles"
    ] = output.get(
        "related_titles",
        []
    )[:10]

    output[
        "related_urls"
    ] = output.get(
        "related_urls",
        []
    )[:10]

    return output


# ---------------------------------------------------------------------
# SUMMARY
# ---------------------------------------------------------------------

def build_summary(
    events: List[Dict[str, Any]]
) -> Dict[str, Any]:

    by_country: Dict[
        str,
        int
    ] = {}

    by_category: Dict[
        str,
        int
    ] = {}

    by_actor: Dict[
        str,
        int
    ] = {}

    by_event_type: Dict[
        str,
        int
    ] = {
        "operational": 0,
        "warning": 0,
        "background": 0
    }

    by_event_subtype: Dict[
        str,
        int
    ] = {
        "incident": 0,
        "activity": 0,
        "indicator": 0,
        "assessment": 0
    }

    by_analytical_layer: Dict[
        str,
        int
    ] = {
        "information": 0,
        "early_warning": 0,
        "operational": 0,
        "assessment": 0
    }

    for event in events:

        event_type = event.get(
            "event_type",
            "background"
        )

        event_subtype = event.get(
            "event_subtype",
            "assessment"
        )

        analytical_layer = event.get(
            "analytical_layer",
            "assessment"
        )

        by_event_type[
            event_type
        ] = (
            by_event_type.get(
                event_type,
                0
            )
            + 1
        )

        by_event_subtype[
            event_subtype
        ] = (
            by_event_subtype.get(
                event_subtype,
                0
            )
            + 1
        )

        by_analytical_layer[
            analytical_layer
        ] = (
            by_analytical_layer.get(
                analytical_layer,
                0
            )
            + 1
        )

        primary = event.get(
            "primary_country",
            "Regional"
        )

        by_country[
            primary
        ] = (
            by_country.get(
                primary,
                0
            )
            + 1
        )

        for category in event.get(
            "categories",
            []
        ):

            by_category[
                category
            ] = (
                by_category.get(
                    category,
                    0
                )
                + 1
            )

        for actor in event.get(
            "actors",
            []
        ):

            by_actor[
                actor
            ] = (
                by_actor.get(
                    actor,
                    0
                )
                + 1
            )

    return {
        "by_event_type":
            by_event_type,

        "by_event_subtype":
            by_event_subtype,

        "by_analytical_layer":
            by_analytical_layer,

        "by_primary_country":
            dict(
                sorted(
                    by_country.items()
                )
            ),

        "by_category":
            dict(
                sorted(
                    by_category.items()
                )
            ),

        "by_actor":
            dict(
                sorted(
                    by_actor.items()
                )
            )
    }


# ---------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------

def main() -> None:

    filtered = load_json(
        FILTERED_INPUT
    )

    items = filtered.get(
        "items",
        []
    )

    events = cluster_items(
        items
    )

    output_events = [
        clean_event_for_output(
            event
        )
        for event
        in events
    ]

    payload = {
        "project":
            filtered.get(
                "project",
                "baltic-hybrid-monitor"
            ),

        "region":
            filtered.get(
                "region",
                "Baltic states and Poland"
            ),

        "generated_at":
            datetime.now(
                timezone.utc
            ).isoformat(),

        "input_generated_at":
            filtered.get(
                "generated_at"
            ),

        "raw_item_count":
            filtered.get(
                "raw_item_count"
            ),

        "filtered_item_count":
            filtered.get(
                "item_count"
            ),

        "event_count":
            len(
                output_events
            ),

        "merged_item_count":
            (
                len(
                    items
                )
                - len(
                    output_events
                )
            ),

        "summary":
            build_summary(
                output_events
            ),

        "method": {
            "description":
                (
                    "Threat Intelligence Engine v1.3 event clustering "
                    "with nullable publication-time compatibility and "
                    "boundary-aware context classification."
                ),

            "rules": [
                (
                    "merge items with high title similarity"
                ),
                (
                    "merge moderately similar items when "
                    "actor/category/country context overlaps"
                ),
                (
                    "calculate primary country using weighted title, "
                    "summary, URL, location and related item signals"
                ),
                (
                    "calculate confidence using source count, "
                    "source diversity and official-source bonus"
                ),
                (
                    "use word and phrase boundary-aware matching "
                    "instead of raw substring matching"
                ),
                (
                    "distinguish confirmed incidents from warnings "
                    "and possible future events"
                ),
                (
                    "prioritize procurement, investment and capability "
                    "development context over incidental threat words"
                ),
                (
                    "use primary title and summary as stronger "
                    "classification evidence than related titles"
                ),
                (
                    "classify event subtype as incident, activity, "
                    "indicator or assessment"
                ),
                (
                    "classify analytical layer as information, "
                    "early_warning, operational or assessment"
                ),
                (
                    "preserve related titles and URLs"
                )
            ],

            "threat_ontology": {
                "incident":
                    (
                        "Reported concrete operational incident "
                        "supported by explicit event/action language."
                    ),

                "activity":
                    (
                        "Concrete military or security activity "
                        "that shapes the threat environment."
                    ),

                "indicator":
                    (
                        "Early warning, possible future event, "
                        "threat signal or information-operation signal."
                    ),

                "assessment":
                    (
                        "Strategic, institutional, political, "
                        "procurement, investment, capability-development "
                        "or analytical background."
                    )
            },

            "analytical_layers": {
                "information":
                    (
                        "Information manipulation, disinformation "
                        "or influence-operation signal."
                    ),

                "early_warning":
                    (
                        "Warning, forecast or precursor signal "
                        "without a confirmed operational incident."
                    ),

                "operational":
                    (
                        "Reported incident or concrete operational "
                        "security/military activity."
                    ),

                "assessment":
                    (
                        "Analytical, policy, investment, preparedness, "
                        "procurement or institutional background."
                    )
            },

            "classification_version":
                "ontology_v1_3_nullable_publication_time"
        },

        "events":
            output_events
    }

    save_json(
        CLUSTERED_OUTPUT,
        payload
    )

    save_json(
        DOCS_CLUSTERED_OUTPUT,
        payload
    )

    print(
        f"Filtered items: "
        f"{len(items)}"
    )

    print(
        f"Clustered events: "
        f"{len(output_events)}"
    )

    print(
        f"Merged items: "
        f"{len(items) - len(output_events)}"
    )

    print(
        "Classification model: Threat Intelligence Engine v1.3"
    )

    print(
        "Term matching: boundary-aware"
    )

    print(
        "Capability-development override: enabled"
    )

    print(
        f"Saved: "
        f"{CLUSTERED_OUTPUT}"
    )

    print(
        f"Saved: "
        f"{DOCS_CLUSTERED_OUTPUT}"
    )


if __name__ == "__main__":
    main()
