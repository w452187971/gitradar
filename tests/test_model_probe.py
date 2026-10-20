"""隔离模型诊断的离线安全边界，不下载或运行模型。"""
import copy
import hashlib
import json
from pathlib import Path
import tempfile
import subprocess
import sys
from unittest.mock import patch
import unittest

from scripts.probe_local_model import FIELDS, checkOutput, downloadVerified, loadCases, parseOutput, ProbeDeadlineExceeded, requestPayload, runCase, serverCommand, timeoutHandler


class ModelProbeTests(unittest.TestCase):
    def setUp(self):
        self.case = {'refs': [{'ref_id': 'r1', 'source_quote': 'does not block YouTube ads'}]}
        self.output = {name: {'value': None, 'source_quote': None, 'ref_id': None} for name in FIELDS}
        self.output['unknowns'] = list(FIELDS)

    def test_quotes_only_match_the_referenced_document(self):
        self.output['purpose'] = {'value': '屏蔽广告', 'source_quote': 'block YouTube ads', 'ref_id': 'other'}
        self.output['unknowns'].remove('purpose')
        self.assertFalse(checkOutput(self.output, self.case)['quotes_match'])
        self.output['purpose']['ref_id'] = 'r1'
        result = checkOutput(self.output, self.case)
        self.assertTrue(result['quotes_match'])
        self.assertEqual(result['semantic_status'], 'human_review_required')

    def test_unknown_requires_null_evidence_and_exact_unknown_list(self):
        self.assertTrue(checkOutput(self.output, self.case)['schema_valid'])
        self.output['purpose']['source_quote'] = 'does not block YouTube ads'
        self.assertFalse(checkOutput(self.output, self.case)['schema_valid'])
        self.output['purpose']['source_quote'] = None
        self.output['unknowns'].pop()
        self.assertFalse(checkOutput(self.output, self.case)['schema_valid'])

    def test_json_must_be_a_single_object_without_fences_or_duplicate_keys(self):
        for raw in ['```json\n{}\n```', '[]', '{} prose', '{"purpose":1,"purpose":2}', '{"purpose":NaN}']:
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                parseOutput(raw)

    def test_no_source_control_counts_refusal_without_semantic_promotion(self):
        case = {'refs': [], 'controls': ['all_fields_unknown']}
        self.assertEqual(checkOutput(self.output, case)['unknown_control'], {'passed': 8, 'total': 8})
        self.output['purpose'] = {'value': '压缩图片', 'source_quote': 'image', 'ref_id': 'r1'}
        self.output['unknowns'].remove('purpose')
        result = checkOutput(self.output, case)
        self.assertEqual(result['unknown_control']['passed'], 7)
        self.assertFalse(result['quotes_match'])

    def test_hash_mismatch_never_promotes_download(self):
        from unittest.mock import patch
        import io
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / 'model.gguf'
            with patch('scripts.probe_local_model.urllib.request.urlopen', return_value=io.BytesIO(b'bad')):
                with self.assertRaises(ValueError):
                    downloadVerified({'url': 'https://example.com/a', 'sha256': hashlib.sha256(b'good').hexdigest(), 'size': 3}, target)
            self.assertFalse(target.exists())
            self.assertFalse(target.with_suffix('.part').exists())

    def test_deadline_is_not_caught_as_a_single_request_failure(self):
        with patch('scripts.probe_local_model.localJson', side_effect=ProbeDeadlineExceeded):
            with tempfile.TemporaryDirectory() as directory, self.assertRaises(ProbeDeadlineExceeded):
                runCase({'full_name': 'test/public', 'kind': 'cli', 'refs': []}, 12345, Path(directory), 1)
        with self.assertRaises(ProbeDeadlineExceeded):
            timeoutHandler(14, None)

    def test_oversized_context_is_reported_without_inference(self):
        responses = [{'prompt': 'long'}, {'tokens': [1] * 3500}]
        with patch('scripts.probe_local_model.localJson', side_effect=responses) as local:
            with tempfile.TemporaryDirectory() as directory:
                result = runCase({'full_name': 'test/public', 'kind': 'cli', 'refs': []}, 12345, Path(directory), 1)
        self.assertEqual(local.call_count, 2)
        self.assertFalse(result['token_budget']['fits'])
        self.assertEqual(result['status'], 'failed')

    def test_local_execution_fails_before_any_download_and_preserves_report(self):
        with tempfile.TemporaryDirectory() as directory:
            process = subprocess.run([sys.executable, 'scripts/probe_local_model.py', '--output-dir', directory],
                                     capture_output=True, text=True)
            self.assertEqual(process.returncode, 1)
            report = json.loads((Path(directory) / 'report.json').read_text())
        self.assertEqual(report['status'], 'failed_unverified')
        self.assertNotIn('downloads', report)
        self.assertEqual(report['metrics']['attempted'], 0)

    def test_inference_limits_and_loopback_are_fixed(self):
        command = serverCommand(Path('/tmp/bin'), Path('/tmp/model'), 12345)
        for key, value in [('--host', '127.0.0.1'), ('-ngl', '0'), ('-t', '4'), ('-tb', '4'), ('-c', '4096')]:
            self.assertEqual(command[command.index(key) + 1], value)
        payload = requestPayload({'full_name': 'test/public', 'refs': []})
        self.assertEqual(payload['max_tokens'], 700)
        self.assertEqual(payload['temperature'], 0)
        self.assertFalse(payload['chat_template_kwargs']['enable_thinking'])

    def test_model_mode_guards_all_production_and_other_probe_steps(self):
        workflow = Path('.github/workflows/update.yml').read_text()
        steps = workflow.split('      - name: ')
        for name in ['Test collector', 'Test frontend', 'Collect and validate isolated batch',
                     'Promote verified batch', 'Commit verified snapshots and pages',
                     'Preserve complete failed batch and diagnostics', 'Probe built-in token batch access']:
            step = next(step for step in steps if step.startswith(name + '\n'))
            self.assertIn('inputs.model_probe_only != true', step)
        self.assertIn('model_probe_only:\n', workflow)
        self.assertIn('probe_only == true && inputs.model_probe_only == true', workflow)

    def test_fixtures_are_six_public_development_cases_with_frozen_hashes(self):
        cases = loadCases(Path('tests/fixtures/model_probe/cases.json'))
        self.assertEqual(len(cases), 6)
        self.assertEqual(len({case['kind'] for case in cases}), 6)
        changed = copy.deepcopy(cases[0])
        changed['refs'][0]['source_quote'] += 'changed'
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'cases.json'
            path.write_text(json.dumps({'cases': [changed, *cases[1:]]}))
            with self.assertRaisesRegex(ValueError, 'hash'):
                loadCases(path)


if __name__ == '__main__':
    unittest.main()
