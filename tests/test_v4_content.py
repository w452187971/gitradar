import copy
import datetime as dt
import unittest

from gitradar.content import deriveFacts, eligibleForRecommendation, resolveContent

NOW = '2026-10-20T12:00:00Z'


def sampleContent():
    fields = {'purpose': '按文件内容搜索电脑里的文档', 'audience': '经常找不到本地文档的人',
              'platforms': ['Windows'], 'form': 'desktop_app', 'prerequisites': [],
              'license': 'MIT', 'cost': '官方未说明费用',
              'usage_paths': [{'url': 'https://github.com/demo/search/releases',
                               'kind': 'download', 'label': '官方发行页'}]}
    refs = [{'id': key, 'url': 'https://github.com/demo/search/blob/main/README.md',
             'section': 'Installation' if key == 'usage_paths' else 'Introduction',
             'content_hash': key + '-v1', 'checked_at': NOW, 'status': 200,
             'source_kind': 'readme', 'text': 'Official project documentation.'}
            for key in fields]
    facts = deriveFacts({'full_name': 'demo/search', 'refs': refs,
                         'facts': {key: {'value': value, 'ref_ids': [key], 'complete': True}
                                   for key, value in fields.items()}})
    curation = dict(fields, status='published', review_kind='source_review',
                    scenes=['文件查找'], primary_scene='文件查找',
                    recommendation_reason='在本机按文档内容找文件',
                    claims={key: [key] for key in fields},
                    evidence_hashes={key: key + '-v1' for key in fields})
    return facts, curation


class ContentTests(unittest.TestCase):
    def testEditorialCriticalUnknownCannotBeErasedByMachineFacts(self):
        facts, curation = sampleContent()
        curation['critical_unknowns'] = ['required_account']
        content = resolveContent(facts, curation, NOW)
        self.assertFalse(content['eligibility']['eligible'])

    def testOfficialChinesePurposeTakesPriorityOverEnglish(self):
        refs = []
        for identifier, text in [('english', 'A file converter.'),
                                 ('chinese', '这是一款记录和整理笔记的应用。')]:
            refs.append({'id': identifier, 'url': 'https://github.com/demo/search',
                         'section': 'Introduction', 'source_kind': 'readme',
                         'text': text, 'content_hash': identifier, 'checked_at': NOW, 'status': 200})
        facts = deriveFacts({'full_name': 'demo/search', 'refs': refs})
        self.assertEqual(facts.get('purpose'), '记录和整理笔记')
        self.assertEqual(facts['claims']['purpose'], ['chinese'])

    def testReviewedEvidencePassesWithoutChangingLegacyOrEditorialFields(self):
        facts, curation = sampleContent()
        original = copy.deepcopy(curation)
        content = resolveContent(facts, curation, NOW)
        self.assertEqual('published', content['effective_status'])
        self.assertTrue(eligibleForRecommendation(content, asOf=NOW)['eligible'])
        self.assertEqual(original, curation)
        self.assertEqual('官方未说明费用', content['cost'])

    def testHashChangeWithdrawsReviewButKeepsEditorialConclusion(self):
        facts, curation = sampleContent()
        facts['evidence_refs'][0]['content_hash'] = 'changed'
        content = resolveContent(facts, curation, NOW)
        self.assertEqual('review_required', content['effective_status'])
        self.assertEqual(curation['purpose'], content['purpose'])
        self.assertFalse(eligibleForRecommendation(content, asOf=NOW)['eligible'])

    def testFreshnessUsesFactFourteenAndPathSevenDays(self):
        for key, days, expected in [('purpose', 14, True), ('purpose', 15, False),
                                    ('usage_paths', 7, True), ('usage_paths', 8, False)]:
            with self.subTest(key=key, days=days):
                facts, curation = sampleContent()
                checked = dt.datetime(2026, 10, 20, 12, tzinfo=dt.timezone.utc) - dt.timedelta(days=days)
                next(ref for ref in facts['evidence_refs'] if ref['id'] == key)['checked_at'] = checked.isoformat()
                content = resolveContent(facts, curation, NOW)
                self.assertEqual(expected, eligibleForRecommendation(content, asOf=NOW)['eligible'])

    def testConfirmedMissingAndCriticalUnknownBlockRecommendation(self):
        facts, curation = sampleContent()
        facts['evidence_refs'][0]['status'] = 404
        self.assertEqual('blocked', resolveContent(facts, curation, NOW)['effective_status'])
        facts, curation = sampleContent()
        facts['critical_unknowns'] = ['required_account']
        self.assertFalse(eligibleForRecommendation(resolveContent(facts, curation, NOW), asOf=NOW)['eligible'])

    def testUnknownLicenseAndUnboundOfficialPathCannotPass(self):
        for field, value in [('license', 'NOASSERTION'),
                             ('usage_paths', [{'url': 'https://evil.example/download', 'kind': 'download'}])]:
            facts, curation = sampleContent()
            curation[field] = value
            self.assertFalse(eligibleForRecommendation(resolveContent(facts, curation, NOW), asOf=NOW)['eligible'])

    def testAutomaticPurposeDoesNotUseExamplesNegationOrAnotherSubject(self):
        for text, section in [('A file converter.', 'Examples'),
                              ('This is not a file converter.', 'Introduction'),
                              ('OtherTool is a file converter.', 'Introduction'),
                              ('Integration with a file converter.', 'Introduction')]:
            facts = deriveFacts({'full_name': 'demo/search', 'refs': [{
                'id': 'intro', 'url': 'https://github.com/demo/search', 'section': section,
                'text': text, 'content_hash': 'h', 'checked_at': NOW, 'status': 200,
                'source_kind': 'readme'}]})
            self.assertFalse(facts.get('purpose'))

    def testSixSupportedTemplatesRemainSpecificAndUnknownStaysUnknown(self):
        for text, purpose in [('A file converter.', '文件格式转换'),
                              ('A local file search tool.', '搜索本地文件'),
                              ('A note-taking application.', '记录和整理笔记'),
                              ('A media downloader.', '下载媒体内容'),
                              ('A password manager.', '保存和管理密码'),
                              ('A desktop application launcher.', '启动桌面应用')]:
            facts = deriveFacts({'full_name': 'demo/search', 'refs': [{
                'id': 'intro', 'url': 'https://github.com/demo/search', 'section': 'Introduction',
                'text': text, 'content_hash': 'h', 'checked_at': NOW, 'status': 200,
                'source_kind': 'readme'}]})
            self.assertIn(purpose, facts['purpose'])
        self.assertFalse(deriveFacts({'full_name': 'demo/search', 'refs': []}).get('purpose'))

    def testReleaseSourceArchiveDoesNotImplyGuiOrPlatforms(self):
        facts = deriveFacts({'full_name': 'demo/search', 'refs': [{
            'id': 'release', 'url': 'https://github.com/demo/search/releases',
            'section': 'Assets', 'text': 'source.zip search.exe',
            'content_hash': 'h', 'checked_at': NOW, 'status': 200, 'source_kind': 'release'}]})
        self.assertEqual('unknown', facts['form'])
        self.assertEqual([], facts['platforms'])


class AutomaticContentTests(unittest.TestCase):
    def testCompanionApplicationCannotEstablishThisProjectsForm(self):
        bundle = self.bundle()
        bundle['refs'][0]['text'] = 'FastFind is a local file search tool.'
        bundle['refs'][1]['text'] = ('The companion is a desktop application.\nSupports Windows.\n'
                                   'Requires an account.\n'
                                   '[Download](https://github.com/demo/FastFind/releases)')
        content = resolveContent(deriveFacts(bundle), asOf=NOW)
        self.assertFalse(content['eligibility']['eligible'])

    def bundle(self):
        return {'full_name': 'demo/FastFind', 'refs': [
            {'id': 'intro', 'url': 'https://github.com/demo/FastFind/blob/main/README.md',
             'section': 'Introduction', 'source_kind': 'readme', 'status': 200,
             'content_hash': 'intro-v1', 'checked_at': NOW,
             'text': 'FastFind is a local file search tool for Windows.\nA desktop application.\nSupports Windows and macOS.'},
            {'id': 'install', 'url': 'https://github.com/demo/FastFind/blob/main/README.md',
             'section': 'Installation', 'source_kind': 'readme', 'status': 200,
             'content_hash': 'install-v1', 'checked_at': NOW,
             'text': 'Download the [desktop installer](https://github.com/demo/FastFind/releases).\nNo account or additional software required.\nFree of charge.'},
            {'id': 'metadata', 'url': 'https://api.github.com/repos/demo/FastFind',
             'section': 'License', 'source_kind': 'repository', 'status': 200,
             'content_hash': 'metadata-v1', 'checked_at': NOW,
             'license_spdx_id': 'MIT', 'text': 'Repository license metadata: MIT.'}]}

    def testRealisticReadmeStructureCanPublishAutomaticallyWithAllClaimsBound(self):
        content = resolveContent(deriveFacts(self.bundle()), asOf=NOW)
        self.assertEqual('published', content['effective_status'])
        self.assertEqual('automatic_template', content['review_kind'])
        self.assertTrue(eligibleForRecommendation(content, asOf=NOW)['eligible'])
        self.assertEqual(['Windows', 'macOS'], content['platforms'])
        self.assertEqual('desktop_app', content['form'])
        self.assertIn('免费', content['cost'])
        self.assertNotIn('实际试用', str(content))

    def testAutomaticIncompletePrerequisitesNeverPassBySilence(self):
        bundle = self.bundle()
        bundle['refs'][1]['text'] = 'Download the [desktop installer](https://github.com/demo/FastFind/releases).'
        content = resolveContent(deriveFacts(bundle), asOf=NOW)
        self.assertFalse(eligibleForRecommendation(content, asOf=NOW)['eligible'])
        self.assertIn('prerequisites', content['critical_unknowns'])

    def testAutomaticNegatedPlatformOrPurposeCannotPublish(self):
        for text in ['FastFind is not a local file search tool.\nA desktop application.\nSupports Windows.',
                     'FastFind is a local file search tool.\nA desktop application.\nDoes not support Windows.']:
            bundle = self.bundle()
            bundle['refs'][0]['text'] = text
            content = resolveContent(deriveFacts(bundle), asOf=NOW)
            self.assertFalse(eligibleForRecommendation(content, asOf=NOW)['eligible'])

    def testAutomaticPaidServiceIsNotRewrittenAsFree(self):
        bundle = self.bundle()
        bundle['refs'][1]['text'] = bundle['refs'][1]['text'].replace('Free of charge.', 'Requires a paid cloud account.')
        content = resolveContent(deriveFacts(bundle), asOf=NOW)
        self.assertNotIn('免费', content['cost'])
        self.assertIn('paid cloud account', str(content['prerequisites']))


class PathRefreshTests(unittest.TestCase):
    def testHeadRefreshDoesNotRefreshUnderlyingReadmeFact(self):
        facts, curation = sampleContent()
        ref = next(ref for ref in facts['evidence_refs'] if ref['id'] == 'usage_paths')
        ref.update(checked_at='2026-10-10T12:00:00Z', path_checked_at=NOW, path_status=200)
        self.assertTrue(eligibleForRecommendation(resolveContent(facts, curation, NOW), asOf=NOW)['eligible'])
        ref['checked_at'] = '2026-10-01T12:00:00Z'
        self.assertFalse(eligibleForRecommendation(resolveContent(facts, curation, NOW), asOf=NOW)['eligible'])

    def testConfirmedMissingPathWithdrawsImmediately(self):
        facts, curation = sampleContent()
        facts['evidence_refs'][-1]['path_status'] = 404
        self.assertFalse(eligibleForRecommendation(resolveContent(facts, curation, NOW), asOf=NOW)['eligible'])

    def testDeclaredCostEvidenceChangesCannotKeepOldReviewValid(self):
        facts, curation = sampleContent()
        next(ref for ref in facts['evidence_refs'] if ref['id'] == 'cost')['content_hash'] = 'paid-now'
        self.assertFalse(eligibleForRecommendation(resolveContent(facts, curation, NOW), asOf=NOW)['eligible'])


class ContextAndMultiplePathTests(unittest.TestCase):
    def test_context_change_blocks_until_editor_binds_current_context_hash(self):
        facts, curation = sampleContent()
        oldEditorial = copy.deepcopy(curation)
        ref = facts['evidence_refs'][0]
        ref.update(source_hash='new-context', context_changed=True)
        content = resolveContent(facts, curation, NOW)
        self.assertEqual(content['effective_status'], 'review_required')
        self.assertIn('context_changed:purpose', content['invalidation_reasons'])
        self.assertEqual(curation, oldEditorial)
        curation['evidence_context_hashes'] = {'purpose': 'new-context'}
        self.assertTrue(resolveContent(facts, curation, NOW)['eligibility']['eligible'])
        ref['source_hash'] = 'another-context'
        self.assertFalse(resolveContent(facts, curation, NOW)['eligibility']['eligible'])

    def test_shared_path_claim_requires_both_url_checks(self):
        facts, curation = sampleContent()
        second = {'url': 'https://github.com/demo/search/releases/second', 'kind': 'download'}
        curation['usage_paths'].append(second)
        ref = next(ref for ref in facts['evidence_refs'] if ref['id'] == 'usage_paths')
        firstUrl = curation['usage_paths'][0]['url']
        ref.update(path_checked_at=NOW, path_status=200, path_checks={
            firstUrl: {'status': 200, 'checked_at': NOW}, second['url']: {'status': 'unverified'}})
        self.assertFalse(resolveContent(facts, curation, NOW)['eligibility']['eligible'])
        ref['path_checks'][second['url']] = {'status': 404}
        self.assertFalse(resolveContent(facts, curation, NOW)['eligibility']['eligible'])
        ref['path_checks'][second['url']] = {'status': 200, 'checked_at': NOW}
        self.assertTrue(resolveContent(facts, curation, NOW)['eligibility']['eligible'])
