"""Baltic lifecycle gate v4. Run after scoring and before snapshot.

Conservative: explicit legal closure and diplomatic reaction to prior incident
become assessments. All other doubtful cases are flagged, not suppressed.
Rebuilds scored-data summaries using the existing scoring engine helpers.
"""
import json
import re
from datetime import datetime, timezone, date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'data/baltic_hybrid_scored_news.json'
MIRROR = ROOT / 'docs/data/baltic_hybrid_scored_news.json'

# The legal action is current news, but it is not a fresh physical attack.
LEGAL_FOLLOWUP = re.compile(
    r'\b(?:prosecutors?|authorities|police|investigators?)\s+(?:have\s+)?(?:close|closed|conclude|concluded|drop|dropped|end|ended)\s+(?:an?\s+|the\s+)?(?:inquiry|investigation|probe|case)\b'
    r'|\b(?:inquiry|investigation|probe|case)\s+(?:has\s+been\s+|was\s+)?(?:closed|concluded|dropped)\b'
    r'|\b(?:investigation|inquiry|probe)\s+into\s+.{0,100}?\s+(?:closed|concluded|completed)\b',
    re.I,
)
DIPLOMATIC_REACTION = re.compile(
    r'\b(?:seeks?\s+(?:urgent\s+)?(?:nato\s+)?consultation|'
    r'confronts?\s+\w+\s+over|slams?\s+\w+\s+(?:over|after)|'
    r'condemns?\s+\w+\s+(?:over|after)|'
    r'summons?\s+(?:the\s+)?(?:ambassador|envoy))\b', re.I,
)
PRIOR_INCIDENT = re.compile(
    r'\b(?:after|over|following|in response to)\b.{0,110}?\b'
    r'(?:airspace violation|incursion|attack|sabotage|drone incident|arson)\b', re.I,
)
NEW_ACTION = re.compile(r'\b(?:new|fresh|another|second)\s+(?:attack|strike|incursion|violation|sabotage)\b', re.I)
YEAR = re.compile(r'\b20\d{2}\b')



# Audits are advisory: never infer incident dates from article publication dates.
# Geographic_scope comes from the scoring engine and is kept unchanged.
EXPLICIT_DATE = re.compile(r'\b(20\d{2})-(0[1-9]|1[0-2])-([0-2]\d|3[01])\b')
OUTSIDE = re.compile(r'\b(?:moldova|moldovan|romania|romanian|france|french|germany|german|italy|italian|spain|spanish)\b', re.I)
INSIDE = re.compile(r'\b(?:estonia|estonian|latvia|latvian|lithuania|lithuanian|poland|polish|kaliningrad|suwalki|suwałki|baltic sea)\b', re.I)

def audit_event(event):
    e = dict(event)
    title = str(e.get('title') or '')
    summary = str(e.get('summary') or '')
    # Do not treat the publication date as the actual incident date.
    candidates = []
    for y, m, d in EXPLICIT_DATE.findall(f'{title} {summary}'):
        try:
            candidates.append(date(int(y), int(m), int(d)).isoformat())
        except ValueError:
            continue
    dates = sorted(set(candidates))
    e['event_date_review'] = {
        'status': 'explicit_date_needs_verification' if dates else 'unknown',
        'candidate_dates': dates,
        'event_date': None,
        'note': 'Article publication time is not proof of the incident date',
        'rule_version': 'v3',
    }
    scope = str(e.get('geographic_scope') or '')
    # Mixed-location articles are not automatically treated as out-of-area.
    if scope == 'external_context':
        status = 'outside_core_area_review'
        reason = 'existing_external_context_scope'
    elif OUTSIDE.search(title) and not INSIDE.search(title):
        status = 'outside_core_area_review'
        reason = 'external_place_in_title'
    elif OUTSIDE.search(title) and INSIDE.search(title):
        status = 'mixed_geography_review'
        reason = 'mixed_place_names_in_title'
    else:
        status = 'not_flagged'
        reason = 'no_explicit_external_signal'
    e['geographic_review'] = {
        'status': status, 'reason': reason,
        'original_geographic_scope': scope, 'rule_version': 'v3',
    }
    return e

def classify(event):
    e = dict(event)
    title = str(e.get('title') or '')
    summary = str(e.get('summary') or '')
    text = f'{title} {summary}'
    publication_year = str(e.get('published_at') or '')[:4]
    prior_year = bool(publication_year and any(y < publication_year for y in YEAR.findall(text)))
    legal = bool(LEGAL_FOLLOWUP.search(title))
    diplomatic = bool(DIPLOMATIC_REACTION.search(title) and PRIOR_INCIDENT.search(title))
    explicit_historical = bool(prior_year and re.search(r'\b(?:anniversary|commemoration|retrospective|look back)\b', text, re.I))
    # New simultaneous action must be reviewed, not automatically suppressed.
    conflicting = bool(NEW_ACTION.search(title))
    confirmed = (legal or diplomatic or explicit_historical) and not conflicting
    reason = ('legal_followup' if legal else 'diplomatic_reaction_to_prior_incident' if diplomatic
              else 'historical_retrospective' if explicit_historical else
              'date_or_conflicting_signal' if prior_year or conflicting else 'insufficient_evidence')
    status = ('historical_follow_up' if confirmed else
              'needs_review' if prior_year or conflicting else 'not_determined')
    e['lifecycle_review'] = {
        'status': status, 'reason': reason,
        'reviewed_at': datetime.now(timezone.utc).isoformat(),
        'rule_version': 'v3',
    }
    if confirmed and e.get('event_subtype') in {'incident', 'activity', 'indicator'}:
        e.setdefault('original_event_subtype', e['event_subtype'])
        e.setdefault('original_hybrid_threat_score', e.get('hybrid_threat_score', 0))
        e['event_subtype'] = 'assessment'
        e['event_type'] = 'assessment'
        e['analytical_layer'] = 'assessment'
        e['hybrid_threat_score'] = 0
        e['hybrid_threat_level'] = 'low'
        if isinstance(e.get('score_breakdown'), dict):
            e['score_breakdown'] = dict(e['score_breakdown'])
            e['score_breakdown']['event_subtype'] = 'assessment'
            e['score_breakdown']['subtype_weight'] = 0.0
            e['score_breakdown']['weighted_score'] = 0.0
    return e


def index_eligibility(event):
    """Conservative geographic gate: explicit external-only incident, no core link.

    Advisory geographic_review alone is insufficient for exclusion. A record
    may be externally scoped but still directly relevant to Baltic security.
    """
    title = str(event.get('title') or '')
    core_countries = {'Estonia', 'Latvia', 'Lithuania', 'Poland'}
    countries = set(event.get('countries') or [])
    outside = bool(OUTSIDE.search(title))
    inside = bool(INSIDE.search(title))
    excluded = (event.get('geographic_scope') == 'external_context'
                and outside and not inside and not (countries & core_countries))
    return {
        'eligible': not excluded,
        'reason': 'explicit_external_only_incident' if excluded else 'included',
        'rule_version': 'v4',
    }


def rebuild_summaries(data, events):
    # Import existing engine to avoid creating a second, inconsistent index formula.
    import score_baltic_hybrid_news as scorer
    current = scorer.filter_current_window(events, datetime.now(timezone.utc))
    data['overall_summary'] = scorer.build_current_summary(current)
    eligible = [e for e in current if e['index_eligibility']['eligible']]
    index_summary = scorer.build_current_summary(eligible)
    # Keep all current news and category/country counts. Change only indices.
    for field in ('operational_index', 'early_warning_index', 'threat_index', 'overall_level'):
        data['overall_summary'][field] = index_summary[field]
    data['index_eligibility_audit'] = {
        'rule_version': 'v4',
        'current_total': len(current),
        'included_count': len(eligible),
        'excluded_count': len(current) - len(eligible),
        'excluded_events': [
            {'event_id': e.get('event_id'), 'title': e.get('title'),
             'score': e.get('hybrid_threat_score'),
             'reason': e['index_eligibility']['reason']}
            for e in current if not e['index_eligibility']['eligible']
        ],
        'unfiltered_threat_index': scorer.build_current_summary(current)['threat_index'],
        'filtered_threat_index': index_summary['threat_index'],
    }
    data['country_summary'] = scorer.build_country_summary(current)
    data['category_summary'] = scorer.build_category_summary(current)
    data['actor_summary'] = scorer.build_actor_summary(current)
    data['subtype_summary'] = scorer.build_subtype_summary(current)
    data['scope_summary'] = scorer.build_scope_summary(current)
    data['historical_summary'] = scorer.build_historical_summary(events)
    data['historical_summaries'] = {
        'country_summary': scorer.build_country_summary(events),
        'category_summary': scorer.build_category_summary(events),
        'actor_summary': scorer.build_actor_summary(events),
        'subtype_summary': scorer.build_subtype_summary(events),
        'scope_summary': scorer.build_scope_summary(events),
    }
    data['current_events'] = current
    if isinstance(data.get('current_threat_window'), dict):
        data['current_threat_window']['event_count'] = len(current)
    return data


def main():
    data = json.loads(SOURCE.read_text(encoding='utf-8'))
    events = data.get('events')
    if not isinstance(events, list):
        raise ValueError('Expected events list in scored data')
    updated = []
    for event in events:
        reviewed = audit_event(classify(event))
        reviewed['index_eligibility'] = index_eligibility(reviewed)
        updated.append(reviewed)
    data['events'] = updated
    data['items'] = updated  # Existing output aliases must agree.
    rebuild_summaries(data, updated)
    for target in (SOURCE, MIRROR):
        target.parent.mkdir(parents=True, exist_ok=True)
        temp = target.with_suffix(target.suffix + '.tmp')
        temp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
        temp.replace(target)
    counts = {k: sum(e['lifecycle_review']['status'] == k for e in updated)
              for k in ('historical_follow_up', 'needs_review', 'not_determined')}
    print(f'Lifecycle validation v4: {len(updated)} events; '
          f"{counts['historical_follow_up']} follow-ups; {counts['needs_review']} need review")
    print(f"Rebuilt current threat index: {data['overall_summary']['threat_index']}")
    print('Geography review flags:', sum(e['geographic_review']['status'] != 'not_flagged' for e in updated))
    print('Index exclusions:', data['index_eligibility_audit']['excluded_count'])
    print('Explicit date candidates:', sum(bool(e['event_date_review']['candidate_dates']) for e in updated))


if __name__ == '__main__':
    main()
