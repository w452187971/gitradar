import unittest

from gitradar.evaluation import evaluateObservation


class ObservationEvaluationTests(unittest.TestCase):
    def evaluate(self, runs=None, now='2026-10-22T00:00:00Z', references=None, projects=None):
        return evaluateObservation({'fixed_cohort': ['o/old'], 'runs': runs or []}, projects or [],
                                   ['o/old'], [], references or [], '2026-10-20T12:00:00Z', now)

    def test_observation_begins_next_full_utc_date(self):
        result = self.evaluate()
        self.assertEqual(result['window_start'], '2026-10-21')
        self.assertEqual(result['scheduled_coverage']['status'], 'unverified')

    def test_manual_runs_cannot_replace_missing_schedules(self):
        runs = [{'utc_date': f'2026-10-{day:02d}', 'run_kind': 'workflow_dispatch',
                 'cohort_size': 1, 'cohort_fresh': 1, 'recommendation_count': 20,
                 'recommendation_fresh_count': 20} for day in range(21, 32)]
        result = self.evaluate(runs, now='2026-11-07T00:00:00Z')
        self.assertEqual(result['scheduled_coverage']['successful_days'], 0)
        self.assertEqual(result['scheduled_coverage']['status'], 'failed')

    def test_repeated_schedule_runs_on_one_day_count_once(self):
        run = {'utc_date': '2026-10-21', 'run_kind': 'schedule', 'cohort_size': 1,
               'cohort_fresh': 1, 'recommendation_count': 20, 'recommendation_fresh_count': 20}
        self.assertEqual(self.evaluate([run] * 14)['scheduled_coverage']['successful_days'], 1)

    def test_run_cannot_reduce_frozen_cohort_denominator(self):
        report = {'fixed_cohort': ['o/a', 'o/b'], 'runs': [{'utc_date': '2026-10-21',
                  'run_kind': 'schedule', 'cohort_size': 1, 'cohort_fresh': 1,
                  'recommendation_count': 20, 'recommendation_fresh_count': 20}]}
        result = evaluateObservation(report, [], [], [], [], '2026-10-20T12:00:00Z', '2026-10-22T00:00:00Z')
        self.assertEqual(result['scheduled_coverage']['successful_days'], 0)

    def test_reference_extension_uses_unique_in_window_sample_count(self):
        refs = [{'full_name': f'o/p{i}', 'first_public_seen_at': '2026-11-06T00:00:00Z',
                 'independently_eligible': True} for i in range(20)]
        result = self.evaluate(now='2026-12-01T00:00:00Z', references=refs)
        self.assertEqual(result['reference_discovery']['sampling_days'], 28)
        self.assertEqual(result['reference_discovery']['sample_count'], 20)

    def test_seed_or_old_pool_cannot_be_counted_as_automatic_new(self):
        new = {'full_name': 'o/old', 'node_id': 'N1', 'discovery_kind': 'automatic_new',
               'first_recommended_at': '2026-10-21T10:00:00Z', 'content': {'review_kind': 'automatic_template'}}
        run = {'utc_date': '2026-10-21', 'new_recommendations': [new]}
        self.assertEqual(self.evaluate([run])['automatic_new']['count'], 0)

    def test_reference_collection_without_enough_samples_stays_unverified(self):
        result = self.evaluate(now='2026-12-01T00:00:00Z')
        self.assertEqual(result['reference_discovery']['status'], 'unverified')
        self.assertEqual(result['reference_discovery']['sample_count'], 0)

    def test_reference_detection_uses_observation_time_instead_of_creation_time(self):
        references = [{'full_name': 'o/new', 'first_public_seen_at': '2026-10-22T00:00:00Z',
                       'independently_eligible': True}] * 20
        project = {'full_name': 'o/new', 'first_observed_at': '2026-10-24T01:00:00Z',
                   'created_at': '2026-10-22T00:00:00Z'}
        result = self.evaluate(now='2026-12-01T00:00:00Z', references=references, projects=[project])
        self.assertEqual(result['reference_discovery']['sample_count'], 1)
        self.assertEqual(result['reference_discovery']['detected_within_48h'], 0)


if __name__ == '__main__':
    unittest.main()
