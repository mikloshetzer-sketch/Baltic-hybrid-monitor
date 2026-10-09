import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from validate_event_lifecycle import classify, audit_event

class LifecycleTests(unittest.TestCase):
    def make(self, title):
        return classify({'title': title, 'published_at': '2026-10-08T10:00:00Z',
                         'event_subtype': 'incident', 'hybrid_threat_score': 45})

    def test_historical_case(self):
        e = self.make('Prosecutors closed investigation into 2025 drone incident')
        self.assertEqual(e['event_subtype'], 'assessment')
        self.assertEqual(e['hybrid_threat_score'], 0)
        self.assertEqual(e['original_hybrid_threat_score'], 45)

    def test_legal_closure_without_year(self):
        e = self.make('Polish prosecutors close inquiry into Russian airspace violation')
        self.assertEqual(e['event_subtype'], 'assessment')

    def test_diplomatic_reaction(self):
        e = self.make('Poland confronts Russia over Estonia airspace violation')
        self.assertEqual(e['event_subtype'], 'assessment')

    def test_new_attack_not_suppressed(self):
        self.assertEqual(self.make('New drone incident in Latvia')['event_subtype'], 'incident')

    def test_prior_year_only_review(self):
        e = self.make('After 2025 warnings, new sabotage in Latvia')
        self.assertEqual(e['event_subtype'], 'incident')
        self.assertEqual(e['lifecycle_review']['status'], 'needs_review')

    def test_original_untouched(self):
        source = {'title': 'New drone incident in Latvia', 'event_subtype': 'incident'}
        classify(source)
        self.assertNotIn('lifecycle_review', source)

class AuditTests(unittest.TestCase):
    def test_external_scope_flag_without_score_change(self):
        e = audit_event({'title':'Attack debris hits Moldova', 'geographic_scope':'external_context', 'hybrid_threat_score':22})
        self.assertEqual(e['geographic_review']['status'], 'outside_core_area_review')
        self.assertEqual(e['hybrid_threat_score'], 22)
    def test_publication_date_not_event_date(self):
        e = audit_event({'title':'New cyberattack in Latvia', 'published_at':'2026-10-08T00:00:00Z'})
        self.assertIsNone(e['event_date_review']['event_date'])
        self.assertEqual(e['event_date_review']['candidate_dates'], [])
    def test_explicit_date_candidate_not_assumed_true(self):
        e = audit_event({'title':'Incident on 2025-09-10 in Poland'})
        self.assertEqual(e['event_date_review']['candidate_dates'], ['2025-09-10'])
        self.assertIsNone(e['event_date_review']['event_date'])
    def test_mixed_geography_requires_review(self):
        e = audit_event({'title':'Poland and Moldova discuss border incidents', 'geographic_scope':'direct'})
        self.assertEqual(e['geographic_review']['status'], 'mixed_geography_review')

if __name__ == '__main__':
    unittest.main()

