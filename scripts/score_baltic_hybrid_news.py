import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Any


ROOT = Path(__file__).resolve().parents[1]

RAW_INPUT = ROOT / "data" / "baltic_hybrid_raw_news.json"
SCORED_OUTPUT = ROOT / "data" / "baltic_hybrid_scored_news.json"
DOCS_OUTPUT = ROOT / "docs" / "data" / "baltic_hybrid_scored_news.json"


COUNTRIES = ["Estonia", "Latvia", "Lithuania", "Poland"]


CATEGORY_WEIGHTS = {
    "sabotage": 8,
    "cyber": 7,
    "critical_infrastructure": 8,
    "military_provocation": 7,
    "drone_incident": 7,
    "gps_interference": 6,
    "espionage": 6,
    "border_pressure": 5,
    "migration_pressure": 4,
    "disinformation": 4
}


ACTOR_WEIGHTS = {
    "Russia": 3,
    "Belarus": 3,
    "GRU": 4,
    "FSB": 4,
    "Sandworm": 4,
    "NATO": 2,
    "EU": 1
}


LOCATION_WEIGHTS = {
    "Kaliningrad": 4,
    "Suwalki Gap": 4,
    "Baltic Sea": 3,
    "Belarus Border": 3,
    "Poland-Belarus Border": 3,
    "Narva": 2,
    "Riga": 1,
    "Tallinn": 1,
    "Vilnius": 1,
    "Klaipeda": 2,
    "Gdansk": 2
}


SOURCE_TYPE_WEIGHTS = {
    "official_context": 2,
    "cyber_official": 3,
    "border_security": 3,
    "regional_media": 2,
    "cyber_media": 2,
    "disinformation": 2,
    "disinformation_osint": 2,
    "military_air": 2,
    "drone_incident": 2,
    "critical_infrastructure": 2,
    "maritime_infrastructure": 2,
    "strategic_hotspot": 2,
    "country_focus": 1,
    "news_search": 0,
    "external_repo": 2
}


ESCALATION_KEYWORDS = {
    "critical": [
        "sabotage",
        "explosion",
        "airspace violation",
        "critical infrastructure",
        "power grid",
        "undersea cable",
        "subsea cable",
        "pipeline",
        "spy",
        "espionage",
        "ransomware",
        "wiper",
        "missile",
        "drone attack",
        "hybrid attack"
    ],
    "high": [
        "cyberattack",
        "cyber attack",
        "ddos",
        "gps jamming",
        "gnss jamming",
        "spoofing",
        "border provocation",
        "military provocation",
        "fighter jet",
        "scramble",
        "intercept",
        "migration pressure",
        "cognitive warfare"
    ],
    "medium": [
        "propaganda",
        "disinformation",
        "influence operation",
        "border pressure",
        "warning",
        "threat",
        "risk",
        "preparedness",
        "exercise"
    ]
}


def load_raw_data() -> Dict[str, Any]:
    if not RAW_INPUT.exists():
        raise FileNotFoundError(
            f"Missing raw input file: {RAW_INPUT}. "
            "Run scripts/fetch_baltic_hybrid_news.py first."
        )

    return json.loads(RAW_INPUT.read_text(encoding="utf-8"))


def text_blob(item: Dict[str, Any]) -> str:
    return f"{item.get('title', '')} {item.get('summary', '')}".lower()


def keyword_score(text: str) -> int:
    score = 0

    for word in ESCALATION_KEYWORDS["critical"]:
        if word in text:
            score += 5

    for word in ESCALATION_KEYWORDS["high"]:
        if word in text:
            score += 3

    for word in ESCALATION_KEYWORDS["medium"]:
        if word in text:
            score += 1

    return score


def category_score(categories: List[str]) -> int:
    return sum(CATEGORY_WEIGHTS.get(category, 0) for category in categories)


def actor_score(actors: List[str]) -> int:
    return sum(ACTOR_WEIGHTS.get(actor, 0) for actor in actors)


def location_score(locations: List[str]) -> int:
    return sum(LOCATION_WEIGHTS.get(location, 0) for location in locations)


def source_score(item: Dict[str, Any]) -> int:
    source_type = item.get("source_type", "news_search")
    base = SOURCE_TYPE_WEIGHTS.get(source_type, 0)

    source_weight = float(item.get("source_weight", 1.0))

    if source_weight >= 1.2:
        base += 2
    elif source_weight >= 1.1:
        base += 1

    return base


def country_spread_bonus(countries: List[str]) -> int:
    if len(countries) >= 3:
        return 3
    if len(countries) == 2:
        return 2
    if len(countries) == 1:
        return 1
    return 0


def category_diversity_bonus(categories: List[str]) -> int:
    if len(categories) >= 3:
        return 3
    if len(categories) == 2:
        return 2
    if len(categories) == 1:
        return 1
    return 0


def strategic_modifier(item: Dict[str, Any]) -> int:
    text = text_blob(item)
    categories = item.get("categories", [])
    actors = item.get("actors", [])
    locations = item.get("locations", [])

    modifier = 0

    if "Russia" in actors and "NATO" in actors:
        modifier += 2

    if "Belarus" in actors and "border_pressure" in categories:
        modifier += 2

    if "Kaliningrad" in locations and "gps_interference" in categories:
        modifier += 3

    if "Suwalki Gap" in locations:
        modifier += 3

    if "Baltic Sea" in locations and "critical_infrastructure" in categories:
        modifier += 3

    if "cyber" in categories and "critical_infrastructure" in categories:
        modifier += 3

    if "drone_incident" in categories and "military_provocation" in categories:
        modifier += 2

    if "full-scale war is not imminent" in text:
        modifier -= 2

    if "no signs of russian attack" in text:
        modifier -= 2

    return modifier


def classify_level(score: int) -> str:
    if score >= 32:
        return "critical"
    if score >= 22:
        return "high"
    if score >= 12:
        return "elevated"
    if score >= 5:
        return "guarded"
    return "low"


def score_item(item: Dict[str, Any]) -> Dict[str, Any]:
    text = text_blob(item)

    categories = item.get("categories", [])
    actors = item.get("actors", [])
    locations = item.get("locations", [])
    countries = item.get("countries", [])

    relevance = float(item.get("relevance_score", 0))

    score = 0
    score += int(round(relevance))
    score += keyword_score(text)
    score += category_score(categories)
    score += actor_score(actors)
    score += location_score(locations)
    score += source_score(item)
    score += country_spread_bonus(countries)
    score += category_diversity_bonus(categories)
    score += strategic_modifier(item)

    if score < 0:
        score = 0

    item["hybrid_threat_score"] = score
    item["hybrid_threat_level"] = classify_level(score)
    item["score_breakdown"] = {
        "relevance": int(round(relevance)),
        "keywords": keyword_score(text),
        "categories": category_score(categories),
        "actors": actor_score(actors),
        "locations": location_score(locations),
        "source": source_score(item),
        "country_spread": country_spread_bonus(countries),
        "category_diversity": category_diversity_bonus(categories),
        "strategic_modifier": strategic_modifier(item)
    }

    return item


def build_country_summary(items: List[Dict[str, Any]]) -> Dict[str, Any]:
    summary = {
        country: {
            "country": country,
            "incident_count": 0,
            "score_total": 0,
            "average_score": 0,
            "highest_score": 0,
            "level": "low",
            "categories": {},
            "actors": {},
            "locations": {}
        }
        for country in COUNTRIES
    }

    for item in items:
        score = int(item.get("hybrid_threat_score", 0))

        for country in item.get("countries", []):
            if country not in summary:
                continue

            summary[country]["incident_count"] += 1
            summary[country]["score_total"] += score
            summary[country]["highest_score"] = max(
                summary[country]["highest_score"],
                score
            )

            for category in item.get("categories", []):
                summary[country]["categories"][category] = (
                    summary[country]["categories"].get(category, 0) + 1
                )

            for actor in item.get("actors", []):
                summary[country]["actors"][actor] = (
                    summary[country]["actors"].get(actor, 0) + 1
                )

            for location in item.get("locations", []):
                summary[country]["locations"][location] = (
                    summary[country]["locations"].get(location, 0) + 1
                )

    for country, data in summary.items():
        if data["incident_count"] > 0:
            data["average_score"] = round(
                data["score_total"] / data["incident_count"],
                2
            )

        data["level"] = classify_level(int(data["average_score"]))

    return summary


def build_category_summary(items: List[Dict[str, Any]]) -> Dict[str, Any]:
    summary = {}

    for item in items:
        score = int(item.get("hybrid_threat_score", 0))

        for category in item.get("categories", []):
            if category not in summary:
                summary[category] = {
                    "category": category,
                    "incident_count": 0,
                    "score_total": 0,
                    "average_score": 0,
                    "highest_score": 0
                }

            summary[category]["incident_count"] += 1
            summary[category]["score_total"] += score
            summary[category]["highest_score"] = max(
                summary[category]["highest_score"],
                score
            )

    for category, data in summary.items():
        if data["incident_count"] > 0:
            data["average_score"] = round(
                data["score_total"] / data["incident_count"],
                2
            )

    return summary


def build_actor_summary(items: List[Dict[str, Any]]) -> Dict[str, Any]:
    summary = {}

    for item in items:
        score = int(item.get("hybrid_threat_score", 0))

        for actor in item.get("actors", []):
            if actor not in summary:
                summary[actor] = {
                    "actor": actor,
                    "incident_count": 0,
                    "score_total": 0,
                    "average_score": 0,
                    "highest_score": 0
                }

            summary[actor]["incident_count"] += 1
            summary[actor]["score_total"] += score
            summary[actor]["highest_score"] = max(
                summary[actor]["highest_score"],
                score
            )

    for actor, data in summary.items():
        if data["incident_count"] > 0:
            data["average_score"] = round(
                data["score_total"] / data["incident_count"],
                2
            )

    return summary


def build_location_summary(items: List[Dict[str, Any]]) -> Dict[str, Any]:
    summary = {}

    for item in items:
        score = int(item.get("hybrid_threat_score", 0))

        for location in item.get("locations", []):
            if location not in summary:
                summary[location] = {
                    "location": location,
                    "incident_count": 0,
                    "score_total": 0,
                    "average_score": 0,
                    "highest_score": 0
                }

            summary[location]["incident_count"] += 1
            summary[location]["score_total"] += score
            summary[location]["highest_score"] = max(
                summary[location]["highest_score"],
                score
            )

    for location, data in summary.items():
        if data["incident_count"] > 0:
            data["average_score"] = round(
                data["score_total"] / data["incident_count"],
                2
            )

    return summary


def build_overall_summary(items: List[Dict[str, Any]]) -> Dict[str, Any]:
    if not items:
        return {
            "incident_count": 0,
            "score_total": 0,
            "average_score": 0,
            "highest_score": 0,
            "overall_level": "low"
        }

    score_total = sum(int(item.get("hybrid_threat_score", 0)) for item in items)
    highest_score = max(int(item.get("hybrid_threat_score", 0)) for item in items)
    average_score = round(score_total / len(items), 2)

    return {
        "incident_count": len(items),
        "score_total": score_total,
        "average_score": average_score,
        "highest_score": highest_score,
        "overall_level": classify_level(int(average_score))
    }


def main() -> None:
    raw_data = load_raw_data()
    items = raw_data.get("items", [])

    scored_items = [score_item(item) for item in items]
    scored_items = sorted(
        scored_items,
        key=lambda x: x.get("hybrid_threat_score", 0),
        reverse=True
    )

    payload = {
        "project": raw_data.get("project", "baltic-hybrid-monitor"),
        "region": raw_data.get("region", "Baltic states and Poland"),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "input_generated_at": raw_data.get("generated_at"),
        "method": {
            "description": "Rule-based Baltic hybrid threat scoring model with actor, location, category and source-type modifiers.",
            "score_components": [
                "raw relevance score",
                "hybrid escalation keywords",
                "threat category weights",
                "actor weights",
                "strategic location weights",
                "source-type weights",
                "country spread bonus",
                "category diversity bonus",
                "strategic modifiers"
            ],
            "levels": {
                "low": "0-4",
                "guarded": "5-11",
                "elevated": "12-21",
                "high": "22-31",
                "critical": "32+"
            }
        },
        "overall_summary": build_overall_summary(scored_items),
        "country_summary": build_country_summary(scored_items),
        "category_summary": build_category_summary(scored_items),
        "actor_summary": build_actor_summary(scored_items),
        "location_summary": build_location_summary(scored_items),
        "items": scored_items
    }

    SCORED_OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    DOCS_OUTPUT.parent.mkdir(parents=True, exist_ok=True)

    SCORED_OUTPUT.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )

    DOCS_OUTPUT.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )

    print(f"Saved scored data to {SCORED_OUTPUT}")
    print(f"Saved public scored data to {DOCS_OUTPUT}")
    print(f"Items scored: {len(scored_items)}")


if __name__ == "__main__":
    main()
