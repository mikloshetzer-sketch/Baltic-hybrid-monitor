import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from validate_event_lifecycle import classify

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

if __name__ == '__main__':
    unittest.main()
