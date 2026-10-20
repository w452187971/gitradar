import copy
import unittest

from gitradar.observations import applyObservations, legacyProjectView


CREATED = '2025-01-01T00:00:00Z'
DATE = '2026-10-20'


def snapshot(identity='R1'):
    return {'projects': [{'full_name': 'a/old', 'node_id': identity, 'history_key': 'a/old',
            'created_at': CREATED, 'stargazers_count': 100, 'summary_zh': '旧内容'}],
            'history': {'a/old': {'2026-10-19': 100, '2026-10-13': 105}}}


def observation(**changes):
    value = {'full_name': 'a/old', 'node_id': 'R1', 'created_at': CREATED,
             'observed_at': DATE+'T12:00:00Z', 'stargazers_count': 95, 'status': 'success'}
    value.update(changes)
    return value


class ObservationTests(unittest.TestCase):
    def test_rename_retains_history_and_saved_aliases(self):
        original = snapshot()
        before = copy.deepcopy(original)
        result = applyObservations(original, [observation(full_name='b/new')], DATE)
        project = result['projects'][0]
        self.assertEqual(project['full_name'], 'b/new')
        self.assertEqual(project['history_key'], 'a/old')
        self.assertEqual(result['history']['a/old'][DATE], 95)
        self.assertEqual(result['saved_aliases']['a/old'], 'b/new')
        self.assertEqual(original, before)
        self.assertEqual(project['delta_1d'], -5)
        self.assertEqual(project['delta_7d'], -10)
        self.assertEqual(legacyProjectView(project)['summary_zh'], '旧内容')

    def test_legacy_created_at_is_verified_before_binding_node(self):
        old = snapshot()
        old['projects'][0].pop('node_id')
        result = applyObservations(old, [observation(created_at='2026-01-01T00:00:00Z')], DATE)
        self.assertNotIn(DATE, result['history']['a/old'])
        self.assertEqual(result['projects'][0]['observation_status'], 'identity_conflict')
        valid = applyObservations(old, [observation()], DATE)
        self.assertEqual(valid['projects'][0]['node_id'], 'R1')

    def test_same_name_recreated_is_isolated(self):
        result = applyObservations(snapshot(), [observation(node_id='R2')], DATE)
        self.assertNotIn(DATE, result['history']['a/old'])
        self.assertEqual(result['projects'][0]['node_id'], 'R1')
        self.assertEqual(result['projects'][0]['observation_status'], 'identity_conflict')
        self.assertIsNone(result['projects'][0]['delta_1d'])

    def test_partial_failure_keeps_old_values_and_missing_dates(self):
        original = snapshot()
        result = applyObservations(original, [observation(status='failed', error='timeout')], DATE)
        self.assertEqual(result['history'], original['history'])
        self.assertEqual(result['projects'][0]['stargazers_count'], 100)
        self.assertEqual(result['projects'][0]['observation_status'], 'retained')
        empty = snapshot()
        empty['history']['a/old'].pop('2026-10-19')
        fresh = applyObservations(empty, [observation()], DATE)
        self.assertIsNone(fresh['projects'][0]['delta_1d'])
        self.assertNotIn('2026-10-19', fresh['history']['a/old'])

    def test_cross_utc_date_and_invalid_star_never_write(self):
        for item in [observation(observed_at='2026-10-21T00:00:00Z'), observation(stargazers_count=-1),
                     observation(observed_at='2026-10-20T00:30:00+08:00')]:
            with self.subTest(item=item):
                result = applyObservations(snapshot(), [item], DATE)
                self.assertNotIn(DATE, result['history']['a/old'])

    def test_same_day_rerun_changes_only_today_and_archived_is_observed(self):
        first = applyObservations(snapshot(), [observation()], DATE)
        result = applyObservations(first, [observation(stargazers_count=90, archived=True)], DATE)
        self.assertEqual(result['history']['a/old'], {'2026-10-19': 100, '2026-10-13': 105, DATE: 90})
        self.assertTrue(result['projects'][0]['archived'])
        self.assertEqual(result['projects'][0]['observation_status'], 'fresh')

    def test_history_owner_collision_does_not_merge_series(self):
        old = snapshot()
        old['projects'].append({'full_name': 'b/new', 'node_id': 'R2', 'created_at': CREATED,
                                'history_key': 'b/new', 'stargazers_count': 10})
        old['history']['b/new'] = {'2026-10-19': 10}
        result = applyObservations(old, [observation(full_name='b/new')], DATE)
        self.assertEqual(result['history'], old['history'])
        self.assertEqual(result['projects'][0]['observation_status'], 'identity_conflict')

    def test_candidate_score_is_recomputed_using_unchanged_v33_formula(self):
        result = applyObservations(snapshot(), [observation()], DATE)
        age = 657
        expected = round((-10)*2 + (-5)*3 + 95/(age+12)*3, 1)
        self.assertEqual(result['projects'][0]['discovery_score'], expected)

    def test_missing_observation_preserves_real_last_observed_time(self):
        old = snapshot()
        old['projects'][0]['last_observed_at'] = '2026-10-19T22:00:00Z'
        result = applyObservations(old, [], DATE)
        self.assertEqual(result['projects'][0]['last_observed_at'], '2026-10-19T22:00:00Z')
        self.assertEqual(result['projects'][0]['observation_status'], 'deferred')
