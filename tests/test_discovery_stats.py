import copy
import unittest

import discovery_stats


EMPTY_STATS = {
    'observed_since': None, 'observed_through': None, 'observed_dates': 0,
    'refreshed_count': 0, 'retained_count': 0, 'newly_discovered_count': 0,
    'daily_coverage': 0, 'weekly_coverage': 0,
    'readme_checked_count': 0, 'readme_stale_count': 0,
    'search_attempted': 0, 'search_succeeded': 0,
    'search_limited': 0, 'search_incomplete': 0,
}


class ObservationMetadataTests(unittest.TestCase):
    def testObservationDatesComeFromThisProjectsHistory(self):
        history = {'sample/tool': {'2026-10-20': 120, '2026-10-03': 100},
                   'sample/other': {'2025-01-01': 10}}
        self.assertEqual({
            'first_seen_date': '2026-10-03', 'last_observed_date': '2026-10-20',
            'observation_status': 'fresh',
        }, discovery_stats.observationMetadata('sample/tool', history, True))

    def testRetainedStatusDoesNotAdvanceTheLastObservedDate(self):
        history = {'sample/tool': {'2026-10-19': 100}}
        self.assertEqual({
            'first_seen_date': '2026-10-19', 'last_observed_date': '2026-10-19',
            'observation_status': 'retained',
        }, discovery_stats.observationMetadata('sample/tool', history, False))

    def testMissingOrEmptyHistoryDoesNotInventObservationDates(self):
        for history in [{}, {'sample/tool': {}}]:
            with self.subTest(history=history):
                self.assertEqual({'observation_status': 'fresh'},
                                 discovery_stats.observationMetadata('sample/tool', history, True))
                self.assertEqual({'observation_status': 'retained'},
                                 discovery_stats.observationMetadata('sample/tool', history, False))


class CollectionStatsTests(unittest.TestCase):
    def testEmptyInputsReturnUnknownDatesAndZeroCounts(self):
        self.assertEqual(EMPTY_STATS, discovery_stats.collectionStats([], {}, set(), []))

    def testGlobalDatesIncludePreviouslyObservedProjectsOutsideTheCurrentList(self):
        history = {'sample/old': {'2026-10-01': 50, '2026-10-03': 60},
                   'sample/current': {'2026-10-03': 100, '2026-10-20': 120}}
        actual = discovery_stats.collectionStats(
            [{'full_name': 'sample/current'}], history, {'sample/current'}, [])
        self.assertEqual({**EMPTY_STATS, 'observed_since': '2026-10-01',
                          'observed_through': '2026-10-20', 'observed_dates': 3}, actual)

    def testRefreshCountsUseExplicitStatusRatherThanCandidateCount(self):
        items = [{'observation_status': 'fresh'}, {'observation_status': 'fresh'},
                 {'observation_status': 'retained'}, {}, {'observation_status': 'unknown'}]
        actual = discovery_stats.collectionStats(items, {}, set(), [])
        self.assertEqual(2, actual['refreshed_count'])
        self.assertEqual(1, actual['retained_count'])

    def testNewDiscoveriesDeduplicateCaseAndIgnorePreviouslyKnownIdentities(self):
        items = [{'full_name': 'Sample/Old'}, {'full_name': 'sample/old'},
                 {'full_name': 'Sample/New'}, {'full_name': 'sample/new'},
                 {'full_name': 'sample/second'}, {}, {'full_name': ''}]
        actual = discovery_stats.collectionStats(items, {}, {'SAMPLE/OLD'}, [])
        self.assertEqual(2, actual['newly_discovered_count'])

    def testDeltaCoverageIncludesZeroAndNegativeIntegersButExcludesBooleans(self):
        items = [{'delta_1d': 0, 'delta_7d': -3}, {'delta_1d': -2, 'delta_7d': 5},
                 {'delta_1d': 4, 'delta_7d': 0}, {'delta_1d': True, 'delta_7d': False},
                 {'delta_1d': 1.5, 'delta_7d': '4'}, {'delta_1d': None}, {}]
        actual = discovery_stats.collectionStats(items, {}, set(), [])
        self.assertEqual(3, actual['daily_coverage'])
        self.assertEqual(3, actual['weekly_coverage'])

    def testStaleReadmeCountsRequireAnActualReadmeCheck(self):
        items = [{'readme_checked': True, 'readme_stale': False},
                 {'readme_checked': True, 'readme_stale': True},
                 {'readme_checked': False, 'readme_stale': True},
                 {'readme_stale': True}, {}]
        actual = discovery_stats.collectionStats(items, {}, set(), [])
        self.assertEqual(2, actual['readme_checked_count'])
        self.assertEqual(1, actual['readme_stale_count'])

    def testSearchStatsDistinguishAttemptsFailuresLimitsAndIncompleteResults(self):
        searches = [
            {'query': 'recent', 'sort': 'stars', 'page': 1, 'returned': 100,
             'total_count': 1000, 'succeeded': True, 'limited': True, 'incomplete': False},
            {'query': 'recent', 'sort': 'updated', 'page': 1, 'returned': 20,
             'total_count': 20, 'succeeded': True, 'limited': False, 'incomplete': True},
            {'query': 'topic', 'succeeded': False, 'total_count': None},
            {'query': 'other', 'succeeded': True, 'returned': 0},
            {'query': 'failed', 'succeeded': False},
        ]
        actual = discovery_stats.collectionStats([], {}, set(), searches)
        self.assertEqual({**EMPTY_STATS, 'search_attempted': 5, 'search_succeeded': 3,
                          'search_limited': 1, 'search_incomplete': 1}, actual)

    def testHelpersDoNotMutateCallerOwnedData(self):
        items = [{'full_name': 'sample/new', 'observation_status': 'fresh', 'delta_1d': 0}]
        history = {'sample/new': {'2026-10-20': 120, '2026-10-19': 120}}
        previousNames = {'Sample/Old'}
        searches = [{'query': 'recent', 'succeeded': True}]
        before = copy.deepcopy((items, history, previousNames, searches))
        discovery_stats.observationMetadata('sample/new', history, True)
        discovery_stats.collectionStats(items, history, previousNames, searches)
        self.assertEqual(before, (items, history, previousNames, searches))


if __name__ == '__main__':
    unittest.main()
