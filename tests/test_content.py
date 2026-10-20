import base64
import contextlib
import datetime as dt
import io
import unittest
from unittest.mock import patch

import collect


TODAY = dt.date(2026, 10, 20)
FILEE_DESCRIPTION = (
    'Free, open-source file converter. Convert 244+ formats offline by drag & drop — '
    'images, PDF, Word, Excel, PowerPoint, HWP/HWPX, video, audio, e-books and archives. '
    'No upload, no Office needed.'
)


def project(name='sample/tool', description='A screenshot tool'):
    return {'full_name': name, 'html_url': 'https://github.com/' + name,
            'description': description, 'topics': [], 'stargazers_count': 100,
            'created_at': '2025-01-01T00:00:00Z', 'pushed_at': '2026-10-20T00:00:00Z',
            'language': None, 'delta_1d': None, 'delta_7d': None,
            'category_zh': '其他开源', 'discovery_score': 0, 'summary_zh': None,
            'difficulty_zh': '⚪ 安装方式未确认', 'readme_checked': False}


def cachedSummary(description='A screenshot tool', checkedAt='2026-10-20', checked=True):
    return {'mode': 'free-v311', 'source_description': description,
            'checked_at': checkedAt, 'zh': '旧的有效简介',
            'difficulty': '⚪ 安装方式未确认', 'readme_checked': checked}


class BriefTests(unittest.TestCase):
    def testFileePurposeComesFromItsDescriptionRatherThanScreenshots(self):
        value = project('KnifeLemon/Filee', FILEE_DESCRIPTION)
        readme = '# Filee\n\n## Screenshots\nA screenshot tool on Windows.\n'
        brief = collect.makeBrief(value, readme)
        self.assertIn('文件格式转换', brief)
        self.assertNotIn('截图工具', brief)

    def testGitAiPurposeIsGitForAgentsRatherThanIntegratedLocalModels(self):
        value = project('feder-cr/git-ai', 'Git designed for AI agents.')
        readme = '# git-ai\n\n## Integrations\nRun local LLM models with this integration.\n'
        brief = collect.makeBrief(value, readme)
        self.assertIn('Git', brief)
        self.assertIn('AI 智能体', brief)
        self.assertNotIn('本地大模型', brief)

    def testCraftLauncherIsAnAppLauncherRatherThanScreenshotSoftware(self):
        value = project('storytold/craft-launcher', 'The Craft App Launcher')
        brief = collect.makeBrief(value, '# Craft\n\n## Screenshots\nScreenshot tool demo.\n')
        self.assertIn('应用启动器', brief)
        self.assertNotIn('截图工具', brief)

    def testExplicitChineseDescriptionIsPreserved(self):
        description = '将多种文件格式相互转换的桌面工具。'
        brief = collect.makeBrief(project(description=description), 'A screenshot tool.')
        self.assertIn(description, brief)
        self.assertNotIn('截图工具', brief)

    def testReadmeCoreIntroductionCanSupplyMissingPurpose(self):
        readme = '# Filee\n\n[![Screenshot](https://badges.example/screenshot)](https://example.org)\n\n'
        readme += '## Overview\n\nAn offline file converter.\n\n## Screenshots\nA screenshot tool.\n'
        brief = collect.makeBrief(project(description=''), readme)
        self.assertIn('文件格式转换', brief)
        self.assertNotIn('截图工具', brief)

    def testSecondarySectionsDoNotInventTheProjectsPurpose(self):
        for heading in ['Screenshots', 'Examples', 'Integrations', 'Demo', '截图', '示例', '集成']:
            with self.subTest(heading=heading):
                brief = collect.makeBrief(project(description='A new project.'),
                                          '# Project\n\n## ' + heading + '\nA screenshot tool.\n')
                self.assertIn('资料不足', brief)

    def testImageAltTextBadgesAndCodeAreNotPurposeEvidence(self):
        readme = '# Project\n\n![A screenshot tool](shot.png)\n\n'
        readme += '```text\nA screenshot tool\n```\n\n## Examples\nA screenshot tool.\n'
        self.assertIn('资料不足', collect.makeBrief(project(description=''), readme))

    def testGenericLanguageModelsDoNotImplyLocalExecution(self):
        descriptions = ['A benchmark for evaluating large language models.',
                        'Run LLM queries through a cloud API.']
        for description in descriptions:
            with self.subTest(description=description):
                self.assertNotIn('本地', collect.makeBrief(project(description=description), ''))

    def testExplicitLocalModelEvidenceKeepsTheLocalPurpose(self):
        for description in ['Run local LLMs on-device.', 'An offline language model runner.']:
            with self.subTest(description=description):
                self.assertIn('本地大模型', collect.makeBrief(project(description=description), ''))

    def testDistributedTaskSchedulerDoesNotImplyPersonalCalendar(self):
        brief = collect.makeBrief(project(description='A task scheduler for distributed computing.'), '')
        self.assertNotIn('日历', brief)
        self.assertNotIn('日程', brief)

    def testExplicitCalendarAndAppointmentEvidenceCanDescribeScheduling(self):
        for description in ['A calendar app.', 'An appointment scheduling tool.', 'A meeting scheduler.']:
            with self.subTest(description=description):
                self.assertIn('日历或日程', collect.makeBrief(project(description=description), ''))

    def testScreenshotPurposeAtStartOfReadmeIsNotASectionHeading(self):
        brief = collect.makeBrief(project(description=''), '# Capture\n\nScreenshot tool for Windows.\n')
        self.assertIn('截图工具', brief)

    def testStandaloneScreenshotSectionTitleIsStillExcluded(self):
        brief = collect.makeBrief(project(description=''), '# Capture\n\nScreenshots\nA screenshot tool.\n')
        self.assertIn('资料不足', brief)


class CategoryTests(unittest.TestCase):
    def testDragAndStorageDoNotCountAsRagOrAi(self):
        for description in ['Hold Alt, drag, and ping anywhere.', 'Unlimited storage for files.']:
            with self.subTest(description=description):
                self.assertNotEqual('AI 应用', collect.classify(project(description=description)))

    def testBoundedAiTermsAndHyphenatedTopicsStillCount(self):
        for description in ['An AI tool.', 'RAG search.', 'An MCP server.', 'Run an LLM.', 'AI-agent tools.']:
            with self.subTest(description=description):
                self.assertEqual('AI 应用', collect.classify(project(description=description)))

    def testOrdinaryLauncherBelongsToSystemTools(self):
        self.assertEqual('系统工具', collect.classify(
            project('storytold/craft-launcher', 'The Craft App Launcher')))

    def testTvAndAdblockRemainInTheirExistingCategory(self):
        for description in ['An Android TV launcher.', 'A TV launcher.', 'An adblock tool.', '广告拦截工具']:
            with self.subTest(description=description):
                self.assertEqual('影音去广告', collect.classify(project(description=description)))


class SummaryCacheTests(unittest.TestCase):
    def enrich(self, items, summaries, error=None):
        payload = {'content': base64.b64encode(b'A screenshot tool.').decode()}
        warnings = []
        with patch.object(collect, 'api', side_effect=error, return_value=payload) as requests:
            with patch('time.sleep'):
                collect.enrichProjects(items, summaries, TODAY, None, warnings)
        return requests.call_count, warnings

    def testFreshEntriesDoNotConsumeTheFortyReadmeBudget(self):
        items = [project(f'sample/tool-{index}') for index in range(100)]
        summaries = {item['full_name']: cachedSummary() for item in items[:40]}
        requests, warnings = self.enrich(items, summaries)
        self.assertEqual(40, requests)
        self.assertIn('sample/tool-79', summaries)
        self.assertNotIn('sample/tool-80', summaries)
        self.assertEqual([], warnings)

    def testUncheckedProjectsPrecedeExpiredHighRankedCaches(self):
        items = [project('sample/high'), project('sample/uncovered')]
        summaries = {'sample/high': cachedSummary(checkedAt='2026-10-01')}
        with patch.object(collect, 'MAX_READMES', 1):
            self.enrich(items, summaries)
        self.assertIn('sample/uncovered', summaries)
        self.assertEqual('2026-10-01', summaries['sample/high']['checked_at'])

    def testOlderExpiredChecksPrecedeNewerChecksWithinTheSameGroup(self):
        items = [project('sample/newer'), project('sample/older')]
        summaries = {'sample/newer': cachedSummary(checkedAt='2026-10-05'),
                     'sample/older': cachedSummary(checkedAt='2026-10-01')}
        with patch.object(collect, 'MAX_READMES', 1):
            self.enrich(items, summaries)
        self.assertEqual('2026-10-20', summaries['sample/older']['checked_at'])
        self.assertEqual('2026-10-05', summaries['sample/newer']['checked_at'])

    def testSuccessfulReadmeStaysCachedForFourteenDays(self):
        summaries = {'sample/tool': cachedSummary(checkedAt='2026-10-07')}
        requests, _ = self.enrich([project()], summaries)
        self.assertEqual(0, requests)
        summaries['sample/tool']['checked_at'] = '2026-10-06'
        requests, _ = self.enrich([project()], summaries)
        self.assertEqual(1, requests)
        self.assertTrue(summaries['sample/tool']['readme_checked'])

    def testFailedReadmeIsRetriedOnTheFollowingDay(self):
        summaries = {'sample/tool': cachedSummary(checked=False)}
        self.assertEqual(0, self.enrich([project()], summaries)[0])
        summaries['sample/tool']['checked_at'] = '2026-10-19'
        self.assertEqual(1, self.enrich([project()], summaries)[0])
        self.assertTrue(summaries['sample/tool']['readme_checked'])

    def testDescriptionChangeRefreshesAnOtherwiseFreshCache(self):
        summaries = {'sample/tool': cachedSummary(description='Old project purpose.')}
        self.assertEqual(1, self.enrich([project()], summaries)[0])
        self.assertEqual('A screenshot tool', summaries['sample/tool'].get('source_description'))

    def testMalformedOrFutureCacheDatesAreRefreshedWithoutAborting(self):
        for date in ['broken', '2026-99-99', None, '2026-10-21']:
            with self.subTest(date=date):
                summaries = {'sample/tool': cachedSummary(checkedAt=date)}
                self.assertEqual(1, self.enrich([project()], summaries)[0])
                self.assertEqual('2026-10-20', summaries['sample/tool']['checked_at'])

    def testReadmeFailureCachesOnlyConservativeDescriptionEvidence(self):
        value = project('KnifeLemon/Filee', FILEE_DESCRIPTION)
        summaries = {}
        requests, warnings = self.enrich([value], summaries, TimeoutError('temporary failure'))
        self.assertEqual(1, requests)
        self.assertEqual(1, len(warnings))
        self.assertFalse(summaries[value['full_name']]['readme_checked'])
        self.assertIn('文件格式转换', summaries[value['full_name']]['zh'])
        self.assertEqual('free-v311', summaries[value['full_name']]['mode'])

    def testOldModeIsNotDisplayedWhileWaitingForReadmeCoverage(self):
        value = project('KnifeLemon/Filee', FILEE_DESCRIPTION)
        summaries = {value['full_name']: {'mode': 'free-v31', 'zh': '截图工具',
                                        'difficulty': '🟢 开箱即用', 'readme_checked': True}}
        collect.attachSummaries([value], summaries)
        self.assertIn('文件格式转换', value['summary_zh'])
        self.assertNotIn('截图工具', value['summary_zh'])
        self.assertFalse(value['readme_checked'])
        self.assertEqual('⚪ 安装方式未确认', value['difficulty_zh'])

    def testChangedDescriptionDoesNotDisplayOldPurpose(self):
        value = project(description='An offline file converter.')
        collect.attachSummaries([value], {'sample/tool': cachedSummary()})
        self.assertIsNotNone(value['summary_zh'])
        self.assertIn('文件格式转换', value['summary_zh'])
        self.assertNotIn('旧的有效简介', value['summary_zh'])

    def testFailedRepositoryRefreshCannotKeepAnOldMisleadingSummary(self):
        value = project('sample/old', FILEE_DESCRIPTION)
        value['summary_zh'] = '截图工具'
        history = {'sample/old': {'2026-10-19': 100}}
        summaries = {'sample/old': {'mode': 'free-v31', 'zh': '截图工具'}}
        fresh = project('sample/new', 'A screenshot tool')
        captured = {}

        def capture(dataDir, savedHistory, savedSummaries, document):
            captured.update(document)

        with patch.object(collect, 'loadState', return_value=([value], history, summaries)):
            with patch.object(collect, 'discover', return_value={'sample/new': fresh}):
                with patch.object(collect, 'api', side_effect=TimeoutError('temporary failure')):
                    with patch.object(collect, 'saveSnapshots', side_effect=capture), patch('time.sleep'):
                        with contextlib.redirect_stdout(io.StringIO()):
                            collect.main()
        retained = next(item for item in captured['projects'] if item['full_name'] == 'sample/old')
        self.assertIn('文件格式转换', retained['summary_zh'])
        self.assertNotIn('截图工具', retained['summary_zh'])
        self.assertFalse(retained['readme_checked'])
        self.assertEqual({'2026-10-19': 100}, history['sample/old'])


if __name__ == '__main__':
    unittest.main()
