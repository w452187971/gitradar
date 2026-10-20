import base64
import contextlib
import datetime as dt
import io
import json
import os
import pathlib
import runpy
import shutil
import tempfile
import unittest
from unittest.mock import patch


SOURCE = pathlib.Path(__file__).resolve().parents[1] / 'collect.py'
TODAY = dt.datetime.now(dt.timezone.utc).date()


def repository(name='sample/fresh', stars=160):
    return {
        'full_name': name, 'html_url': 'https://github.com/' + name,
        'description': 'A useful desktop tool', 'stargazers_count': stars,
        'language': 'Python', 'topics': [], 'fork': False, 'archived': False,
        'created_at': '2025-01-01T00:00:00Z',
        'pushed_at': str(TODAY) + 'T00:00:00Z',
    }


def previousProject(name='sample/old'):
    value = repository(name, 100)
    value.update(delta_1d=12, delta_7d=40, category_zh='系统工具',
                 discovery_score=100, summary_zh=None)
    return value


class CollectorTests(unittest.TestCase):
    def setUp(self):
        self.workspace = tempfile.TemporaryDirectory()
        self.addCleanup(self.workspace.cleanup)
        self.root = pathlib.Path(self.workspace.name)
        self.script = self.root / 'collect.py'
        shutil.copyfile(SOURCE, self.script)
        self.data = self.root / 'data'
        self.data.mkdir()
        self.writeData('history.json', {})
        self.writeData('projects.json', {'projects': []})
        self.writeData('summaries.json', {})
        self.fresh = [repository()]
        self.refreshFails = False
        self.searchFails = False
        self.refreshResult = repository('sample/old', 120)

    def writeData(self, name, value):
        (self.data / name).write_text(json.dumps(value), encoding='utf-8')

    def readData(self, name):
        return json.loads((self.data / name).read_text(encoding='utf-8'))

    def snapshotFiles(self):
        return {p.name: p.read_bytes() for p in self.data.glob('*.json')}

    def fakeUrlopen(self, request, **kwargs):
        url = request.full_url
        if not url.startswith('https://api.github.com/'):
            raise AssertionError('Unexpected external request: ' + url)
        if '/search/repositories?' in url:
            if self.searchFails:
                raise TimeoutError('search temporarily unavailable')
            payload = {'items': self.fresh}
        elif url.endswith('/readme'):
            payload = {'content': base64.b64encode(b'Download the release.dmg').decode()}
        elif self.refreshFails:
            raise TimeoutError('repository temporarily unavailable')
        else:
            payload = self.refreshResult
        return io.BytesIO(json.dumps(payload).encode())

    def runCollector(self):
        with patch('urllib.request.urlopen', self.fakeUrlopen), patch('time.sleep'):
            with patch.dict(os.environ, {'OPENAI_API_KEY': 'must-not-be-used'}, clear=True):
                with contextlib.redirect_stdout(io.StringIO()):
                    runpy.run_path(str(self.script), run_name='legacy_regression')['legacyMain']()
        return self.readData('projects.json')

    def testCorruptHistoryAbortsWithoutChangingAnySnapshot(self):
        (self.data / 'history.json').write_text('{broken', encoding='utf-8')
        before = self.snapshotFiles()
        with self.assertRaises(ValueError):
            self.runCollector()
        self.assertEqual(before, self.snapshotFiles())

    def testMissingHistoryWithTrackedProjectsAborts(self):
        self.writeData('projects.json', {'projects': [previousProject()]})
        (self.data / 'history.json').unlink()
        before = self.snapshotFiles()
        with self.assertRaises(ValueError):
            self.runCollector()
        self.assertEqual(before, self.snapshotFiles())

    def testInvalidHistoryStructureAbortsBeforeWriting(self):
        self.writeData('history.json', {'sample/fresh': {str(TODAY): -1}})
        before = self.snapshotFiles()
        with self.assertRaises(ValueError):
            self.runCollector()
        self.assertEqual(before, self.snapshotFiles())

    def testMissingDailyBaselineDoesNotUseFiveDayGrowth(self):
        self.writeData('history.json', {'sample/fresh': {
            str(TODAY - dt.timedelta(days=5)): 100}})
        project = self.runCollector()['projects'][0]
        self.assertIsNone(project['delta_1d'])

    def testMissingWeeklyBaselineDoesNotUseNineteenDayGrowth(self):
        self.writeData('history.json', {'sample/fresh': {
            str(TODAY - dt.timedelta(days=19)): 100}})
        project = self.runCollector()['projects'][0]
        self.assertIsNone(project['delta_7d'])

    def testExactBaselinesPreserveNegativeNetChange(self):
        self.writeData('history.json', {'sample/fresh': {
            str(TODAY - dt.timedelta(days=1)): 220,
            str(TODAY - dt.timedelta(days=7)): 200}})
        project = self.runCollector()['projects'][0]
        self.assertEqual(-60, project['delta_1d'])
        self.assertEqual(-40, project['delta_7d'])

    def testOldSnapshotsAreRetained(self):
        oldDate = str(TODAY - dt.timedelta(days=90))
        self.writeData('history.json', {'sample/fresh': {oldDate: 10}})
        self.runCollector()
        self.assertIn(oldDate, self.readData('history.json')['sample/fresh'])
        self.assertEqual(10, self.readData('history.json')['sample/fresh'][oldDate])

    def testFailedRefreshKeepsProjectWithoutInventingSnapshot(self):
        yesterday = str(TODAY - dt.timedelta(days=1))
        self.writeData('projects.json', {'projects': [previousProject()]})
        self.writeData('history.json', {'sample/old': {yesterday: 100}})
        self.refreshFails = True
        document = self.runCollector()
        projects = {p['full_name']: p for p in document['projects']}
        self.assertIn('sample/old', projects)
        self.assertIsNone(projects['sample/old']['delta_1d'])
        self.assertIsNone(projects['sample/old']['delta_7d'])
        self.assertEqual({yesterday: 100}, self.readData('history.json')['sample/old'])
        self.assertTrue(any('sample/old' in warning for warning in document['warnings']))

    def testTotalFailurePreservesAllFiles(self):
        self.writeData('projects.json', {'projects': [previousProject()]})
        self.writeData('history.json', {'sample/old': {str(TODAY): 100}})
        self.searchFails = self.refreshFails = True
        before = self.snapshotFiles()
        with self.assertRaises(RuntimeError):
            self.runCollector()
        self.assertEqual(before, self.snapshotFiles())

    def testDiscoveryCaseChangeKeepsOneProjectAndItsHistory(self):
        yesterday = str(TODAY - dt.timedelta(days=1))
        self.writeData('projects.json', {'projects': [previousProject()]})
        self.writeData('history.json', {'sample/old': {yesterday: 100}})
        self.fresh = [repository('Sample/Old', 160)]
        document = self.runCollector()
        self.assertEqual(1, document['count'])
        self.assertEqual('sample/old', document['projects'][0]['full_name'])
        self.assertEqual(60, document['projects'][0]['delta_1d'])
        self.assertEqual({'sample/old'}, set(self.readData('history.json')))

    def testRefreshCaseChangeUsesExistingHistoryKey(self):
        yesterday = str(TODAY - dt.timedelta(days=1))
        self.writeData('projects.json', {'projects': [previousProject()]})
        self.writeData('history.json', {'sample/old': {yesterday: 100}})
        self.refreshResult = repository('Sample/Old', 120)
        projects = {p['full_name']: p for p in self.runCollector()['projects']}
        self.assertIn('sample/old', projects)
        self.assertEqual(20, projects['sample/old']['delta_1d'])
        self.assertNotIn('Sample/Old', self.readData('history.json'))

    def testCrossingUtcMidnightAbortsWithoutWritingWrongDate(self):
        class CrossingMidnight(dt.datetime):
            calls = 0

            @classmethod
            def now(cls, tz=None):
                date = TODAY if cls.calls == 0 else TODAY + dt.timedelta(days=1)
                cls.calls += 1
                return cls.combine(date, dt.time(0), tzinfo=dt.timezone.utc)

        before = self.snapshotFiles()
        with patch('datetime.datetime', CrossingMidnight):
            with self.assertRaises(RuntimeError):
                self.runCollector()
        self.assertEqual(before, self.snapshotFiles())

    def testFailedAtomicReplacePreservesOriginalFiles(self):
        before = self.snapshotFiles()
        with patch('os.replace', side_effect=OSError('disk unavailable')):
            with self.assertRaises(OSError):
                self.runCollector()
        self.assertEqual(before, self.snapshotFiles())

    def testRepeatedDailyRunKeepsOlderDatesAndRefreshesToday(self):
        yesterday = str(TODAY - dt.timedelta(days=1))
        self.writeData('history.json', {'sample/fresh': {yesterday: 100}})
        self.runCollector()
        self.fresh = [repository(stars=170)]
        project = self.runCollector()['projects'][0]
        self.assertEqual(70, project['delta_1d'])
        self.assertEqual({yesterday: 100, str(TODAY): 170},
                         self.readData('history.json')['sample/fresh'])


if __name__ == '__main__':
    unittest.main()
