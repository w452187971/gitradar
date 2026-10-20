import copy
import tempfile
import unittest
from pathlib import Path

from gitradar.validation import validateBatch


class BatchValidationTests(unittest.TestCase):
    def setUp(self):
        self.previous = {'history': {'o/a': {'2026-10-19': 10, '2026-10-20': 12}},
                         'projects': [{'full_name': 'o/a', 'history_key': 'o/a'}]}
        self.current = {'batch_id': 'b1', 'schema_version': '4.0',
                        'generated_at': '2026-10-20T15:00:00+00:00',
                        'history': {'o/a': {'2026-10-19': 10, '2026-10-20': 14}},
                        'projects': [{'full_name': 'o/a', 'history_key': 'o/a',
                                      'node_id': 'N1', 'observation_status': 'fresh'}],
                        'recommendations': {'batch_id': 'b1', 'recommendations': []},
                        'evidence': {'batch_id': 'b1', 'projects': {}}, 'usage': {}}
        self.manifest = {'batch_id': 'b1', 'schema_version': '4.0', 'artifacts': {}}

    def test_successful_same_day_observation_preserves_all_old_dates(self):
        self.assertTrue(validateBatch(self.previous, self.current, self.manifest)['allowed'])

    def test_noncurrent_date_cannot_be_rewritten(self):
        self.current['history']['o/a']['2026-10-19'] = 11
        self.assertFalse(validateBatch(self.previous, self.current, self.manifest)['allowed'])

    def test_even_current_date_key_cannot_be_removed(self):
        del self.current['history']['o/a']['2026-10-20']
        self.assertFalse(validateBatch(self.previous, self.current, self.manifest)['allowed'])

    def test_retained_project_cannot_advance_same_day_history(self):
        self.current['projects'][0]['observation_status'] = 'retained'
        self.assertFalse(validateBatch(self.previous, self.current, self.manifest)['allowed'])

    def test_mixed_feed_batch_blocks_publication(self):
        self.current['recommendations']['batch_id'] = 'old'
        self.assertFalse(validateBatch(self.previous, self.current, self.manifest)['allowed'])

    def test_reusing_identity_for_two_histories_is_rejected(self):
        self.current['projects'].append({'full_name': 'o/b', 'history_key': 'o/b', 'node_id': 'N1'})
        self.assertFalse(validateBatch(self.previous, self.current, self.manifest)['allowed'])

    def test_over_budget_including_retries_blocks_publication(self):
        for usage in ({'rest_requests': 101}, {'search_requests': 21}, {'graphql_points': 601}):
            with self.subTest(usage=usage):
                self.current['usage'] = usage
                self.assertFalse(validateBatch(self.previous, self.current, self.manifest)['allowed'])

    def test_manifest_cannot_reference_artifact_outside_build_directory(self):
        self.manifest['artifacts'] = {'../outside.html': '0' * 64}
        self.assertFalse(validateBatch(self.previous, self.current, self.manifest)['allowed'])

    def test_validating_does_not_mutate_snapshots(self):
        baseline = copy.deepcopy(self.previous)
        validateBatch(self.previous, self.current, self.manifest)
        self.assertEqual(self.previous, baseline)

    def test_fresh_star_count_must_match_current_history(self):
        self.current['projects'][0]['stargazers_count'] = 99
        self.assertFalse(validateBatch(self.previous, self.current, self.manifest)['allowed'])

    def test_recorded_delta_must_recompute_from_real_date_endpoints(self):
        self.current['projects'][0]['delta_1d'] = 5
        self.assertFalse(validateBatch(self.previous, self.current, self.manifest)['allowed'])

    def test_candidates_cannot_disappear_during_migration(self):
        self.current['projects'] = []
        self.current['history'] = copy.deepcopy(self.previous['history'])
        self.assertFalse(validateBatch(self.previous, self.current, self.manifest)['allowed'])


if __name__ == '__main__':
    unittest.main()
