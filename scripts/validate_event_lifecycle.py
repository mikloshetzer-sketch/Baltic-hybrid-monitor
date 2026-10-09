"""Baltic Lifecycle v5: event timing, source corrections, geography and index gate.

Run after scoring and before exact-day snapshot generation.
Keep every event in the dataset. Index exclusion is independent of event counts.
"""
import json
import re
from datetime import datetime, timezone, date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "data/baltic_hybrid_scored_news.json"
MIRROR = ROOT / "docs/data/baltic_hybrid_scored_news.json"

LEGAL_FOLLOWUP = re.compile(
    r"\b(?:prosecutors?|authorities|police|investigators?)\s+(?:have\s+)?(?:close|closed|conclude|concluded|drop|dropped|end|ended)\s+(?:an?\s+|the\s+)?(?:inquiry|investigation|probe|case)\b"
    r"|\b(?:inquiry|investigation|probe|case)\s+(?:has\s+been\s+|was\s+)?(?:closed|concluded|dropped)\b"
    r"|\b(?:investigation|inquiry|probe)\s+into\s+.{0,100}?\s+(?:closed|concluded|completed)\b", re.I)
DIPLOMATIC_REACTION = re.compile(
    r"\b(?:seeks?\s+(?:urgent\s+)?(?:nato\s+)?consultation|"
    r"confronts?\s+\w+\s+over|slams?\s+\w+\s+(?:over|after)|"
    r"condemns?\s+\w+\s+(?:over|after)|"
    r"summons?\s+(?:the\s+)?(?:ambassador|envoy))\b", re.I)
PRIOR_INCIDENT = re.compile(
    r"\b(?:after|over|following|in response to)\b.{0,110}?\b"
    r"(?:airspace violation|incursion|attack|sabotage|drone incident|arson)\b", re.I)
NEW_ACTION = re.compile(r"\b(?:new|fresh|another|second)\s+(?:attack|strike|incursion|violation|sabotage)\b", re.I)
YEAR = re.compile(r"\b20\d{2}\b")
EXPLICIT_DATE = re.compile(r"\b(20\d{2})-(0[1-9]|1[0-2])-([0-2]\d|3[01])\b")
OUTSIDE = re.compile(r"\b(?:moldova|moldovan|romania|romanian|france|french|germany|german|italy|italian|spain|spanish)\b", re.I)
INSIDE = re.compile(r"\b(?:estonia|estonian|latvia|latvian|lithuania|lithuanian|poland|polish|kaliningrad|suwalki|suwałki|baltic sea)\b", re.I)

# Reviewed, source-specific corrections. These are NOT general keyword rules.
# Each correction must have a matching source URL and a documented basis.
SOURCE_CORRECTIONS = {
    "https://news.err.ee/1610161744/possible-cyberattack-halts-estonian-artists-association-fundraiser-auction": {
        "status": "source_correction",
        "reason": "operator_found_no_evidence_of_malicious_activity",
        "source": "https://news.err.ee/1610161744/possible-cyberattack-halts-estonian-artists-association-fundraiser-auction",
        "note": "The updated ERR report quotes the server operator: no evidence of malicious activity. Technical disruption remains a real event; cyber attribution is unsupported.",
    },
    "https://www.lvm.lv/jaunumi/8018-lvm-saskaries-ar-kiberdrosibas-incidentu": {
        "status": "historical_incident",
        "reason": "original_incident_occurred_2026_06_22",
        "event_date": "2026-06-22",
        "source": "https://www.lvm.lv/jaunumi/8018-lvm-saskaries-ar-kiberdrosibas-incidentu",
        "note": "Latvian State Forests incident occurred on June 22, 2026 and was disclosed June 25; a later article is not a new attack.",
    },
}
HISTORICAL_LVM_TITLE = re.compile(r"\bcyberattack on latvian state forests detected\b", re.I)
ERR_AUCTION_TITLE = re.compile(r"\bpossible cyberattack halts estonian artists\b", re.I)

def correction_for(event):
    """Match known cases narrowly; no automatic exclusion of similar headlines."""
    url = str(event.get("url") or "").split("?")[0].rstrip("/")
    if url in SOURCE_CORRECTIONS:
        return SOURCE_CORRECTIONS[url]
    title = str(event.get("title") or "")
    # Historical title has a confirmed official source even if an RSS URL differs.
    if HISTORICAL_LVM_TITLE.search(title):
        return SOURCE_CORRECTIONS["https://www.lvm.lv/jaunumi/8018-lvm-saskaries-ar-kiberdrosibas-incidentu"]
    if ERR_AUCTION_TITLE.search(title):
        return SOURCE_CORRECTIONS["https://news.err.ee/1610161744/possible-cyberattack-halts-estonian-artists-association-fundraiser-auction"]
    return None

def audit_event(event):
    e = dict(event)
    title = str(e.get("title") or "")
    summary = str(e.get("summary") or "")
    candidates = []
    for y, m, d in EXPLICIT_DATE.findall(f"{title} {summary}"):
        try:
            candidates.append(date(int(y), int(m), int(d)).isoformat())
        except ValueError:
            pass
    dates = sorted(set(candidates))
    e["event_date_review"] = {
        "status": "explicit_date_needs_verification" if dates else "unknown",
        "candidate_dates": dates,
        "event_date": None,
        "note": "Article publication time is not proof of the incident date",
        "rule_version": "v5",
    }
    scope = str(e.get("geographic_scope") or "")
    if scope == "external_context":
        status, reason = "outside_core_area_review", "existing_external_context_scope"
    elif OUTSIDE.search(title) and not INSIDE.search(title):
        status, reason = "outside_core_area_review", "external_place_in_title"
    elif OUTSIDE.search(title) and INSIDE.search(title):
        status, reason = "mixed_geography_review", "mixed_place_names_in_title"
    else:
        status, reason = "not_flagged", "no_explicit_external_signal"
    e["geographic_review"] = {
        "status": status, "reason": reason,
        "original_geographic_scope": scope, "rule_version": "v5",
    }
    correction = correction_for(e)
    if correction and correction.get("event_date"):
        e["event_date_review"].update({
            "status": "verified_historical_event",
            "event_date": correction["event_date"],
            "candidate_dates": sorted(set(dates + [correction["event_date"]])),
            "verification_source": correction["source"],
        })
    return e

def classify(event):
    e = dict(event)
    title = str(e.get("title") or "")
    summary = str(e.get("summary") or "")
    text = f"{title} {summary}"
    publication_year = str(e.get("published_at") or "")[:4]
    prior_year = bool(publication_year and any(y < publication_year for y in YEAR.findall(text)))
    legal = bool(LEGAL_FOLLOWUP.search(title))
    diplomatic = bool(DIPLOMATIC_REACTION.search(title) and PRIOR_INCIDENT.search(title))
    historical = bool(prior_year and re.search(r"\b(?:anniversary|commemoration|retrospective|look back)\b", text, re.I))
    conflicting = bool(NEW_ACTION.search(title))
    confirmed = (legal or diplomatic or historical) and not conflicting
    reason = ("legal_followup" if legal else "diplomatic_reaction_to_prior_incident" if diplomatic
              else "historical_retrospective" if historical else
              "date_or_conflicting_signal" if prior_year or conflicting else "insufficient_evidence")
    status = ("historical_follow_up" if confirmed else
              "needs_review" if prior_year or conflicting else "not_determined")
    e["lifecycle_review"] = {
        "status": status, "reason": reason,
        "reviewed_at": datetime.now(timezone.utc).isoformat(),
        "rule_version": "v5",
    }
    if confirmed and e.get("event_subtype") in {"incident", "activity", "indicator"}:
        e.setdefault("original_event_subtype", e["event_subtype"])
        e.setdefault("original_hybrid_threat_score", e.get("hybrid_threat_score", 0))
        e["event_subtype"] = "assessment"
        e["event_type"] = "assessment"
        e["analytical_layer"] = "assessment"
        e["hybrid_threat_score"] = 0
        e["hybrid_threat_level"] = "low"
        if isinstance(e.get("score_breakdown"), dict):
            e["score_breakdown"] = dict(e["score_breakdown"])
            e["score_breakdown"]["event_subtype"] = "assessment"
            e["score_breakdown"]["subtype_weight"] = 0.0
            e["score_breakdown"]["weighted_score"] = 0.0
    return e

def index_eligibility(event):
    title = str(event.get("title") or "")
    countries = set(event.get("countries") or [])
    core = {"Estonia", "Latvia", "Lithuania", "Poland"}
    outside = bool(OUTSIDE.search(title))
    inside = bool(INSIDE.search(title))
    excluded = (event.get("geographic_scope") == "external_context"
                and outside and not inside and not (countries & core))
    correction = correction_for(event)
    if correction:
        return {
            "eligible": False,
            "reason": correction["reason"],
            "rule_version": "v5",
            "verification_source": correction["source"],
        }
    return {
        "eligible": not excluded,
        "reason": "explicit_external_only_incident" if excluded else "included",
        "rule_version": "v5",
    }

def apply_source_review(event):
    """Preserve original scores and classifications; mark verified exclusions."""
    e = dict(event)
    correction = correction_for(e)
    if correction:
        e["source_correction_review"] = {
            "status": correction["status"],
            "reason": correction["reason"],
            "source": correction["source"],
            "note": correction["note"],
            "rule_version": "v5",
        }
        # Do not rewrite the observed event or its original threat score.
        # Eligibility is used only by the index calculation.
    else:
        e["source_correction_review"] = {
            "status": "not_flagged", "rule_version": "v5",
        }
    return e

def rebuild_summaries(data, events):
    import score_baltic_hybrid_news as scorer
    current = scorer.filter_current_window(events, datetime.now(timezone.utc))
    data["overall_summary"] = scorer.build_current_summary(current)
    eligible = [e for e in current if e["index_eligibility"]["eligible"]]
    index_summary = scorer.build_current_summary(eligible)
    for field in ("operational_index", "early_warning_index", "threat_index", "overall_level"):
        data["overall_summary"][field] = index_summary[field]
    data["index_eligibility_audit"] = {
        "rule_version": "v5",
        "current_total": len(current),
        "included_count": len(eligible),
        "excluded_count": len(current) - len(eligible),
        "excluded_events": [
            {"event_id": e.get("event_id"), "title": e.get("title"),
             "score": e.get("hybrid_threat_score"),
             "reason": e["index_eligibility"]["reason"],
             "verification_source": e["index_eligibility"].get("verification_source")}
            for e in current if not e["index_eligibility"]["eligible"]
        ],
        "unfiltered_threat_index": scorer.build_current_summary(current)["threat_index"],
        "filtered_threat_index": index_summary["threat_index"],
    }
    data["country_summary"] = scorer.build_country_summary(current)
    data["category_summary"] = scorer.build_category_summary(current)
    data["actor_summary"] = scorer.build_actor_summary(current)
    data["subtype_summary"] = scorer.build_subtype_summary(current)
    data["scope_summary"] = scorer.build_scope_summary(current)
    data["historical_summary"] = scorer.build_historical_summary(events)
    data["historical_summaries"] = {
        "country_summary": scorer.build_country_summary(events),
        "category_summary": scorer.build_category_summary(events),
        "actor_summary": scorer.build_actor_summary(events),
        "subtype_summary": scorer.build_subtype_summary(events),
        "scope_summary": scorer.build_scope_summary(events),
    }
    data["current_events"] = current
    if isinstance(data.get("current_threat_window"), dict):
        data["current_threat_window"]["event_count"] = len(current)
    return data

def main():
    data = json.loads(SOURCE.read_text(encoding="utf-8"))
    events = data.get("events")
    if not isinstance(events, list):
        raise ValueError("Expected events list in scored data")
    updated = []
    for event in events:
        reviewed = apply_source_review(audit_event(classify(event)))
        reviewed["index_eligibility"] = index_eligibility(reviewed)
        updated.append(reviewed)
    data["events"] = updated
    data["items"] = updated
    rebuild_summaries(data, updated)
    for target in (SOURCE, MIRROR):
        target.parent.mkdir(parents=True, exist_ok=True)
        temp = target.with_suffix(target.suffix + ".tmp")
        temp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        temp.replace(target)
    counts = {k: sum(e["lifecycle_review"]["status"] == k for e in updated)
              for k in ("historical_follow_up", "needs_review", "not_determined")}
    print(f"Lifecycle validation v5: {len(updated)} events; "
          f"{counts['historical_follow_up']} follow-ups; {counts['needs_review']} need review")
    print("Rebuilt current threat index:", data["overall_summary"]["threat_index"])
    print("Geography review flags:", sum(e["geographic_review"]["status"] != "not_flagged" for e in updated))
    print("Index exclusions:", data["index_eligibility_audit"]["excluded_count"])
    print("Verified source corrections:", sum(e["source_correction_review"]["status"] != "not_flagged" for e in updated))

if __name__ == "__main__":
    main()

