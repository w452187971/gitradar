"""Static delivery must not turn old scores or untrusted strings into reviewed facts."""
import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from gitradar.content import resolveContent
from test_v4_content import NOW, sampleContent

try:
    from gitradar.site import buildSite
except ImportError:
    buildSite = None


def project(index=0):
    facts, editorial = sampleContent()
    content = resolveContent(facts, editorial, NOW)
    name = f'demo/search{index}'
    return {'full_name': name, 'history_key': name, 'content': content,
            'stargazers_count': 123, 'recommendation_reason': '按内容搜索本地文件；本站首次推荐'}


def snapshot(count=1):
    projects = [project(index) for index in range(count)]
    return {'schema_version': '4.0', 'batch_id': 'batch-a', 'generated_at': NOW,
            'source_commit': 'abc123', 'projects': projects,
            'recommendations': {'batch_id': 'batch-a', 'recommendations': projects},
            'warnings': [], 'saved_aliases': {'old/search': 'demo/search0'}}


class SiteTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(buildSite, '缺少 buildSite 静态生成能力')
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.output = Path(self.temporary.name)

    def build(self, data=None):
        return buildSite(data or snapshot(), self.output)

    def read(self, name):
        return (self.output / name).read_text()

    def testHomepageAndSceneDirectoryReadableWithoutExecutingScripts(self):
        manifest = self.build(snapshot(8))
        html = self.read('index.html')
        self.assertEqual(8, html.count('data-project="'))
        for text in ('按文件内容搜索电脑里的文档', 'Windows', '官方发行页', '适合谁', '需要准备', '推荐依据'):
            self.assertIn(text, html)
        self.assertIn('data-initial="false"', html)
        self.assertIn('explore.html#day', html)
        self.assertIn('文件查找', self.read('scenes.html'))
        self.assertEqual('batch-a', manifest['batch_id'])

    def testShareableDetailIncludesEvidenceAndExplicitReviewBoundary(self):
        self.build()
        detail = self.read('projects/demo--search0.html')
        for text in ('适合谁', '前置条件', '已知限制', '证据', '未实际试用', NOW[:10], 'MIT'):
            self.assertIn(text, detail)
        self.assertIn('../scenes.html', detail)
        self.assertIn('id="interaction-status"', detail)
        self.assertIn('https://github.com/demo/search/releases', detail)

    def testEveryArtifactHashMatchesBytesAndPathsRemainInsideOutput(self):
        manifest = self.build()
        for name, digest in manifest['artifacts'].items():
            self.assertTrue((self.output / name).resolve().is_relative_to(self.output.resolve()))
            self.assertEqual(hashlib.sha256((self.output / name).read_bytes()).hexdigest(), digest)
        self.assertIn('assets/site.js', manifest['artifacts'])
        self.assertIn('explore.html', manifest['artifacts'])

    def testZeroAndLegacyDataDoNotPretendToBeQualifiedRecommendations(self):
        for data in (snapshot(0), {'projects': [project()], 'generated_at': NOW}):
            self.build(data)
            html = self.read('index.html')
            self.assertNotIn('data-project="', html)
            self.assertIn('暂无符合当前资料门槛的推荐', html)
            self.assertIn('explore.html', html)

    def testUnreviewedFeedItemCannotBeLaunderedByTheRenderer(self):
        data = snapshot()
        data['recommendations']['recommendations'][0]['content']['effective_status'] = 'review_required'
        self.build(data)
        self.assertNotIn('data-project="', self.read('index.html'))

    def testRepositoryIdentityAndArchivedStateCannotBypassDirectoryQualification(self):
        for flags in ({'identity_conflict': True}, {'archived': True}, {'fork': True}):
            data = snapshot()
            data['projects'][0].update(flags)
            self.build(data)
            self.assertNotIn('data-project="', self.read('index.html'))
            self.assertNotIn('data-project="', self.read('scenes.html'))

    def testSourceStringsAreTextAndUnsafeUrlsNeverBecomeLinks(self):
        data = snapshot()
        content = data['projects'][0]['content']
        content['purpose'] = '<img src=x onerror=alert(1)> 跨设备文件查找'
        content['audience'] = '</script><script>alert(1)</script>'
        content['evidence_refs'].append({'url': 'javascript:alert(1)', 'section': '<svg onload=x>'})
        self.build(data)
        html = self.read('index.html') + self.read('projects/demo--search0.html')
        self.assertNotIn('<img src=x', html)
        self.assertNotIn('<script>alert', html)
        self.assertNotIn('href="javascript:', html)
        self.assertIn('&lt;img', html)

    def testBatchMismatchFailsBeforeReplacingPublishedHomepage(self):
        self.build()
        old = self.read('index.html')
        data = snapshot()
        data['recommendations']['batch_id'] = 'other-batch'
        with self.assertRaisesRegex(ValueError, 'batch|批次'):
            self.build(data)
        self.assertEqual(old, self.read('index.html'))

    def testRetiredDetailsKeepOriginalEvidenceDateAndDisableMissingPath(self):
        self.build()
        data = snapshot(0)
        withdrawn = project()
        withdrawn['content']['effective_status'] = 'blocked'
        withdrawn['content']['invalidation_reasons'] = ['not_found:usage_paths']
        withdrawn['content']['evidence_refs'][0]['path_status'] = 404
        data['projects'] = [withdrawn]
        self.build(data)
        detail = self.read('projects/demo--search0.html')
        self.assertIn('已退出本期推荐', detail)
        self.assertIn(NOW[:10], detail)
        self.assertNotIn('href="https://github.com/demo/search/releases"', detail)
        self.assertIn('入口已停用', detail)

    def testWithdrawnPathStaysDisabledAcrossLaterBatchesAndEvidenceLinks(self):
        data = snapshot()
        data['projects'][0]['content']['evidence_refs'].append({
            'id': 'official_path', 'url': 'https://github.com/demo/search/releases',
            'section': 'Acquisition', 'status': 200, 'checked_at': NOW})
        self.build(data)
        missing = copy.deepcopy(data['projects'][0])
        missing['content']['effective_status'] = 'blocked'
        missing['content']['invalidation_reasons'] = ['not_found:official_path']
        missing['content']['evidence_refs'][-1]['status'] = 404
        withdrawn = snapshot(0)
        withdrawn['projects'] = [missing]
        self.build(withdrawn)
        self.build(snapshot(0))
        detail = self.read('projects/demo--search0.html')
        self.assertIn('入口已停用', detail)
        self.assertNotIn('href="https://github.com/demo/search/releases"', detail)

    def testTopLevelUnavailableStatusDisablesOldDetailAcquisition(self):
        for flags in ({'status': 'not_found'}, {'status': 'blocked'}, {'http_status': 404},
                      {'http_status': 410}, {'observation_status': 'identity_conflict'}):
            data = snapshot()
            self.build(data)
            withdrawn = snapshot(0)
            withdrawn['projects'] = [project()]
            withdrawn['projects'][0].update(flags)
            self.build(withdrawn)
            detail = self.read('projects/demo--search0.html')
            self.assertIn('入口已停用', detail)
            self.assertNotIn('href="https://github.com/demo/search/releases"', detail)

    def testUnknownExistingDetailsAreNeverDeleted(self):
        directory = self.output / 'projects'
        directory.mkdir()
        (directory / 'legacy.html').write_text('historical shared page')
        self.build(snapshot(0))
        self.assertEqual('historical shared page', self.read('projects/legacy.html'))

    def testDiscoverySourcesDistinguishEditorialSeedsFromAutomaticNewProjects(self):
        data = snapshot()
        data['recommendations']['discovery_counts'] = {'automatic_new': 0, 'seed': 1,
            'baseline_backfill': 0, 'manual_addition': 0, 'rotation': 0}
        self.build(data)
        html = self.read('index.html')
        self.assertIn('自动新发现 0', html)
        self.assertIn('首批审核种子 1', html)
        self.assertIn('旧池补齐 0', html)
        self.assertIn('人工补充 0', html)
        self.assertIn('轮换 0', html)

    def testSavedAliasesAreAvailableWithoutReplacingTheOldStorageKey(self):
        self.build()
        state = json.loads(self.read('data/site-state.json'))
        self.assertEqual('demo/search0', state['saved_aliases']['old/search'])
        self.assertIn('data-save="demo/search0"', self.read('index.html'))

    def testGeneratorRejectsUnsafeRepositoryPaths(self):
        data = snapshot()
        data['projects'][0]['history_key'] = '../../escape'
        with self.assertRaises(ValueError):
            self.build(data)
        self.assertFalse((self.output.parent / 'escape.html').exists())


if __name__ == '__main__':
    unittest.main()
