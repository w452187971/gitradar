import base64
import contextlib
import datetime as dt
import io
import unittest
import urllib.parse
from unittest.mock import patch

import collect


TODAY = dt.date(2026, 10, 20)


def repository(name='sample/tool', stars=1600):
    return {'full_name': name, 'html_url': 'https://github.com/' + name,
            'description': 'A desktop tool.', 'topics': [], 'stargazers_count': stars,
            'created_at': '2026-10-19T00:00:00Z', 'fork': False, 'archived': False}


class DiscoveryRulesTests(unittest.TestCase):
    def discover(self, today=TODAY, total=201, incomplete=False, fail=False):
        requests, reports, warnings = [], [], []

        def response(url, token=None):
            params = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)
            requests.append({key: values[0] for key, values in params.items()})
            if fail:
                raise TimeoutError('search unavailable')
            return {'items': [repository()], 'total_count': total, 'incomplete_results': incomplete}

        with patch.object(collect, 'api', side_effect=response), patch('time.sleep'):
            try:
                repos = collect.discover(today, None, warnings, reports)
            except TypeError as error:
                self.fail('discover must accept optional search reports: ' + str(error))
        return repos, requests, reports, warnings

    def testQueriesAddLowStarAndOldProjectEntrancesWithServerFilters(self):
        queries = collect.discoveryQueries(TODAY)
        self.assertEqual(18, len(queries))
        self.assertTrue(all('fork:false' in q and 'archived:false' in q for q in queries))
        self.assertTrue(any('stars:5..49' in q and 'created:>=2026-09-20' in q for q in queries))
        for stars in ['20..2999', '3000..9999', '>=10000']:
            self.assertTrue(any('created:<2026-07-22' in q and 'pushed:>=2026-10-13' in q
                                and 'stars:' + stars in q for q in queries))

    def testEighteenPrimarySearchesAndTwoBoundedExtraPages(self):
        _, requests, reports, warnings = self.discover(total=201)
        self.assertEqual(20, len(requests))
        self.assertTrue(all(request['page'] == '1' for request in requests[:18]))
        self.assertTrue(all(2 <= int(request['page']) <= 3 for request in requests[18:]))
        self.assertEqual(20, len(reports))
        self.assertTrue(all(report['succeeded'] and report['limited'] for report in reports))
        self.assertEqual([], warnings)

    def testNoExtraPagesAreRequestedWhenAllResultsFitOnOnePage(self):
        _, requests, reports, _ = self.discover(total=100)
        self.assertEqual(18, len(requests))
        self.assertTrue(all(not report['limited'] for report in reports))

    def testPrimarySortAlternatesByDayAndQueryIndex(self):
        first = self.discover(total=1)[1]
        second = self.discover(today=TODAY + dt.timedelta(days=1), total=1)[1]
        self.assertEqual({'stars', 'updated'}, {request['sort'] for request in first})
        self.assertTrue(all(a['sort'] != b['sort'] for a, b in zip(first, second)))

    def testExtraQueriesAndValidPagesRotateRatherThanAlwaysRepeatingTheFront(self):
        seenQueries, seenPages = set(), set()
        for day in range(12):
            requests = self.discover(today=TODAY + dt.timedelta(days=day), total=201)[1]
            primaryQueries = [request['q'] for request in requests[:18]]
            for request in requests[18:]:
                seenQueries.add(primaryQueries.index(request['q']))
                seenPages.add(int(request['page']))
        self.assertEqual(set(range(18)), seenQueries)
        self.assertEqual({2, 3}, seenPages)

    def testIncompleteResponsesWarnButKeepSuccessfulMetadata(self):
        _, _, reports, warnings = self.discover(total=1, incomplete=True)
        self.assertEqual(18, len(reports))
        self.assertTrue(all(r['succeeded'] and r['incomplete'] and r['returned'] == 1 for r in reports))
        self.assertTrue(any('incomplete' in warning.lower() for warning in warnings))

    def testFailuresAreReportedWithoutTriggeringUnboundedRequests(self):
        repos, requests, reports, warnings = self.discover(fail=True)
        self.assertEqual({}, repos)
        self.assertEqual(18, len(requests))
        self.assertTrue(all(not r['succeeded'] and r['returned'] == 0 for r in reports))
        self.assertEqual(18, len(warnings))

    def testThreeArgumentDiscoveryCallRemainsSupportedAndFiltersResponses(self):
        bad = repository('sample/fork')
        bad['fork'] = True
        with patch.object(collect, 'api', return_value={'items': [bad, repository()], 'total_count': 2}):
            with patch('time.sleep'):
                self.assertEqual({'sample/tool'}, set(collect.discover(TODAY, None, [])))


class ScoreAndObservationTests(unittest.TestCase):
    def testCategoryDoesNotAddAnUnrelatedNinetyPointReward(self):
        first = repository()
        second = {**first, 'description': 'A novel project.', 'full_name': 'sample/unknown'}
        self.assertEqual(collect.buildProject(first, {}, TODAY)['discovery_score'],
                         collect.buildProject(second, {}, TODAY)['discovery_score'])

    def testNegativeNetGrowthRetainsItsExistingWeights(self):
        history = {'sample/tool': {'2026-10-19': 1700, '2026-10-13': 1800}}
        result = collect.buildProject(repository(), history, TODAY)
        self.assertEqual((-100, -200), (result['delta_1d'], result['delta_7d']))
        self.assertEqual(-330.8, result['discovery_score'])

    def testFreshObservationDatesComeFromPreservedHistory(self):
        history = {'sample/tool': {'2026-01-01': 10, '2026-10-19': 1500}}
        result = collect.buildProject(repository(), history, TODAY)
        self.assertEqual('2026-01-01', result.get('first_seen_date'))
        self.assertEqual('2026-10-20', result.get('last_observed_date'))
        self.assertEqual('fresh', result.get('observation_status'))

    def testFailedRefreshDerivesRetainedDatesWithoutWritingToday(self):
        history = {'sample/tool': {'2026-01-01': 10, '2026-10-19': 1500}}
        with patch.object(collect, 'api', side_effect=TimeoutError('unavailable')), patch('time.sleep'):
            try:
                result = collect.refreshTracked([repository()], {}, None, [], history)[0]
            except TypeError as error:
                self.fail('refreshTracked must accept optional history: ' + str(error))
        self.assertEqual('2026-01-01', result.get('first_seen_date'))
        self.assertEqual('2026-10-19', result.get('last_observed_date'))
        self.assertEqual('retained', result.get('observation_status'))
        self.assertNotIn('2026-10-20', history['sample/tool'])

    def testMainPublishesRulesVersionWithSearchAndObservationMetadata(self):
        captured = {}
        history = {'sample/tool': {'2026-10-19': 1500}}

        def discover(today, token, warnings, reports=None):
            reports.append({'query': 'sample', 'sort': 'stars', 'page': 1, 'returned': 1,
                            'total_count': 1, 'incomplete': False, 'limited': False, 'succeeded': True})
            return {'sample/tool': repository()}

        def save(dataDir, savedHistory, summaries, document):
            captured.update(document)

        payload = {'content': base64.b64encode(b'A file manager.').decode()}
        with patch.object(collect, 'loadState', return_value=([], history, {})):
            with patch.object(collect, 'discover', side_effect=discover), patch.object(collect, 'api', return_value=payload):
                with patch.object(collect, 'saveSnapshots', side_effect=save), patch('time.sleep'):
                    with contextlib.redirect_stdout(io.StringIO()):
                        collect.legacyMain()
        self.assertEqual('v3.3', captured.get('rules_version'))
        self.assertEqual(1, captured['collection_stats']['refreshed_count'])
        self.assertEqual(1, captured['collection_stats']['search_attempted'])
        self.assertEqual('sample', captured['search_reports'][0]['query'])


if __name__ == '__main__':
    unittest.main()
