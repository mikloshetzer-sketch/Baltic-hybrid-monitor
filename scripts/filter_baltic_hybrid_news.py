import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, List, Set


ROOT = Path(__file__).resolve().parents[1]

RAW_INPUT = ROOT / "data" / "baltic_hybrid_raw_news.json"
FILTERED_OUTPUT = ROOT / "data" / "baltic_hybrid_filtered_news.json"
DOCS_FILTERED_OUTPUT = ROOT / "docs" / "data" / "baltic_hybrid_filtered_news.json"


# ---------------------------------------------------------------------
# THREAT RELEVANCE MODEL
#
# The filter should answer one question:
#
# Is this item relevant to Baltic / Polish hybrid-threat monitoring?
#
# Being about Estonia, Latvia, Lithuania, Poland, NATO, the EU or
# cybersecurity is NOT sufficient by itself.
#
# The item must also contain a meaningful threat, hostile-actor,
# operational, warning or information-operation signal.
# ---------------------------------------------------------------------


BALTIC_COUNTRIES = {
    "Estonia",
    "Latvia",
    "Lithuania",
    "Poland"
}


HOSTILE_ACTORS = {
    "Russia",
    "Belarus",
    "GRU",
    "FSB",
    "Sandworm"
}


INSTITUTIONAL_ACTORS = {
    "NATO",
    "EU"
}


STRONG_THREAT_CATEGORIES = {
    "sabotage",
    "drone_incident",
    "gps_interference",
    "espionage",
    "military_provocation",
    "border_pressure",
    "migration_pressure",
    "disinformation"
}


CONDITIONAL_THREAT_CATEGORIES = {
    "cyber",
    "critical_infrastructure"
}


STRATEGIC_LOCATIONS = {
    "Kaliningrad",
    "Suwalki Gap",
    "Belarus Border",
    "Poland-Belarus Border",
    "Narva",
    "Baltic Sea",
    "Klaipeda",
    "Gdansk"
}


REGIONAL_TERMS = [
    "estonia",
    "estonian",
    "latvia",
    "latvian",
    "lithuania",
    "lithuanian",
    "poland",
    "polish",
    "baltic",
    "baltic states",
    "baltics",
    "baltic sea",
    "eastern flank",
    "suwalki",
    "suwałki",
    "kaliningrad",
    "narva",
    "poland-belarus border",
    "polish-belarusian border"
]


HOSTILE_ACTOR_TERMS = [
    "russia",
    "russian",
    "kremlin",
    "moscow",
    "putin",
    "belarus",
    "belarusian",
    "lukashenko",
    "gru",
    "fsb",
    "sandworm"
]


HYBRID_THREAT_TERMS = [
    "hybrid warfare",
    "hybrid war",
    "hybrid attack",
    "hybrid attacks",
    "hybrid threat",
    "hybrid threats",
    "hybrid operation",
    "hybrid operations",
    "hybrid activity",
    "hybrid activities",
    "sabotage",
    "sabotage attack",
    "sabotage operation",
    "espionage",
    "spy",
    "spying",
    "intelligence operation",
    "covert operation",
    "influence operation",
    "information operation",
    "disinformation campaign",
    "propaganda campaign",
    "foreign information manipulation"
]


CYBER_INCIDENT_TERMS = [
    "cyberattack",
    "cyber attack",
    "cyber attacks",
    "ddos attack",
    "ddos attacks",
    "malware attack",
    "ransomware attack",
    "wiper attack",
    "systems breached",
    "network breached",
    "data breach",
    "cyber espionage",
    "cyber sabotage",
    "state-sponsored cyber",
    "state sponsored cyber"
]


ELECTRONIC_WARFARE_TERMS = [
    "gps jamming",
    "gnss jamming",
    "gps interference",
    "gnss interference",
    "navigation interference",
    "gps spoofing",
    "gnss spoofing",
    "electronic warfare",
    "signal interference"
]


DRONE_AIRSPACE_TERMS = [
    "drone incursion",
    "drone intrusion",
    "drone entered",
    "drone crossed",
    "drone shot down",
    "drone crash",
    "drone crashed",
    "unauthorized drone",
    "unidentified drone",
    "airspace violation",
    "airspace incursion",
    "violated airspace",
    "entered airspace",
    "fighter jets scrambled",
    "scrambled fighter jets"
]


INFRASTRUCTURE_INCIDENT_TERMS = [
    "undersea cable damaged",
    "subsea cable damaged",
    "cable damaged",
    "cable cut",
    "cable sabotage",
    "pipeline damaged",
    "pipeline sabotage",
    "power grid attack",
    "energy infrastructure attack",
    "critical infrastructure attack",
    "infrastructure sabotage"
]


BORDER_PRESSURE_TERMS = [
    "border breach",
    "illegal border crossing",
    "border pressure",
    "migration pressure",
    "migrant pressure",
    "instrumentalised migration",
    "instrumentalized migration",
    "weaponised migration",
    "weaponized migration",
    "border provocation",
    "border incident"
]


MILITARY_ESCALATION_TERMS = [
    "military provocation",
    "military buildup",
    "military build-up",
    "troop movement",
    "force movement",
    "military exercise",
    "military drills",
    "air policing",
    "fighter jets",
    "missile entered",
    "missile crossed",
    "nato eastern flank",
    "nato flank",
    "suwalki gap"
]


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
    "could sabotage",
    "could stage",
    "could strike",
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
# GENERAL NOISE
#
# These items are not threat-monitoring material unless a very strong
# hostile / operational signal is also present.
# ---------------------------------------------------------------------


NOISE_TERMS = [
    "culture",
    "concert",
    "music",
    "chopin",
    "violin",
    "orchestra",
    "sports",
    "football",
    "basketball",
    "mountaineering",
    "climber",
    "climbers",
    "weather",
    "heavy rain",
    "storm damage",
    "water leak",
    "hospital",
    "seat selection",
    "airbaltic seats",
    "six-year-old",
    "labour exploitation",
    "labor exploitation",
    "election candidate pool",
    "presidential elections",
    "news in simple latvian",
    "population research",
    "bar open again",
    "tourism",
    "recipe",
    "fashion",
    "festival",
    "parade",
    "online streaming",
    "streaming services",
    "roadworks",
    "traffic delays",
    "oil shale refinery",
    "shale oil plant",
    "sports club",
    "cinema",
    "theatre",
    "theater",
    "restaurant",
    "food festival"
]


GENERAL_CYBER_NOISE_TERMS = [
    "cybersecurity challenge",
    "international cybersecurity challenge",
    "cybersecurity competition",
    "cyber resilience act",
    "certification",
    "managed security services",
    "cybersecurity reserve",
    "cybersecurity investments",
    "cybersecurity investment",
    "cyber hygiene",
    "skills shortage",
    "cyber skills",
    "training course",
    "training programme",
    "training program",
    "conference",
    "webinar",
    "workshop",
    "vulnerability disclosure",
    "software vulnerability",
    "software vulnerabilities",
    "security update",
    "patch available"
]


CRIME_NOISE_TERMS = [
    "cigarette smuggling",
    "drug smuggling",
    "tax fraud",
    "financial fraud",
    "money laundering",
    "court case",
    "goes to court",
    "organized crime",
    "organised crime"
]


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
# TEXT HELPERS
# ---------------------------------------------------------------------


def normalize(
    text: str
) -> str:

    text = str(
        text
    ).lower()

    text = re.sub(
        r"https?://\S+",
        " ",
        text
    )

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
        for term
        in terms
    )


def build_text(
    item: Dict[str, Any]
) -> str:

    return " ".join([
        str(
            item.get(
                "title",
                ""
            )
        ),
        str(
            item.get(
                "summary",
                ""
            )
        ),
        str(
            item.get(
                "url",
                ""
            )
        )
    ])


# ---------------------------------------------------------------------
# CONTEXT HELPERS
# ---------------------------------------------------------------------


def get_actor_set(
    item: Dict[str, Any]
) -> Set[str]:

    return {
        str(
            actor
        )
        for actor
        in item.get(
            "actors",
            []
        )
    }


def get_category_set(
    item: Dict[str, Any]
) -> Set[str]:

    return {
        str(
            category
        )
        for category
        in item.get(
            "categories",
            []
        )
    }


def get_country_set(
    item: Dict[str, Any]
) -> Set[str]:

    return {
        str(
            country
        )
        for country
        in item.get(
            "countries",
            []
        )
    }


def get_location_set(
    item: Dict[str, Any]
) -> Set[str]:

    return {
        str(
            location
        )
        for location
        in item.get(
            "locations",
            []
        )
    }


def has_hostile_actor(
    item: Dict[str, Any]
) -> bool:

    actors = get_actor_set(
        item
    )

    if actors & HOSTILE_ACTORS:
        return True

    text = build_text(
        item
    )

    return contains_any(
        text,
        HOSTILE_ACTOR_TERMS
    )


def has_baltic_context(
    item: Dict[str, Any]
) -> bool:

    countries = get_country_set(
        item
    )

    if countries & BALTIC_COUNTRIES:
        return True

    locations = get_location_set(
        item
    )

    if locations & STRATEGIC_LOCATIONS:
        return True

    return contains_any(
        build_text(
            item
        ),
        REGIONAL_TERMS
    )


def has_nato_context(
    item: Dict[str, Any]
) -> bool:

    actors = get_actor_set(
        item
    )

    if "NATO" in actors:
        return True

    return contains_term(
        build_text(
            item
        ),
        "nato"
    )


def has_operational_threat_signal(
    item: Dict[str, Any]
) -> bool:

    text = build_text(
        item
    )

    return any([
        contains_any(
            text,
            HYBRID_THREAT_TERMS
        ),
        contains_any(
            text,
            CYBER_INCIDENT_TERMS
        ),
        contains_any(
            text,
            ELECTRONIC_WARFARE_TERMS
        ),
        contains_any(
            text,
            DRONE_AIRSPACE_TERMS
        ),
        contains_any(
            text,
            INFRASTRUCTURE_INCIDENT_TERMS
        ),
        contains_any(
            text,
            BORDER_PRESSURE_TERMS
        ),
        contains_any(
            text,
            MILITARY_ESCALATION_TERMS
        )
    ])


def has_warning_signal(
    item: Dict[str, Any]
) -> bool:

    return contains_any(
        build_text(
            item
        ),
        WARNING_TERMS
    )


def has_strong_category(
    item: Dict[str, Any]
) -> bool:

    categories = get_category_set(
        item
    )

    return bool(
        categories
        & STRONG_THREAT_CATEGORIES
    )


def has_conditional_category(
    item: Dict[str, Any]
) -> bool:

    categories = get_category_set(
        item
    )

    return bool(
        categories
        & CONDITIONAL_THREAT_CATEGORIES
    )


# ---------------------------------------------------------------------
# NOISE DETECTION
# ---------------------------------------------------------------------


def is_general_noise(
    item: Dict[str, Any]
) -> bool:

    text = build_text(
        item
    )

    return contains_any(
        text,
        NOISE_TERMS
    )


def is_general_cyber_noise(
    item: Dict[str, Any]
) -> bool:

    text = build_text(
        item
    )

    return contains_any(
        text,
        GENERAL_CYBER_NOISE_TERMS
    )


def is_general_crime_noise(
    item: Dict[str, Any]
) -> bool:

    text = build_text(
        item
    )

    return contains_any(
        text,
        CRIME_NOISE_TERMS
    )


# ---------------------------------------------------------------------
# RELEVANCE DECISION
# ---------------------------------------------------------------------


def should_keep(
    item: Dict[str, Any]
) -> bool:

    hostile_actor = has_hostile_actor(
        item
    )

    baltic_context = has_baltic_context(
        item
    )

    nato_context = has_nato_context(
        item
    )

    operational_signal = (
        has_operational_threat_signal(
            item
        )
    )

    warning_signal = (
        has_warning_signal(
            item
        )
    )

    strong_category = (
        has_strong_category(
            item
        )
    )

    conditional_category = (
        has_conditional_category(
            item
        )
    )

    general_noise = (
        is_general_noise(
            item
        )
    )

    cyber_noise = (
        is_general_cyber_noise(
            item
        )
    )

    crime_noise = (
        is_general_crime_noise(
            item
        )
    )

    # -------------------------------------------------------------
    # 1. VERY STRONG HOSTILE / OPERATIONAL SIGNAL
    #
    # Explicit hostile actor plus a genuine threat / warning signal.
    # This can remain even when the story is region-wide rather than
    # tied to one Baltic country.
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
            baltic_context
            or nato_context
            or strong_category
        )
    ):

        return True

    # -------------------------------------------------------------
    # 2. BALTIC / POLISH CONCRETE THREAT EVENT
    # -------------------------------------------------------------

    if (
        baltic_context
        and operational_signal
    ):

        return True

    # -------------------------------------------------------------
    # 3. BALTIC / POLISH STRONG THREAT CATEGORY
    #
    # Category alone is not enough unless regional context exists.
    # -------------------------------------------------------------

    if (
        baltic_context
        and strong_category
    ):

        if (
            general_noise
            or crime_noise
        ):

            return False

        return True

    # -------------------------------------------------------------
    # 4. NATO + HOSTILE ACTOR + THREAT CONTEXT
    # -------------------------------------------------------------

    if (
        nato_context
        and hostile_actor
        and (
            warning_signal
            or strong_category
            or operational_signal
        )
    ):

        return True

    # -------------------------------------------------------------
    # 5. CYBER / CRITICAL INFRASTRUCTURE
    #
    # These categories are especially noisy.
    #
    # They need additional operational, hostile or Baltic evidence.
    # -------------------------------------------------------------

    if conditional_category:

        if cyber_noise and not hostile_actor:
            return False

        if general_noise and not hostile_actor:
            return False

        if crime_noise and not hostile_actor:
            return False

        if (
            hostile_actor
            and (
                baltic_context
                or operational_signal
                or warning_signal
            )
        ):

            return True

        if (
            baltic_context
            and operational_signal
        ):

            return True

        return False

    # -------------------------------------------------------------
    # 6. INFORMATION OPERATIONS
    # -------------------------------------------------------------

    categories = get_category_set(
        item
    )

    if "disinformation" in categories:

        if (
            baltic_context
            or hostile_actor
        ):

            return True

    # -------------------------------------------------------------
    # 7. GENERAL NOISE ALWAYS DROPS HERE
    # -------------------------------------------------------------

    if (
        general_noise
        or cyber_noise
        or crime_noise
    ):

        return False

    # -------------------------------------------------------------
    # 8. NO SUFFICIENT THREAT EVIDENCE
    # -------------------------------------------------------------

    return False


# ---------------------------------------------------------------------
# FILTER
# ---------------------------------------------------------------------


def filter_items(
    items: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:

    kept = []

    for item in items:

        if should_keep(
            item
        ):

            kept.append(
                item
            )

    return kept


# ---------------------------------------------------------------------
# SOURCE SUMMARY
# ---------------------------------------------------------------------


def build_source_summary(
    items: List[Dict[str, Any]]
) -> Dict[str, Any]:

    summary = {}

    for item in items:

        name = item.get(
            "source_name",
            "Unknown source"
        )

        if name not in summary:

            summary[
                name
            ] = {
                "source_name":
                    name,

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
            name
        ][
            "item_count"
        ] += 1

        method = item.get(
            "collection_method",
            "rss"
        )

        if method == "html_fallback":

            summary[
                name
            ][
                "html_fallback_count"
            ] += 1

        elif method == "external_json":

            summary[
                name
            ][
                "external_json_count"
            ] += 1

        else:

            summary[
                name
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
# FILTER DIAGNOSTICS
# ---------------------------------------------------------------------


def build_filter_diagnostics(
    raw_items: List[Dict[str, Any]],
    filtered_items: List[Dict[str, Any]]
) -> Dict[str, Any]:

    raw_count = len(
        raw_items
    )

    kept_count = len(
        filtered_items
    )

    removed_count = (
        raw_count
        - kept_count
    )

    keep_rate = (
        round(
            (
                kept_count
                / raw_count
                * 100
            ),
            2
        )
        if raw_count
        else 0.0
    )

    return {
        "raw_count":
            raw_count,

        "kept_count":
            kept_count,

        "removed_count":
            removed_count,

        "keep_rate_percent":
            keep_rate
    }


# ---------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------


def main() -> None:

    raw = load_json(
        RAW_INPUT
    )

    raw_items = raw.get(
        "items",
        []
    )

    filtered_items = filter_items(
        raw_items
    )

    diagnostics = (
        build_filter_diagnostics(
            raw_items,
            filtered_items
        )
    )

    payload = {
        "project":
            raw.get(
                "project",
                "baltic-hybrid-monitor"
            ),

        "region":
            raw.get(
                "region",
                "Baltic states and Poland"
            ),

        "generated_at":
            datetime.now(
                timezone.utc
            ).isoformat(),

        "input_generated_at":
            raw.get(
                "generated_at"
            ),

        "raw_item_count":
            len(
                raw_items
            ),

        "item_count":
            len(
                filtered_items
            ),

        "removed_count":
            (
                len(
                    raw_items
                )
                - len(
                    filtered_items
                )
            ),

        "filter_diagnostics":
            diagnostics,

        "source_summary":
            build_source_summary(
                filtered_items
            ),

        "method": {
            "description":
                (
                    "Threat Intelligence Engine v1.1 relevance filter "
                    "for Baltic and Polish hybrid-threat monitoring."
                ),

            "classification_version":
                "relevance_filter_v1_1_context_gate",

            "rules": [
                (
                    "do not keep an item merely because it mentions "
                    "the EU, NATO, a Baltic country or a location"
                ),
                (
                    "do not keep generic cybersecurity material "
                    "without hostile, regional or operational evidence"
                ),
                (
                    "require Baltic/Polish context, hostile-actor "
                    "context or NATO-Russia/Belarus threat context"
                ),
                (
                    "retain concrete sabotage, cyberattack, espionage, "
                    "GNSS, drone, border, infrastructure and military "
                    "threat signals"
                ),
                (
                    "retain Russia/Belarus-linked warnings and "
                    "information-operation signals"
                ),
                (
                    "remove culture, sport, lifestyle, weather, "
                    "general crime and domestic-news noise"
                ),
                (
                    "use boundary-aware word and phrase matching "
                    "instead of raw substring matching"
                ),
                (
                    "treat cyber and critical_infrastructure as "
                    "conditional rather than automatically strong "
                    "categories"
                )
            ]
        },

        "items":
            filtered_items
    }

    save_json(
        FILTERED_OUTPUT,
        payload
    )

    save_json(
        DOCS_FILTERED_OUTPUT,
        payload
    )

    print(
        f"Raw items: "
        f"{len(raw_items)}"
    )

    print(
        f"Filtered items: "
        f"{len(filtered_items)}"
    )

    print(
        f"Removed items: "
        f"{len(raw_items) - len(filtered_items)}"
    )

    print(
        f"Keep rate: "
        f"{diagnostics['keep_rate_percent']}%"
    )

    print(
        "Filter model: "
        "Threat Intelligence Engine relevance_filter_v1_1_context_gate"
    )

    print(
        f"Saved: "
        f"{FILTERED_OUTPUT}"
    )

    print(
        f"Saved: "
        f"{DOCS_FILTERED_OUTPUT}"
    )


if __name__ == "__main__":
    main()
    
