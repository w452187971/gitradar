"""14B 容量对照只测封装与隔离，不下载或执行权重。"""
import hashlib
import json
import os
from pathlib import Path
import tempfile
from unittest.mock import patch
import unittest

from scripts import probe_model_comparison as comparison


class ModelComparisonTests(unittest.TestCase):
    def test_tampered_baseline_source_is_rejected_before_loading(self):
        original = comparison.gitBytes
        with patch.object(comparison, 'gitBytes', side_effect=lambda path: b'altered' if path == comparison.SOURCE else original(path)):
            with self.assertRaisesRegex(ValueError, 'source'):
                comparison.verifiedInputs({})

    def test_fixture_is_byte_identical_and_runtime_only_comes_from_baseline(self):
        source, fixture, pins = comparison.verifiedInputs({})
        self.assertEqual(hashlib.sha256(source).hexdigest(), comparison.SOURCE_SHA256)
        self.assertEqual(fixture, (comparison.ROOT / comparison.FIXTURE).read_bytes())
        baseline = json.loads(comparison.gitBytes(comparison.PINS))
        current = json.loads(pins)
        self.assertEqual(current['runtime'], baseline['runtime'])
        self.assertEqual(current['model']['size'], 9001752960)
        self.assertEqual(current['model']['sha256'], '500a8806e85ee9c83f3ae08420295592451379b4f8cf2d0f41c15dffeb6b81f0')

    def test_changed_current_fixture_is_rejected(self):
        blobs = {path: comparison.gitBytes(path) for path in [comparison.SOURCE, comparison.FIXTURE, comparison.PINS]}
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / comparison.FIXTURE
            path.parent.mkdir(parents=True)
            path.write_bytes(b'changed fixture')
            with patch.object(comparison, 'ROOT', root), patch.object(comparison, 'gitBytes', side_effect=blobs.__getitem__):
                with self.assertRaisesRegex(ValueError, 'fixture'):
                    comparison.verifiedInputs({})

    def test_local_execution_refuses_before_download_and_preserves_provenance(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch.dict(os.environ, {'GITHUB_ACTIONS': 'false', 'GITHUB_SHA': 'event-sha-is-not-checkout'}):
                with patch('urllib.request.urlopen') as request:
                    code = comparison.runComparison(Path(directory))
            report = json.loads((Path(directory) / 'report.json').read_text())
            provenance = json.loads((Path(directory) / 'comparison-provenance.json').read_text())
        self.assertEqual(code, 1)
        self.assertEqual(report['status'], 'failed_unverified')
        self.assertEqual(provenance['baseline_commit'], comparison.BASELINE)
        self.assertEqual(provenance['event_github_sha'], 'event-sha-is-not-checkout')
        actualHead = comparison.subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=comparison.ROOT,
                                              capture_output=True, check=True, timeout=20).stdout.decode().strip()
        self.assertEqual(provenance['checkout_head'], actualHead)
        request.assert_not_called()

    def test_disk_shortage_fails_before_baseline_main(self):
        _, _, pins = comparison.verifiedInputs({})
        with patch.object(comparison.shutil, 'disk_usage', return_value=type('Disk', (), {'free': 1})()):
            with self.assertRaisesRegex(RuntimeError, 'space'):
                comparison.requireSpace(json.loads(pins))

    def test_harness_is_ephemeral_and_does_not_modify_v4_or_data(self):
        source, fixture, pins = comparison.verifiedInputs({})
        module = comparison.loadBaseline(source)
        before = {path: (comparison.ROOT / path).read_bytes() for path in [comparison.SOURCE, 'scripts/model_probe_pins.json']}
        harness = []
        def fakeMain():
            harness.append(module.ROOT)
            self.assertEqual((module.ROOT / comparison.FIXTURE).read_bytes(), fixture)
            self.assertEqual((module.ROOT / comparison.PINS).read_bytes(), pins)
            self.assertFalse((module.ROOT / 'data').exists())
            return 1
        with tempfile.TemporaryDirectory() as directory:
            with patch.object(comparison, 'loadBaseline', return_value=module), patch.object(module, 'requirePublicRunner'):
                with patch.object(module, 'main', side_effect=fakeMain), patch.object(comparison, 'requireSpace'):
                    self.assertEqual(comparison.runComparison(Path(directory)), 1)
            provenance = json.loads((Path(directory) / 'comparison-provenance.json').read_text())
        self.assertFalse(harness[0].exists())
        self.assertEqual(provenance['harness_fixture_sha256'], hashlib.sha256(fixture).hexdigest())
        self.assertEqual(provenance['harness_pins_sha256'], hashlib.sha256(pins).hexdigest())
        for path, body in before.items():
            self.assertEqual((comparison.ROOT / path).read_bytes(), body)

    def test_workflow_is_manual_read_only_and_never_collects_or_promotes(self):
        text = (comparison.ROOT / '.github/workflows/model-comparison.yml').read_text()
        for required in ['workflow_dispatch:', 'contents: read', 'persist-credentials: false', 'fetch-depth: 0',
                         'timeout-minutes: 17', '900s', 'comparison-provenance.json', 'model_probe_only != true', 'probe_only == true']:
            self.assertIn(required, text)
        for forbidden in ['schedule:', 'collect.py', 'git push', 'secrets.', '.v4-output']:
            self.assertNotIn(forbidden, text)


if __name__ == '__main__':
    unittest.main()
