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

    def confirmedMerge(self):
        createdAt = '2026-10-15T20:40:05Z'
        self.previous['projects'] = [
            {'full_name': 'old/tool', 'created_at': createdAt},
            {'full_name': 'new/tool', 'node_id': 'N1', 'created_at': createdAt}]
        self.previous['history'] = {'old/tool': {'2026-10-19': 9, '2026-10-20': 10},
                                    'new/tool': {'2026-10-20': 10}}
        self.current['history'] = copy.deepcopy(self.previous['history'])
        self.current['history']['old/tool']['2026-10-20'] = 11
        self.current['projects'] = [{'full_name': 'new/tool', 'history_key': 'old/tool',
            'node_id': 'N1', 'created_at': createdAt, 'history_aliases': ['new/tool'],
            'observation_status': 'fresh', 'stargazers_count': 11, 'delta_1d': 2, 'delta_7d': None}]

    def test_confirmed_same_identity_merge_preserves_both_history_series(self):
        self.confirmedMerge()
        result = validateBatch(self.previous, self.current, self.manifest)
        self.assertTrue(result['allowed'], result['errors'])
        self.assertEqual(self.current['history']['new/tool'], {'2026-10-20': 10})

    def test_history_alias_requires_existing_identity_and_creation_time_proof(self):
        for index, field, value in [(0, 'created_at', '2026-10-16T00:00:00Z'),
                                     (0, 'node_id', 'OTHER'), (1, 'node_id', 'OTHER'),
                                     (1, 'created_at', '2026-10-16T00:00:00Z')]:
            with self.subTest(index=index, field=field):
                self.confirmedMerge()
                self.previous['projects'][index][field] = value
                result = validateBatch(self.previous, self.current, self.manifest)
                self.assertFalse(result['allowed'])
                self.assertIn('invalid_history_alias:new/tool', result['errors'])

    def test_history_aliases_cannot_be_unknown_repeated_or_another_primary_key(self):
        for aliases in [['unknown/tool'], ['new/tool', 'new/tool'], ['old/tool'], 'new/tool', [None]]:
            with self.subTest(aliases=aliases):
                self.confirmedMerge()
                self.current['projects'][0]['history_aliases'] = aliases
                self.assertFalse(validateBatch(self.previous, self.current, self.manifest)['allowed'])

    def test_redundant_history_is_not_a_fresh_writable_series(self):
        self.confirmedMerge()
        self.current['history']['new/tool']['2026-10-20'] = 11
        result = validateBatch(self.previous, self.current, self.manifest)
        self.assertFalse(result['allowed'])
        self.assertIn('history_changed:new/tool:2026-10-20', result['errors'])

    def test_confirmed_alias_remains_valid_in_following_batch(self):
        self.confirmedMerge()
        self.previous = copy.deepcopy(self.current)
        self.current['history']['old/tool']['2026-10-20'] = 12
        self.current['projects'][0].update(stargazers_count=12, delta_1d=3)
        result = validateBatch(self.previous, self.current, self.manifest)
        self.assertTrue(result['allowed'], result['errors'])

    def test_confirmed_target_history_aliases_survive_initial_rename_merge(self):
        self.confirmedMerge()
        self.previous['projects'][1]['history_aliases'] = ['ancestor/tool']
        self.previous['history']['ancestor/tool'] = {'2026-10-19': 8}
        self.current['history']['ancestor/tool'] = {'2026-10-19': 8}
        self.current['projects'][0]['history_aliases'].append('ancestor/tool')
        result = validateBatch(self.previous, self.current, self.manifest)
        self.assertTrue(result['allowed'], result['errors'])


if __name__ == '__main__':
    unittest.main()
