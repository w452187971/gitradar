"""容量对照只测封装与隔离，不下载或执行权重。"""
import hashlib
import json
import os
from pathlib import Path
import tempfile
from unittest.mock import patch
import unittest

from scripts import probe_model_comparison as comparison


class ModelComparisonTests(unittest.TestCase):
    def test_default_14b_matches_explicit_choice(self):
        self.assertEqual(comparison.verifiedInputs({}), comparison.verifiedInputs({}, '14b'))

    def test_8b_changes_only_model_and_keeps_exact_baseline_inputs(self):
        source, fixture, pins = comparison.verifiedInputs({}, '8b')
        defaultSource, defaultFixture, defaultPins = comparison.verifiedInputs({})
        self.assertEqual((source, fixture), (defaultSource, defaultFixture))
        current, previous = json.loads(pins), json.loads(defaultPins)
        self.assertEqual(current['runtime'], previous['runtime'])
        self.assertEqual(current['model']['size'], 5027783488)
        self.assertEqual(current['model']['revision'], '7c41481f57cb95916b40956ab2f0b139b296d974')
        self.assertEqual(current['model']['sha256'], 'd98cdcbd03e17ce47681435b5150e34c1417f50b5c0019dd560e4882c5745785')
        self.assertEqual(len(current['model']['sha256']), 64)
        current.pop('model')
        previous.pop('model')
        self.assertEqual(current, previous)

    def test_8b_pin_tampering_is_rejected(self):
        blobs = {path: comparison.gitBytes(path) for path in [comparison.SOURCE, comparison.FIXTURE, comparison.PINS]}
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fixture = root / comparison.FIXTURE
            fixture.parent.mkdir(parents=True)
            fixture.write_bytes(blobs[comparison.FIXTURE])
            pins = root / 'scripts/model_comparison_8b.json'
            pins.parent.mkdir(parents=True)
            pins.write_text('{}')
            with patch.object(comparison, 'ROOT', root), patch.object(comparison, 'gitBytes', side_effect=blobs.__getitem__):
                with self.assertRaisesRegex(ValueError, 'pins SHA256'):
                    comparison.verifiedInputs({}, '8b')

    def test_unsupported_model_key_is_rejected_before_loading_or_network(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch.object(comparison, 'loadBaseline') as load, patch('urllib.request.urlopen') as request:
                self.assertEqual(comparison.runComparison(Path(directory), '32b'), 1)
            report = json.loads((Path(directory) / 'report.json').read_text())
        self.assertIn('Unsupported comparison modelKey', report['error'])
        load.assert_not_called()
        request.assert_not_called()

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

    def test_8b_workflow_only_changes_model_selection_and_artifact_identity(self):
        original = (comparison.ROOT / '.github/workflows/model-comparison.yml').read_text()
        expected = original.replace('14B', '8B').replace('model-14b-', 'model-8b-')
        expected = expected.replace('python3 scripts/probe_model_comparison.py\n',
                                    'python3 scripts/probe_model_comparison.py --model-key 8b\n')
        actual = (comparison.ROOT / '.github/workflows/model-comparison-8b.yml').read_text()
        self.assertEqual(actual, expected)


if __name__ == '__main__':
    unittest.main()
