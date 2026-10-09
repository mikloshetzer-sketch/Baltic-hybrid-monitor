"""Baltic lifecycle gate v2. Run after scoring and before snapshot.

Conservative: explicit legal closure and diplomatic reaction to prior incident
become assessments. All other doubtful cases are flagged, not suppressed.
Rebuilds scored-data summaries using the existing scoring engine helpers.
"""
import json
import re
from datetime import datetime, timezone
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
        'rule_version': 'v2',
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


def rebuild_summaries(data, events):
    # Import existing engine to avoid creating a second, inconsistent index formula.
    import score_baltic_hybrid_news as scorer
    current = scorer.filter_current_window(events, datetime.now(timezone.utc))
    data['overall_summary'] = scorer.build_current_summary(current)
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
    updated = [classify(e) for e in events]
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
    print(f'Lifecycle validation v2: {len(updated)} events; '
          f"{counts['historical_follow_up']} follow-ups; {counts['needs_review']} need review")
    print(f"Rebuilt current threat index: {data['overall_summary']['threat_index']}")


if __name__ == '__main__':
    main()

