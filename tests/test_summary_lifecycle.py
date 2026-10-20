import base64
import datetime as dt
import unittest
from unittest.mock import patch

import collect


TODAY = dt.date(2026, 10, 20)


def project():
    return {'full_name': 'sample/tool', 'description': 'A useful helper.', 'topics': []}


def success(checkedAt='2026-10-01'):
    return {'mode': 'free-v311', 'source_description': 'A useful helper.',
            'checked_at': checkedAt, 'readme_checked': True,
            'zh': '【关键词提取】原有文件管理用途。', 'difficulty': '🟡 可能需要命令行安装'}


class SummaryLifecycleTests(unittest.TestCase):
    def attach(self, cache):
        value = project()
        collect.attachSummaries([value], {'sample/tool': cache}, TODAY)
        return value

    def enrich(self, summaries, today=TODAY, error=None):
        payload = {'content': base64.b64encode(b'A file manager.').decode()}
        with patch.object(collect, 'api', side_effect=error, return_value=payload) as requests:
            with patch('time.sleep'):
                collect.enrichProjects([project()], summaries, today, None, [])
        return requests.call_count

    def testExpiredSuccessStaysVisibleWithOriginalEvidenceDate(self):
        value = self.attach(success())
        self.assertEqual('【关键词提取】原有文件管理用途。', value['summary_zh'])
        self.assertTrue(value['readme_checked'])
        self.assertTrue(value.get('readme_stale'))
        self.assertEqual('2026-10-01', value.get('readme_checked_at'))

    def testFreshSuccessIsDatedWithoutBeingMarkedStale(self):
        value = self.attach(success('2026-10-19'))
        self.assertFalse(value.get('readme_stale', True))
        self.assertEqual('2026-10-19', value.get('readme_checked_at'))

    def testModeDescriptionAndFutureDatesStillInvalidateOldEvidence(self):
        for changes in [{'mode': 'free-v31'}, {'source_description': 'Different purpose.'},
                        {'checked_at': '2026-10-21'}, {'checked_at': 'broken'}]:
            with self.subTest(changes=changes):
                value = self.attach({**success(), **changes})
                self.assertNotEqual('【关键词提取】原有文件管理用途。', value['summary_zh'])
                self.assertFalse(value['readme_checked'])
                self.assertIsNone(value.get('readme_checked_at'))

    def testFailedRefreshPreservesSuccessfulEvidenceAndRecordsAttempt(self):
        summaries = {'sample/tool': success()}
        self.enrich(summaries, error=TimeoutError('temporary failure'))
        cached = summaries['sample/tool']
        self.assertTrue(cached['readme_checked'])
        self.assertEqual('2026-10-01', cached['checked_at'])
        self.assertEqual('2026-10-20', cached.get('last_attempt_at'))
        self.assertTrue(cached.get('refresh_failed'))
        self.assertTrue(self.attach(cached).get('readme_stale'))

    def testFailedAttemptIsNotRepeatedTodayButRetriesTheFollowingDay(self):
        summaries = {'sample/tool': success()}
        self.assertEqual(1, self.enrich(summaries, error=TimeoutError('temporary failure')))
        self.assertEqual(0, self.enrich(summaries))
        self.assertEqual(1, self.enrich(summaries, today=TODAY + dt.timedelta(days=1)))
        self.assertFalse(summaries['sample/tool'].get('refresh_failed', True))
        self.assertEqual('2026-10-21', summaries['sample/tool']['checked_at'])

    def testFailureWithoutOldSuccessRemainsUnknown(self):
        summaries = {}
        self.enrich(summaries, error=TimeoutError('temporary failure'))
        self.assertFalse(summaries['sample/tool']['readme_checked'])
        self.assertTrue(summaries['sample/tool'].get('refresh_failed'))
        value = self.attach(summaries['sample/tool'])
        self.assertFalse(value.get('readme_stale', True))
        self.assertIsNone(value.get('readme_checked_at'))
        self.assertIn('资料不足', value['summary_zh'])


if __name__ == '__main__':
    unittest.main()
