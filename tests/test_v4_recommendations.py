import copy
import unittest

from gitradar.content import resolveContent
from gitradar.recommendations import selectRecommendations
from test_v4_content import NOW, sampleContent


def candidate(index, scene='文件查找', form='desktop_app'):
    facts, curation = sampleContent()
    facts['full_name'] = 'demo/tool' + str(index)
    facts['node_id'] = 'node' + str(index)
    for ref in facts['evidence_refs']:
        ref['url'] = 'https://github.com/' + facts['full_name']
    curation.update(primary_scene=scene, scenes=[scene], form=form,
                    usage_paths=[{'url': 'https://github.com/' + facts['full_name'] + '/releases',
                                  'kind': 'download', 'label': '官方发行页'}])
    return {'full_name': facts['full_name'], 'node_id': facts['node_id'],
            'content': resolveContent(facts, curation, NOW), 'discovery_score': 100000 - index,
            'first_qualified_at': '2026-10-19T00:00:00Z'}


class RecommendationsTests(unittest.TestCase):
    def testRecentReleaseFromRealClientEvidenceCanUseMomentumSlot(self):
        from gitradar.github_client import GitHubClient
        item = candidate(1)
        item['first_qualified_at'] = '2026-09-01T00:00:00Z'
        ref = GitHubClient(now=lambda: NOW).makeEvidenceRef('Release notes', 'release', 'release',
            {'html_url': 'https://github.com/demo/tool1/releases/tag/v1',
             'published_at': '2026-10-19T00:00:00Z'}, {'full_name': 'demo/tool1'})
        item['content']['evidence_refs'].append(ref)
        feed = selectRecommendations([item], {}, NOW)
        self.assertEqual('momentum', feed['recommendations'][0]['slot'])

    def testLaterBatchRotatesQualifiedProjectsOutsideTheInitialTwenty(self):
        projects = [candidate(i, str(i % 4)) for i in range(29)]
        first = selectRecommendations(projects, {}, NOW)
        second = selectRecommendations(projects, first, '2026-10-21T12:00:00Z')
        initial = {p['node_id'] for p in first['recommendations']}
        later = {p['node_id'] for p in second['recommendations']}
        self.assertEqual(29, len(initial | later))
        self.assertEqual(NOW, second['first_recommended_at'][next(iter(initial & later))])

    def testUnavailableOrConflictedTopLevelObservationCannotRecommend(self):
        for fields in ({'observation_status': 'identity_conflict'}, {'archived': True},
                       {'fork': True}, {'status': 'not_found'}, {'http_status': 404}):
            with self.subTest(fields=fields):
                item = candidate(1)
                item.update(fields)
                self.assertEqual([], selectRecommendations([item], {}, NOW)['recommendations'])

    def testZeroEligibleDoesNotFillFromOldScores(self):
        item = candidate(1)
        item['content']['effective_status'] = 'queued'
        self.assertEqual([], selectRecommendations([item], {}, NOW)['recommendations'])

    def testTwentyDiverseProjectsBeginWithSixOrdinaryGuiItems(self):
        projects = [candidate(i, ['文件查找', '文件转换', '笔记效率', '隐私保护'][i % 4],
                              'library' if i < 10 else 'desktop_app') for i in range(40)]
        feed = selectRecommendations(projects, {}, NOW)
        selected = feed['recommendations']
        self.assertEqual(20, len(selected))
        self.assertTrue(all(item['content']['form'] == 'desktop_app' for item in selected[:6]))
        self.assertLessEqual(sum(item['content']['form'] == 'library' for item in selected), 4)
        self.assertEqual(4, len({item['primary_scene'] for item in selected}))
        self.assertTrue(all('discovery_score' in item for item in selected))

    def testSinglePrimarySceneQuotaCannotBeEvadedByExtraTags(self):
        projects = [candidate(i) for i in range(25)]
        for item in projects:
            item['content']['scenes'] = ['文件查找', '文件转换', '笔记效率', '隐私保护']
        selected = selectRecommendations(projects, {}, NOW)['recommendations']
        self.assertEqual(10, len(selected))
        self.assertEqual({'文件查找'}, {item['primary_scene'] for item in selected})

    def testIdentityAndConfirmedFamilyOnlyOccupyOneSlot(self):
        first, alias, mirror, separate = [candidate(i, str(i)) for i in range(4)]
        alias['node_id'] = first['node_id']
        first['content']['family'] = 'confirmed-family'
        mirror['content']['family'] = 'confirmed-family'
        self.assertEqual(2, len(selectRecommendations([first, alias, mirror, separate], {}, NOW)['recommendations']))

    def testFirstRecommendedDatePersistsAcrossExitAndReturn(self):
        project = candidate(1)
        initial = selectRecommendations([project], {}, NOW)
        empty = selectRecommendations([], initial, '2026-10-21T12:00:00Z')
        restored = selectRecommendations([project], empty, '2026-10-22T12:00:00Z')
        self.assertEqual(NOW, restored['first_recommended_at']['node1'])
        self.assertEqual(0, restored['discovery_counts']['automatic_new'])

    def testSeedAndBaselineBackfillDoNotBecomeAutomaticNewDiscoveries(self):
        projects = [candidate(i, str(i)) for i in range(4)]
        for item in projects:
            item.update(discovery_origin='automatic', first_observed_at='2026-10-19T00:00:00Z',
                        observation_started_at='2026-10-18T00:00:00Z', automatically_qualified=True)
        projects[0]['content']['seed'] = True
        projects[1]['in_frozen_baseline'] = True
        projects[2]['content']['review_kind'] = 'source_review'
        projects[3]['content']['review_kind'] = 'automatic_template'
        feed = selectRecommendations(projects, {}, NOW)
        self.assertEqual(1, feed['discovery_counts']['automatic_new'])
        self.assertEqual(1, feed['discovery_counts']['seed'])
        self.assertEqual(1, feed['discovery_counts']['baseline_backfill'])
        self.assertEqual(1, feed['discovery_counts']['manual_addition'])

    def testGrowthNeedsRealEndpointsAndSlotsRefillWithoutFabrication(self):
        projects = [candidate(i, str(i % 4)) for i in range(24)]
        for item in projects:
            item['delta_1d'] = 999
        feed = selectRecommendations(projects, {}, NOW)
        selected = feed['recommendations']
        self.assertEqual(20, len(selected))
        self.assertEqual(8, sum(item['slot'] == 'new' for item in selected))
        self.assertEqual(0, sum(item['slot'] == 'momentum' for item in selected))
        self.assertEqual(0, sum(item['slot'] == 'rotation' for item in selected))
        self.assertEqual(12, sum(item['slot'] == 'refill' for item in selected))
        self.assertFalse(any('增长' in item['recommendation_reason'] for item in selected))

    def testStaleEvidenceAndNoOrdinaryPrefixShrinkTheFeedHonestly(self):
        item = candidate(1, form='library')
        self.assertEqual([], selectRecommendations([item], {}, NOW)['recommendations'])
        item = candidate(2)
        self.assertEqual([], selectRecommendations([item], {}, '2026-11-20T00:00:00Z')['recommendations'])

    def testFeedSelectionDoesNotMutateCandidateOrPreviousState(self):
        projects = [candidate(1)]
        previous = {'first_recommended_at': {'other': '2026-01-01T00:00:00Z'}}
        before = copy.deepcopy((projects, previous))
        selectRecommendations(projects, previous, NOW)
        self.assertEqual(before, (projects, previous))


class IdentityCaseTests(unittest.TestCase):
    def testOpaqueNodeIdentifiersRemainCaseSensitiveAcrossRuns(self):
        item = candidate(1)
        item['node_id'] = 'R_AbCd'
        feed = selectRecommendations([item], {}, NOW)
        self.assertIn('R_AbCd', feed['first_recommended_at'])
