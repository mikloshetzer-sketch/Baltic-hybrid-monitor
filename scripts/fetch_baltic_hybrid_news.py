import json
import os
import re
import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Any, Optional, Set
from urllib.parse import urlparse, urljoin

import feedparser
import requests
from bs4 import BeautifulSoup
from dateutil import parser as date_parser


ROOT = Path(__file__).resolve().parents[1]

CONFIG_PATH = ROOT / "config" / "baltic_sources.json"
RAW_OUTPUT = ROOT / "data" / "baltic_hybrid_raw_news.json"
DOCS_OUTPUT = ROOT / "docs" / "data" / "baltic_hybrid_raw_news.json"


# ---------------------------------------------------------------------
# THREAT INTELLIGENCE COLLECTOR v1.1
#
# Goal:
#
# Collect a broad but meaningful candidate set for Baltic / Polish
# hybrid-threat monitoring.
#
# This collector is NOT the final relevance filter.
#
# It should:
# - avoid obvious semantic false positives;
# - assign categories more carefully;
# - distinguish regional context from source origin;
# - keep plausible threat indicators;
# - leave final relevance decisions to filter_baltic_hybrid_news.py.
# ---------------------------------------------------------------------


COUNTRY_KEYWORDS = {
    "Estonia": [
        "estonia",
        "estonian",
        "tallinn",
        "narva",
        "tartu",
        "ida-viru",
        "ida-virumaa"
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
        "gdańsk"
    ]
}


REGIONAL_KEYWORDS = [
    "baltic states",
    "baltics",
    "baltic region",
    "baltic sea",
    "eastern flank",
    "nato eastern flank"
]


LOCATION_KEYWORDS = {
    "Kaliningrad": [
        "kaliningrad",
        "russian enclave"
    ],
    "Suwalki Gap": [
        "suwalki gap",
        "suwałki gap"
    ],
    "Baltic Sea": [
        "baltic sea",
        "gulf of finland",
        "gulf of riga"
    ],
    "Narva": [
        "narva"
    ],
    "Riga": [
        "riga"
    ],
    "Tallinn": [
        "tallinn"
    ],
    "Vilnius": [
        "vilnius"
    ],
    "Klaipeda": [
        "klaipeda",
        "klaipėda"
    ],
    "Gdansk": [
        "gdansk",
        "gdańsk"
    ],
    "Belarus Border": [
        "belarus border",
        "border with belarus",
        "belarusian border"
    ],
    "Poland-Belarus Border": [
        "poland-belarus border",
        "polish-belarusian border"
    ]
}


# ---------------------------------------------------------------------
# ACTORS
#
# Institutional actors deliberately use stricter expressions.
# "EU" or "alliance" alone are too noisy.
# ---------------------------------------------------------------------


ACTOR_KEYWORDS = {
    "Russia": [
        "russia",
        "russian",
        "russian federation",
        "kremlin",
        "putin"
    ],
    "Belarus": [
        "belarus",
        "belarusian",
        "lukashenko"
    ],
    "NATO": [
        "nato",
        "north atlantic treaty organization",
        "north atlantic alliance",
        "nato eastern flank",
        "nato air policing"
    ],
    "EU": [
        "european union",
        "eu commission",
        "european commission",
        "european council",
        "eeas",
        "enisa",
        "frontex"
    ],
    "GRU": [
        "gru",
        "russian military intelligence"
    ],
    "FSB": [
        "fsb",
        "federal security service"
    ],
    "Sandworm": [
        "sandworm",
        "electrum"
    ]
}


# ---------------------------------------------------------------------
# CATEGORY SIGNALS
#
# Categories are now context-aware.
#
# Generic words such as:
#   migration
#   explosive
#   port
#   airport
#   cyber
#
# are NOT enough by themselves to create a threat category.
# ---------------------------------------------------------------------


SABOTAGE_TERMS = [
    "sabotage",
    "sabotage attack",
    "sabotage operation",
    "sabotage incident",
    "sabotage attempt",
    "rail sabotage",
    "infrastructure sabotage",
    "arson attack",
    "deliberate arson",
    "suspected arson",
    "deliberate explosion",
    "explosive device",
    "incendiary device",
    "subversion"
]


CYBER_ATTACK_TERMS = [
    "cyberattack",
    "cyber attack",
    "cyber attacks",
    "ddos attack",
    "distributed denial of service",
    "malware attack",
    "ransomware attack",
    "wiper attack",
    "phishing campaign",
    "credential theft campaign",
    "systems breached",
    "network breached",
    "data breach",
    "state-sponsored cyberattack",
    "state sponsored cyberattack",
    "cyber espionage",
    "cyber sabotage",
    "apt campaign"
]


CYBER_CONTEXT_TERMS = [
    "cyber",
    "cybersecurity",
    "malware",
    "ransomware",
    "phishing",
    "ddos",
    "wiper",
    "hackers",
    "hacking",
    "zero-day",
    "zero day",
    "apt"
]


DISINFORMATION_TERMS = [
    "disinformation",
    "misinformation",
    "propaganda",
    "fake news",
    "influence operation",
    "information operation",
    "cognitive warfare",
    "cognitive war",
    "information warfare",
    "bot network",
    "foreign information manipulation",
    "influence campaign"
]


BORDER_PRESSURE_TERMS = [
    "border pressure",
    "border incident",
    "border provocation",
    "border crisis",
    "illegal border crossing",
    "illegal crossing",
    "border breach",
    "pushback",
    "tunnel under border",
    "tunnel beneath border",
    "border tunnel"
]


MIGRATION_PRESSURE_TERMS = [
    "migration pressure",
    "migrant pressure",
    "migrants at border",
    "migrants on border",
    "asylum seekers at border",
    "instrumentalised migration",
    "instrumentalized migration",
    "weaponised migration",
    "weaponized migration",
    "belarus migrants",
    "belarusian migrant pressure",
    "migrant weaponisation",
    "migrant weaponization"
]


GPS_INTERFERENCE_TERMS = [
    "gps jamming",
    "gnss jamming",
    "gps interference",
    "gnss interference",
    "gps spoofing",
    "gnss spoofing",
    "navigation interference",
    "satellite navigation interference",
    "signal interference"
]


DRONE_INCIDENT_TERMS = [
    "drone incident",
    "drone incursion",
    "drone intrusion",
    "drone entered",
    "drone crossed",
    "drone crash",
    "drone crashed",
    "drone shot down",
    "drone debris",
    "unauthorized drone",
    "unidentified drone",
    "uav incursion",
    "uav entered",
    "airspace violation",
    "airspace incursion",
    "violated airspace",
    "entered airspace"
]


MILITARY_PROVOCATION_TERMS = [
    "military provocation",
    "fighter jet interception",
    "fighter jets intercepted",
    "fighter jets scrambled",
    "scrambled fighter jets",
    "missile entered",
    "missile crossed",
    "missile incursion",
    "warship provocation",
    "naval provocation",
    "unsafe interception",
    "air policing incident"
]


MILITARY_ACTIVITY_TERMS = [
    "military exercise",
    "military exercises",
    "military drill",
    "military drills",
    "air policing",
    "troop movement",
    "troop deployment",
    "force movement",
    "military buildup",
    "military build-up",
    "deployment"
]


CRITICAL_INFRASTRUCTURE_TERMS = [
    "critical infrastructure"
]


INFRASTRUCTURE_ASSET_TERMS = [
    "power grid",
    "energy grid",
    "pipeline",
    "lng terminal",
    "substation",
    "railway",
    "rail network",
    "port",
    "harbour",
    "airport",
    "telecom network",
    "telecommunications network",
    "undersea cable",
    "subsea cable",
    "communication cable",
    "power cable"
]


INFRASTRUCTURE_INCIDENT_TERMS = [
    "infrastructure attack",
    "infrastructure sabotage",
    "infrastructure damaged",
    "infrastructure damage",
    "cable damaged",
    "cable cut",
    "cable sabotage",
    "pipeline damaged",
    "pipeline sabotage",
    "grid attack",
    "power grid attack",
    "substation attack",
    "airport disruption",
    "port disruption",
    "rail sabotage",
    "telecom disruption",
    "undersea cable damaged",
    "subsea cable damaged"
]


ESPIONAGE_TERMS = [
    "espionage",
    "spying",
    "spy arrested",
    "arrested spy",
    "intelligence agent",
    "foreign agent",
    "russian agent",
    "belarusian agent",
    "counterintelligence",
    "intelligence service",
    "gru",
    "fsb",
    "svr"
]


# ---------------------------------------------------------------------
# WARNING / THREAT TERMS
# ---------------------------------------------------------------------


WARNING_TERMS = [
    "warns",
    "warned",
    "warning",
    "threat",
    "threatens",
    "threatened",
    "risk of attack",
    "risk of sabotage",
    "risk of escalation",
    "could attack",
    "could stage",
    "could strike",
    "could sabotage",
    "may attack",
    "may sabotage",
    "might attack",
    "possible attack",
    "potential attack",
    "potential sabotage",
    "false flag",
    "intelligence warning"
]


# ---------------------------------------------------------------------
# NEGATIVE SEMANTIC CONTEXT
#
# These help prevent known semantic false positives.
# ---------------------------------------------------------------------


MIGRATION_FALSE_POSITIVE_TERMS = [
    "bird migration",
    "birds migrate",
    "migration season",
    "migration nears",
    "animal migration",
    "crane migration",
    "cranes migrate",
    "migratory birds"
]


EXPLOSIVES_INDUSTRY_TERMS = [
    "explosives factory",
    "explosives plant",
    "explosive factory",
    "explosive plant",
    "explosives production",
    "explosives manufacturing",
    "warhead factory",
    "warhead plant",
    "production facility for explosives",
    "manufacturing complex",
    "manufacturing facility",
    "defence company",
    "defense company",
    "production set to begin",
    "plans to build",
    "plans to set up",
    "to invest",
    "will invest"
]


INFRASTRUCTURE_DEVELOPMENT_TERMS = [
    "to build",
    "will build",
    "plans to build",
    "being built",
    "under construction",
    "construction project",
    "investment",
    "to invest",
    "will invest",
    "upgrade",
    "modernisation",
    "modernization",
    "expansion",
    "new terminal",
    "new airport",
    "new port",
    "new plant",
    "new facility"
]


GENERAL_CYBER_NOISE_TERMS = [
    "cybersecurity challenge",
    "international cybersecurity challenge",
    "cybersecurity competition",
    "cyber resilience act",
    "certification",
    "managed security services",
    "cybersecurity reserve",
    "cybersecurity investment",
    "cybersecurity investments",
    "cyber hygiene",
    "cyber skills",
    "training course",
    "training programme",
    "training program",
    "conference",
    "webinar",
    "workshop"
]


# ---------------------------------------------------------------------
# QUALITY / NOISE
# ---------------------------------------------------------------------


LOW_QUALITY_DOMAINS = [
    "youtube.com",
    "youtu.be",
    "tiktok.com",
    "facebook.com",
    "reddit.com"
]


HARD_EXCLUDE_TERMS = [
    "sports",
    "football",
    "basketball",
    "tennis",
    "volleyball",
    "celebrity",
    "movie",
    "film festival",
    "music festival",
    "concert",
    "chopin",
    "violin",
    "orchestra",
    "theatre",
    "theater",
    "recipe",
    "fashion",
    "tourism guide",
    "mountaineering",
    "charity drive",
    "parade",
    "culture festival",
    "flamingo",
    "climate neutral agency"
]


STATIC_PAGE_TERMS = [
    "member countries",
    "secretary general",
    "permanent representatives",
    "audit reports",
    "financial statements",
    "performance audit",
    "organization",
    "nato structure",
    "cybersecurity material",
    "awareness and cyber hygiene",
    "cybersecurity policies",
    "state of cybersecurity in the eu",
    "for national / eu authorities",
    "topic",
    "topics",
    "press office"
]


# ---------------------------------------------------------------------
# BROAD SECURITY TERMS
#
# Used only as supporting evidence.
# A match here is NOT enough to create a threat category by itself.
# ---------------------------------------------------------------------


REQUIRED_SECURITY_TERMS = [
    "russia",
    "russian",
    "belarus",
    "belarusian",
    "kremlin",
    "nato",
    "security",
    "defence",
    "defense",
    "military",
    "hybrid",
    "sabotage",
    "cyber",
    "attack",
    "threat",
    "border",
    "drone",
    "uav",
    "airspace",
    "gps",
    "gnss",
    "jamming",
    "spoofing",
    "disinformation",
    "propaganda",
    "espionage",
    "spy",
    "critical infrastructure",
    "migration pressure",
    "intelligence",
    "kaliningrad",
    "suwalki",
    "baltic sea",
    "eastern flank"
]


FALLBACK_HOMEPAGES = {
    "LRT English Lithuania":
        "https://www.lrt.lt/en/news-in-english",

    "Polish Radio English":
        "https://www.polskieradio.pl/395",

    "TVP World":
        "https://tvpworld.com/",

    "NATO News":
        "https://www.nato.int/cps/en/natohq/news.htm",

    "ENISA News":
        "https://www.enisa.europa.eu/news"
}


# ---------------------------------------------------------------------
# IO
# ---------------------------------------------------------------------


def load_config() -> Dict[str, Any]:

    if not CONFIG_PATH.exists():

        raise FileNotFoundError(
            f"Missing config file: {CONFIG_PATH}"
        )

    return json.loads(
        CONFIG_PATH.read_text(
            encoding="utf-8"
        )
    )


def clean_text(
    value: str
) -> str:

    value = re.sub(
        r"<[^>]+>",
        " ",
        value or ""
    )

    value = re.sub(
        r"&nbsp;",
        " ",
        value
    )

    value = re.sub(
        r"\s+",
        " ",
        value
    )

    return value.strip()


def normalize_for_matching(
    value: str
) -> str:

    value = str(
        value
    ).lower()

    value = re.sub(
        r"https?://\S+",
        " ",
        value
    )

    value = re.sub(
        r"[^a-z0-9áéíóöőúüűąćęłńóśźż\- /]+",
        " ",
        value
    )

    value = re.sub(
        r"\s+",
        " ",
        value
    )

    return value.strip()


# ---------------------------------------------------------------------
# SAFE MATCHING
# ---------------------------------------------------------------------


def contains_term(
    text: str,
    term: str
) -> bool:

    normalized_text = normalize_for_matching(
        text
    )

    normalized_term = normalize_for_matching(
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


def detect_from_keywords(
    text: str,
    mapping: Dict[str, List[str]]
) -> List[str]:

    found = []

    for label, keywords in mapping.items():

        if contains_any(
            text,
            keywords
        ):

            found.append(
                label
            )

    return found


# ---------------------------------------------------------------------
# UTILITIES
# ---------------------------------------------------------------------


def stable_id(
    *parts: str
) -> str:

    raw = "|".join(
        parts
    )

    return hashlib.sha256(
        raw.encode(
            "utf-8"
        )
    ).hexdigest()[:16]


def canonical_title(
    title: str
) -> str:

    title = title.lower()

    title = re.sub(
        r"\s*-\s*[^-]{2,80}$",
        "",
        title
    )

    title = re.sub(
        r"[^a-z0-9áéíóöőúüűąćęłńóśźż ]+",
        " ",
        title
    )

    title = re.sub(
        r"\s+",
        " ",
        title
    )

    return title.strip()


def parse_date(
    entry: Any
) -> str:

    for key in [
        "published",
        "updated",
        "created"
    ]:

        if getattr(
            entry,
            key,
            None
        ):

            try:

                dt = date_parser.parse(
                    getattr(
                        entry,
                        key
                    )
                )

                if not dt.tzinfo:

                    dt = dt.replace(
                        tzinfo=timezone.utc
                    )

                return dt.astimezone(
                    timezone.utc
                ).isoformat()

            except Exception:
                pass

    return datetime.now(
        timezone.utc
    ).isoformat()


def get_domain(
    url: str
) -> str:

    try:

        parsed = urlparse(
            url
        )

        return parsed.netloc.replace(
            "www.",
            ""
        )

    except Exception:

        return ""


def is_low_quality_url(
    url: str
) -> bool:

    domain = get_domain(
        url
    )

    return any(
        blocked in domain
        for blocked
        in LOW_QUALITY_DOMAINS
    )


# ---------------------------------------------------------------------
# COUNTRY DETECTION
#
# Source country is NOT automatically added anymore.
#
# It is only recorded separately as source_country.
# ---------------------------------------------------------------------


def detect_countries(
    text: str
) -> List[str]:

    return detect_from_keywords(
        text,
        COUNTRY_KEYWORDS
    )


def detect_regional_context(
    text: str
) -> bool:

    return contains_any(
        text,
        REGIONAL_KEYWORDS
    )


# ---------------------------------------------------------------------
# ACTOR DETECTION
# ---------------------------------------------------------------------


def detect_actors(
    text: str
) -> List[str]:

    return detect_from_keywords(
        text,
        ACTOR_KEYWORDS
    )


# ---------------------------------------------------------------------
# LOCATION DETECTION
# ---------------------------------------------------------------------


def detect_locations(
    text: str
) -> List[str]:

    return detect_from_keywords(
        text,
        LOCATION_KEYWORDS
    )


# ---------------------------------------------------------------------
# CATEGORY DETECTION
# ---------------------------------------------------------------------


def detect_categories(
    text: str
) -> List[str]:

    categories: Set[str] = set()

    # -------------------------------------------------------------
    # SABOTAGE
    # -------------------------------------------------------------

    if contains_any(
        text,
        SABOTAGE_TERMS
    ):

        if not (
            contains_any(
                text,
                EXPLOSIVES_INDUSTRY_TERMS
            )
            and not contains_term(
                text,
                "sabotage"
            )
        ):

            categories.add(
                "sabotage"
            )

    # -------------------------------------------------------------
    # CYBER
    #
    # Generic "cyber" alone is not enough.
    # -------------------------------------------------------------

    if contains_any(
        text,
        CYBER_ATTACK_TERMS
    ):

        categories.add(
            "cyber"
        )

    # -------------------------------------------------------------
    # DISINFORMATION
    # -------------------------------------------------------------

    if contains_any(
        text,
        DISINFORMATION_TERMS
    ):

        categories.add(
            "disinformation"
        )

    # -------------------------------------------------------------
    # BORDER PRESSURE
    # -------------------------------------------------------------

    if contains_any(
        text,
        BORDER_PRESSURE_TERMS
    ):

        categories.add(
            "border_pressure"
        )

    # -------------------------------------------------------------
    # MIGRATION PRESSURE
    #
    # "migration" alone is deliberately not a trigger.
    # -------------------------------------------------------------

    if (
        contains_any(
            text,
            MIGRATION_PRESSURE_TERMS
        )
        and not contains_any(
            text,
            MIGRATION_FALSE_POSITIVE_TERMS
        )
    ):

        categories.add(
            "migration_pressure"
        )

    # -------------------------------------------------------------
    # GPS / GNSS
    # -------------------------------------------------------------

    if contains_any(
        text,
        GPS_INTERFERENCE_TERMS
    ):

        categories.add(
            "gps_interference"
        )

    # -------------------------------------------------------------
    # DRONE / AIRSPACE
    # -------------------------------------------------------------

    if contains_any(
        text,
        DRONE_INCIDENT_TERMS
    ):

        categories.add(
            "drone_incident"
        )

    # -------------------------------------------------------------
    # MILITARY PROVOCATION
    # -------------------------------------------------------------

    if contains_any(
        text,
        MILITARY_PROVOCATION_TERMS
    ):

        categories.add(
            "military_provocation"
        )

    # -------------------------------------------------------------
    # CRITICAL INFRASTRUCTURE
    #
    # Asset mention alone is insufficient.
    # -------------------------------------------------------------

    infrastructure_asset = (
        contains_any(
            text,
            INFRASTRUCTURE_ASSET_TERMS
        )
        or contains_any(
            text,
            CRITICAL_INFRASTRUCTURE_TERMS
        )
    )

    infrastructure_incident = (
        contains_any(
            text,
            INFRASTRUCTURE_INCIDENT_TERMS
        )
    )

    infrastructure_warning = (
        infrastructure_asset
        and contains_any(
            text,
            WARNING_TERMS
        )
    )

    infrastructure_development = (
        infrastructure_asset
        and contains_any(
            text,
            INFRASTRUCTURE_DEVELOPMENT_TERMS
        )
    )

    if (
        infrastructure_incident
        or (
            infrastructure_warning
            and not infrastructure_development
        )
    ):

        categories.add(
            "critical_infrastructure"
        )

    # -------------------------------------------------------------
    # ESPIONAGE
    # -------------------------------------------------------------

    if contains_any(
        text,
        ESPIONAGE_TERMS
    ):

        categories.add(
            "espionage"
        )

    return sorted(
        categories
    )


# ---------------------------------------------------------------------
# SIGNAL HELPERS
# ---------------------------------------------------------------------


def has_hostile_actor(
    actors: List[str]
) -> bool:

    return bool(
        set(
            actors
        )
        & {
            "Russia",
            "Belarus",
            "GRU",
            "FSB",
            "Sandworm"
        }
    )


def has_strong_operational_signal(
    text: str
) -> bool:

    return any([
        contains_any(
            text,
            SABOTAGE_TERMS
        ),
        contains_any(
            text,
            CYBER_ATTACK_TERMS
        ),
        contains_any(
            text,
            GPS_INTERFERENCE_TERMS
        ),
        contains_any(
            text,
            DRONE_INCIDENT_TERMS
        ),
        contains_any(
            text,
            BORDER_PRESSURE_TERMS
        ),
        contains_any(
            text,
            MIGRATION_PRESSURE_TERMS
        ),
        contains_any(
            text,
            MILITARY_PROVOCATION_TERMS
        ),
        contains_any(
            text,
            INFRASTRUCTURE_INCIDENT_TERMS
        ),
        contains_any(
            text,
            ESPIONAGE_TERMS
        )
    ])


def has_warning_signal(
    text: str
) -> bool:

    return contains_any(
        text,
        WARNING_TERMS
    )


def has_security_context(
    text: str
) -> bool:

    return contains_any(
        text,
        REQUIRED_SECURITY_TERMS
    )


def has_general_cyber_context(
    text: str
) -> bool:

    return contains_any(
        text,
        CYBER_CONTEXT_TERMS
    )


def is_general_cyber_noise(
    text: str
) -> bool:

    return contains_any(
        text,
        GENERAL_CYBER_NOISE_TERMS
    )


# ---------------------------------------------------------------------
# RELEVANCE SCORE
#
# Relevance is now context-based rather than raw keyword volume.
# ---------------------------------------------------------------------


def rough_relevance_score(
    text: str,
    source_weight: float,
    countries: List[str],
    categories: List[str],
    actors: List[str],
    locations: List[str],
    regional_context: bool
) -> float:

    score = 0.0

    hostile_actor = has_hostile_actor(
        actors
    )

    operational_signal = (
        has_strong_operational_signal(
            text
        )
    )

    warning_signal = (
        has_warning_signal(
            text
        )
    )

    # Regional grounding
    if countries:
        score += min(
            len(
                countries
            ),
            2
        ) * 1.5

    if regional_context:
        score += 1.5

    if locations:
        score += min(
            len(
                locations
            ),
            2
        ) * 1.0

    # Threat categories
    score += min(
        len(
            categories
        ),
        3
    ) * 2.0

    # Actors
    if hostile_actor:
        score += 2.5

    elif actors:
        score += 0.5

    # Operational evidence
    if operational_signal:
        score += 3.0

    # Warning evidence
    if warning_signal:
        score += 1.5

    # Especially useful combinations
    if (
        hostile_actor
        and (
            countries
            or regional_context
            or locations
        )
    ):
        score += 2.0

    if (
        hostile_actor
        and operational_signal
    ):
        score += 2.0

    if (
        categories
        and (
            countries
            or regional_context
        )
    ):
        score += 1.0

    # General cyber without an actual incident gets very little value.
    if (
        has_general_cyber_context(
            text
        )
        and not (
            "cyber" in categories
        )
    ):
        score += 0.25

    return round(
        score * source_weight,
        2
    )


# ---------------------------------------------------------------------
# HTML FALLBACK CANDIDATES
# ---------------------------------------------------------------------


def is_relevant_html_candidate(
    title: str,
    url: str,
    source_name: str
) -> bool:

    text = (
        f"{title} {url}"
    )

    if len(
        title.strip()
    ) < 25:

        return False

    if contains_any(
        text,
        HARD_EXCLUDE_TERMS
    ):

        return False

    if contains_any(
        text,
        STATIC_PAGE_TERMS
    ):

        return False

    if source_name == "NATO News":

        if (
            "/news/"
            not in url
            and "news.htm"
            not in url
        ):

            return False

    if source_name == "ENISA News":

        if "/news/" not in url:

            return False

    if source_name in [
        "Polish Radio English",
        "LRT English Lithuania",
        "TVP World"
    ]:

        if not has_security_context(
            text
        ):

            return False

    return True


# ---------------------------------------------------------------------
# RAW COLLECTION GATE
#
# This remains deliberately broader than the downstream relevance
# filter but no longer accepts a story just because one weak label
# exists.
# ---------------------------------------------------------------------


def should_keep_item(
    title: str,
    summary: str,
    countries: List[str],
    categories: List[str],
    actors: List[str],
    locations: List[str],
    regional_context: bool,
    score: float,
    url: str,
    collection_method: str = "rss"
) -> bool:

    text = (
        f"{title} {summary} {url}"
    )

    if is_low_quality_url(
        url
    ):

        return False

    if contains_any(
        text,
        HARD_EXCLUDE_TERMS
    ):

        return False

    hostile_actor = (
        has_hostile_actor(
            actors
        )
    )

    operational_signal = (
        has_strong_operational_signal(
            text
        )
    )

    warning_signal = (
        has_warning_signal(
            text
        )
    )

    regional_signal = bool(
        countries
        or locations
        or regional_context
    )

    threat_category = bool(
        categories
    )

    # -------------------------------------------------------------
    # HTML fallback is deliberately stricter
    # -------------------------------------------------------------

    if collection_method == "html_fallback":

        if contains_any(
            text,
            STATIC_PAGE_TERMS
        ):

            return False

        if not has_security_context(
            text
        ):

            return False

        if (
            is_general_cyber_noise(
                text
            )
            and not hostile_actor
            and not operational_signal
        ):

            return False

        if (
            hostile_actor
            and (
                operational_signal
                or warning_signal
                or regional_signal
            )
        ):

            return True

        if (
            regional_signal
            and (
                threat_category
                or operational_signal
                or warning_signal
            )
        ):

            return True

        if score >= 5.5:

            return True

        return False

    # -------------------------------------------------------------
    # RSS / external JSON
    # -------------------------------------------------------------

    if (
        hostile_actor
        and operational_signal
    ):

        return True

    if (
        hostile_actor
        and warning_signal
        and (
            regional_signal
            or threat_category
        )
    ):

        return True

    if (
        regional_signal
        and operational_signal
    ):

        return True

    if (
        regional_signal
        and threat_category
    ):

        return True

    if (
        hostile_actor
        and regional_signal
        and score >= 4.0
    ):

        return True

    if (
        threat_category
        and score >= 5.0
    ):

        return True

    if (
        regional_signal
        and warning_signal
        and score >= 4.0
    ):

        return True

    return False


# ---------------------------------------------------------------------
# ITEM BUILDER
# ---------------------------------------------------------------------


def build_item(
    title: str,
    summary: str,
    url: str,
    published_at: str,
    source: Dict[str, Any],
    collection_method: str = "rss"
) -> Optional[Dict[str, Any]]:

    source_weight = float(
        source.get(
            "weight",
            1.0
        )
    )

    source_country = source.get(
        "country"
    )

    combined = (
        f"{title} {summary} {url}"
    )

    countries = detect_countries(
        combined
    )

    regional_context = (
        detect_regional_context(
            combined
        )
    )

    categories = detect_categories(
        combined
    )

    actors = detect_actors(
        combined
    )

    locations = detect_locations(
        combined
    )

    relevance = rough_relevance_score(
        text=combined,
        source_weight=source_weight,
        countries=countries,
        categories=categories,
        actors=actors,
        locations=locations,
        regional_context=regional_context
    )

    if not should_keep_item(
        title=title,
        summary=summary,
        countries=countries,
        categories=categories,
        actors=actors,
        locations=locations,
        regional_context=regional_context,
        score=relevance,
        url=url,
        collection_method=collection_method
    ):

        return None

    item_id = stable_id(
        canonical_title(
            title
        ),
        published_at[:10],
        source.get(
            "name",
            ""
        )
    )

    return {
        "id":
            item_id,

        "title":
            title,

        "summary":
            summary,

        "url":
            url,

        "domain":
            get_domain(
                url
            ),

        "published_at":
            published_at,

        "source_name":
            source.get(
                "name",
                "Unknown source"
            ),

        "source_type":
            source.get(
                "type",
                "rss"
            ),

        "source_group":
            source.get(
                "source_group",
                "unknown"
            ),

        "source_weight":
            source_weight,

        "source_country":
            source_country,

        "countries":
            countries,

        "regional_context":
            regional_context,

        "categories":
            categories,

        "actors":
            actors,

        "locations":
            locations,

        "relevance_score":
            relevance,

        "collection_method":
            collection_method,

        "collected_at":
            datetime.now(
                timezone.utc
            ).isoformat()
    }


# ---------------------------------------------------------------------
# RSS
# ---------------------------------------------------------------------


def fetch_rss_source(
    source: Dict[str, Any]
) -> List[Dict[str, Any]]:

    parsed = feedparser.parse(
        source[
            "url"
        ]
    )

    if (
        len(
            parsed.entries
        ) == 0
        and source.get(
            "name"
        )
        in FALLBACK_HOMEPAGES
    ):

        return fetch_html_fallback_source(
            source
        )

    items = []

    for entry in parsed.entries[:50]:

        title = clean_text(
            getattr(
                entry,
                "title",
                ""
            )
        )

        summary = clean_text(
            getattr(
                entry,
                "summary",
                ""
            )
        )

        link = getattr(
            entry,
            "link",
            ""
        )

        published_at = parse_date(
            entry
        )

        item = build_item(
            title=title,
            summary=summary,
            url=link,
            published_at=published_at,
            source=source,
            collection_method="rss"
        )

        if item:

            items.append(
                item
            )

    return items


# ---------------------------------------------------------------------
# HTML FALLBACK
# ---------------------------------------------------------------------


def fetch_html_fallback_source(
    source: Dict[str, Any]
) -> List[Dict[str, Any]]:

    source_name = source.get(
        "name"
    )

    homepage = FALLBACK_HOMEPAGES.get(
        source_name
    )

    if not homepage:

        return []

    try:

        response = requests.get(
            homepage,
            timeout=25,
            headers={
                "User-Agent":
                    "Mozilla/5.0 BalticHybridMonitor/1.1"
            }
        )

        response.raise_for_status()

    except Exception:

        return []

    soup = BeautifulSoup(
        response.text,
        "html.parser"
    )

    candidates = []

    seen_urls = set()

    for link in soup.find_all(
        "a",
        href=True
    ):

        title = clean_text(
            link.get_text(
                " ",
                strip=True
            )
        )

        href = link.get(
            "href",
            ""
        )

        absolute_url = urljoin(
            homepage,
            href
        )

        if absolute_url in seen_urls:

            continue

        if not is_relevant_html_candidate(
            title,
            absolute_url,
            source_name
        ):

            continue

        seen_urls.add(
            absolute_url
        )

        candidates.append({
            "title":
                title,

            "url":
                absolute_url
        })

        if len(
            candidates
        ) >= 25:

            break

    items = []

    for candidate in candidates:

        item = build_item(
            title=candidate[
                "title"
            ],
            summary="",
            url=candidate[
                "url"
            ],
            published_at=datetime.now(
                timezone.utc
            ).isoformat(),
            source=source,
            collection_method="html_fallback"
        )

        if item:

            items.append(
                item
            )

    return items


# ---------------------------------------------------------------------
# EXTERNAL JSON
# ---------------------------------------------------------------------


def fetch_external_json_feed(
    feed: Dict[str, Any]
) -> List[Dict[str, Any]]:

    env_var = feed.get(
        "env_var"
    )

    url = (
        os.getenv(
            env_var,
            ""
        ).strip()
        if env_var
        else ""
    )

    if not url:

        return []

    try:

        response = requests.get(
            url,
            timeout=25
        )

        response.raise_for_status()

        data = response.json()

    except Exception as exc:

        return [{
            "id":
                stable_id(
                    feed[
                        "name"
                    ],
                    "fetch_error"
                ),

            "title":
                (
                    f"External feed error: "
                    f"{feed['name']}"
                ),

            "summary":
                str(
                    exc
                ),

            "url":
                url,

            "domain":
                get_domain(
                    url
                ),

            "published_at":
                datetime.now(
                    timezone.utc
                ).isoformat(),

            "source_name":
                feed[
                    "name"
                ],

            "source_type":
                "external_error",

            "source_group":
                feed.get(
                    "source_group",
                    "external_json"
                ),

            "source_weight":
                float(
                    feed.get(
                        "weight",
                        1.0
                    )
                ),

            "source_country":
                feed.get(
                    "country"
                ),

            "countries":
                [],

            "regional_context":
                False,

            "categories":
                [],

            "actors":
                [],

            "locations":
                [],

            "relevance_score":
                0,

            "collection_method":
                "external_json_error",

            "collected_at":
                datetime.now(
                    timezone.utc
                ).isoformat()
        }]

    raw_items = data.get(
        "items",
        data
        if isinstance(
            data,
            list
        )
        else []
    )

    output = []

    for raw in raw_items[:150]:

        title = clean_text(
            str(
                raw.get(
                    "title",
                    ""
                )
            )
        )

        summary = clean_text(
            str(
                raw.get(
                    "summary",
                    raw.get(
                        "description",
                        ""
                    )
                )
            )
        )

        item_url = raw.get(
            "url",
            raw.get(
                "link",
                ""
            )
        )

        published_at = raw.get(
            "published_at",
            raw.get(
                "date",
                datetime.now(
                    timezone.utc
                ).isoformat()
            )
        )

        item = build_item(
            title=title,
            summary=summary,
            url=item_url,
            published_at=published_at,
            source=feed,
            collection_method="external_json"
        )

        if item:

            output.append(
                item
            )

    return output


# ---------------------------------------------------------------------
# DEDUPLICATION
# ---------------------------------------------------------------------


def deduplicate(
    items: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:

    grouped: Dict[
        str,
        Dict[str, Any]
    ] = {}

    for item in items:

        key = canonical_title(
            item.get(
                "title",
                ""
            )
        )

        if not key:

            key = item.get(
                "id"
            )

        existing = grouped.get(
            key
        )

        if not existing:

            grouped[
                key
            ] = item

            continue

        existing_score = float(
            existing.get(
                "relevance_score",
                0
            )
        )

        new_score = float(
            item.get(
                "relevance_score",
                0
            )
        )

        if new_score > existing_score:

            grouped[
                key
            ] = item

    unique = list(
        grouped.values()
    )

    return sorted(
        unique,
        key=lambda x: (
            x.get(
                "published_at",
                ""
            ),
            x.get(
                "relevance_score",
                0
            )
        ),
        reverse=True
    )


# ---------------------------------------------------------------------
# SOURCE SUMMARY
# ---------------------------------------------------------------------


def build_source_summary(
    items: List[Dict[str, Any]]
) -> Dict[str, Any]:

    summary = {}

    for item in items:

        source_name = item.get(
            "source_name",
            "Unknown source"
        )

        if source_name not in summary:

            summary[
                source_name
            ] = {
                "source_name":
                    source_name,

                "source_group":
                    item.get(
                        "source_group",
                        "unknown"
                    ),

                "source_type":
                    item.get(
                        "source_type",
                        "unknown"
                    ),

                "item_count":
                    0,

                "rss_count":
                    0,

                "html_fallback_count":
                    0,

                "external_json_count":
                    0
            }

        summary[
            source_name
        ][
            "item_count"
        ] += 1

        method = item.get(
            "collection_method",
            "rss"
        )

        if method == "html_fallback":

            summary[
                source_name
            ][
                "html_fallback_count"
            ] += 1

        elif method == "external_json":

            summary[
                source_name
            ][
                "external_json_count"
            ] += 1

        else:

            summary[
                source_name
            ][
                "rss_count"
            ] += 1

    return dict(
        sorted(
            summary.items(),
            key=lambda pair:
                pair[1][
                    "item_count"
                ],
            reverse=True
        )
    )


# ---------------------------------------------------------------------
# COLLECTION DIAGNOSTICS
# ---------------------------------------------------------------------


def build_diagnostics(
    items: List[Dict[str, Any]]
) -> Dict[str, Any]:

    category_counts: Dict[
        str,
        int
    ] = {}

    actor_counts: Dict[
        str,
        int
    ] = {}

    country_counts: Dict[
        str,
        int
    ] = {}

    regional_context_count = 0

    for item in items:

        if item.get(
            "regional_context"
        ):

            regional_context_count += 1

        for category in item.get(
            "categories",
            []
        ):

            category_counts[
                category
            ] = (
                category_counts.get(
                    category,
                    0
                )
                + 1
            )

        for actor in item.get(
            "actors",
            []
        ):

            actor_counts[
                actor
            ] = (
                actor_counts.get(
                    actor,
                    0
                )
                + 1
            )

        for country in item.get(
            "countries",
            []
        ):

            country_counts[
                country
            ] = (
                country_counts.get(
                    country,
                    0
                )
                + 1
            )

    return {
        "item_count":
            len(
                items
            ),

        "regional_context_count":
            regional_context_count,

        "category_counts":
            dict(
                sorted(
                    category_counts.items()
                )
            ),

        "actor_counts":
            dict(
                sorted(
                    actor_counts.items()
                )
            ),

        "country_counts":
            dict(
                sorted(
                    country_counts.items()
                )
            )
    }


# ---------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------


def main() -> None:

    config = load_config()

    all_items = []

    for source in config.get(
        "rss_sources",
        []
    ):

        all_items.extend(
            fetch_rss_source(
                source
            )
        )

    for feed in config.get(
        "external_json_feeds",
        []
    ):

        all_items.extend(
            fetch_external_json_feed(
                feed
            )
        )

    unique_items = deduplicate(
        all_items
    )

    payload = {
        "project":
            config.get(
                "project",
                "baltic-hybrid-monitor"
            ),

        "region":
            config.get(
                "region",
                "Baltic states and Poland"
            ),

        "generated_at":
            datetime.now(
                timezone.utc
            ).isoformat(),

        "item_count":
            len(
                unique_items
            ),

        "source_summary":
            build_source_summary(
                unique_items
            ),

        "diagnostics":
            build_diagnostics(
                unique_items
            ),

        "method": {
            "description":
                (
                    "Threat Intelligence Engine v1.1 context-aware "
                    "RSS, HTML fallback and external JSON collector "
                    "for Baltic and Polish hybrid-threat monitoring."
                ),

            "classification_version":
                "collector_v1_1_context_aware",

            "countries":
                config.get(
                    "countries",
                    []
                ),

            "categories":
                config.get(
                    "threat_categories",
                    []
                ),

            "features": [
                (
                    "boundary-aware keyword and phrase matching"
                ),
                (
                    "context-aware threat category detection"
                ),
                (
                    "source country separated from detected event country"
                ),
                (
                    "migration-pressure detection excludes generic "
                    "migration references"
                ),
                (
                    "explosives industry references do not automatically "
                    "create sabotage events"
                ),
                (
                    "critical infrastructure requires incident or "
                    "warning context rather than asset mention alone"
                ),
                (
                    "generic cyber references do not automatically "
                    "create cyber incidents"
                ),
                (
                    "institutional actor detection avoids weak EU and "
                    "alliance substring matches"
                ),
                (
                    "context-weighted relevance scoring"
                ),
                (
                    "broad but evidence-based raw collection gate"
                ),
                (
                    "canonical title deduplication"
                ),
                (
                    "strict HTML fallback relevance screening"
                ),
                (
                    "collection diagnostics"
                )
            ]
        },

        "items":
            unique_items
    }

    RAW_OUTPUT.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    DOCS_OUTPUT.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    RAW_OUTPUT.write_text(
        json.dumps(
            payload,
            ensure_ascii=False,
            indent=2
        ),
        encoding="utf-8"
    )

    DOCS_OUTPUT.write_text(
        json.dumps(
            payload,
            ensure_ascii=False,
            indent=2
        ),
        encoding="utf-8"
    )

    print(
        f"Saved "
        f"{len(unique_items)} "
        f"items to "
        f"{RAW_OUTPUT}"
    )

    print(
        f"Saved public copy to "
        f"{DOCS_OUTPUT}"
    )

    print(
        "Collector model: "
        "collector_v1_1_context_aware"
    )

    print(
        "Boundary-aware matching: enabled"
    )

    print(
        "Source-country auto assignment: disabled"
    )

    print(
        "Context-aware category detection: enabled"
    )


if __name__ == "__main__":
    main()
