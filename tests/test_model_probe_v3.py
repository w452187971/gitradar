"""v3 只测隔离协议与程序绑定，不把绑定当作语义证据。"""
import copy
import hashlib
import json
from pathlib import Path
import tempfile
from unittest.mock import patch
import unittest

from scripts import probe_local_model as probe


class ModelProbeV3Tests(unittest.TestCase):
    def setUp(self):
        text = 'This DNS blocker cannot block YouTube ads.'
        self.case = {'full_name': 'test/public', 'kind': 'self_hosted', 'refs': [
            {'ref_id': 'r1', 'source_quote': text, 'sha256': hashlib.sha256(text.encode()).hexdigest()}]}
        self.raw = {name: {'value': None, 'ref_id': None} for name in probe.FIELDS}

    def test_raw_schema_only_has_value_and_current_case_reference_enum(self):
        schema = probe.responseSchema(self.case)
        self.assertEqual(set(schema['properties']), set(probe.FIELDS))
        for field in schema['properties'].values():
            self.assertEqual(set(field['properties']), {'value', 'ref_id'})
            self.assertEqual(field['properties']['ref_id']['enum'], ['r1', None])
        missing = probe.responseSchema({'refs': []})['properties']['purpose']['properties']
        self.assertEqual(missing['ref_id']['enum'], [None])
        self.assertEqual(missing['value']['type'], ['string', 'null'])

    def test_partial_null_or_foreign_reference_is_rejected_without_repair(self):
        for field in [{'value': '猜测', 'ref_id': None}, {'value': None, 'ref_id': 'r1'},
                      {'value': '猜测', 'ref_id': 'foreign'}, {'value': '', 'ref_id': 'r1'}]:
            raw = copy.deepcopy(self.raw)
            raw['purpose'] = field
            original = copy.deepcopy(raw)
            self.assertFalse(probe.checkOutput(raw, self.case)['raw_valid'])
            with self.assertRaises(ValueError):
                probe.bindOutput(raw, self.case)
            self.assertEqual(raw, original)

    def test_binding_is_exact_immutable_and_still_semantically_pending(self):
        self.raw['purpose'] = {'value': '屏蔽YouTube广告', 'ref_id': 'r1'}
        before = copy.deepcopy(self.case)
        bound = probe.bindOutput(self.raw, self.case)
        self.assertEqual(bound['purpose']['source_quote'], self.case['refs'][0]['source_quote'])
        self.assertNotIn('purpose', bound['unknowns'])
        self.assertEqual(len(bound['unknowns']), 7)
        self.assertEqual(self.case, before)
        self.assertNotIn('source_quote', self.raw['purpose'])
        self.assertEqual(probe.checkOutput(self.raw, self.case)['semantic_status'], 'human_review_required')
        changed = copy.deepcopy(self.case)
        changed['refs'][0]['source_quote'] += ' changed'
        with self.assertRaisesRegex(ValueError, 'hash'):
            probe.bindOutput(self.raw, changed)

    def modelResponses(self, raw):
        return [{'prompt': 'probe'}, {'tokens': [1] * 40}, {'choices': [{
            'message': {'content': json.dumps(raw)}, 'finish_reason': 'stop'}],
            'timings': {'prompt_ms': 1, 'predicted_ms': 2}}]

    def test_invalid_model_output_is_visible_and_never_bound_or_coerced(self):
        self.raw['purpose'] = {'value': '图片压缩', 'ref_id': None}
        with tempfile.TemporaryDirectory() as directory:
            with patch('scripts.probe_local_model.localJson', side_effect=self.modelResponses(self.raw)):
                result = probe.runCase(self.case, 12345, Path(directory), 1)
        self.assertEqual(result['raw_model_output'], self.raw)
        self.assertIsNone(result['runtime_bound_output'])
        self.assertEqual(result['status'], 'failed')
        self.assertEqual(result['binding_status'], 'rejected_invalid_raw_output')

    def test_raw_and_bound_report_are_separate_and_never_claim_quote_accuracy(self):
        self.raw['purpose'] = {'value': '屏蔽YouTube广告', 'ref_id': 'r1'}
        with tempfile.TemporaryDirectory() as directory:
            with patch('scripts.probe_local_model.localJson', side_effect=self.modelResponses(self.raw)):
                result = probe.runCase(self.case, 12345, Path(directory), 1)
        self.assertEqual(result['status'], 'raw_contract_passed_semantics_pending')
        self.assertEqual(result['raw_model_output'], self.raw)
        self.assertNotIn('source_quote', result['raw_model_output']['purpose'])
        self.assertEqual(result['runtime_bound_output']['purpose']['source_quote'], self.case['refs'][0]['source_quote'])
        self.assertEqual(result['semantic_status'], 'human_review_required')
        report = {'cases': [result] * 6, 'schema_canary': {'status': 'passed'}}
        probe.summarize(report)
        self.assertEqual(report['status'], 'runtime_complete_semantics_unverified')
        self.assertNotIn('quotes_match', report['metrics'])
        self.assertIsNone(report['metrics']['model_source_selection_accuracy'])
        self.assertIsNone(report['metrics']['semantic_accuracy'])
        self.assertEqual(report['metrics']['non_null_fields'], 6)

    def test_no_source_control_really_calls_inference_and_exposes_guessed_value(self):
        case = {'full_name': 'test/public', 'kind': 'missing', 'refs': [], 'controls': ['all_fields_unknown']}
        self.raw['purpose'] = {'value': '凭记忆压缩图片', 'ref_id': None}
        with tempfile.TemporaryDirectory() as directory:
            with patch('scripts.probe_local_model.localJson', side_effect=self.modelResponses(self.raw)) as request:
                result = probe.runCase(case, 12345, Path(directory), 1)
        self.assertEqual(request.call_count, 3)
        self.assertEqual(result['unknown_control'], {'passed': 7, 'total': 8})
        self.assertFalse(result['nullpair_valid'])
        self.assertEqual(result['raw_model_output']['purpose']['value'], '凭记忆压缩图片')

    def test_path_must_be_literal_https_url_in_the_selected_reference(self):
        self.case['refs'][0]['source_quote'] = 'Get https://example.org/install and https://example.org/releases'
        text = self.case['refs'][0]['source_quote']
        self.case['refs'][0]['sha256'] = hashlib.sha256(text.encode()).hexdigest()
        for value, valid in [('https://example.org/install', True), ('https://guessed.org/download', False),
                             ('http://example.org/install', False), ('官方发布页', False)]:
            with self.subTest(value=value):
                self.raw['path'] = {'value': value, 'ref_id': 'r1'}
                result = probe.checkOutput(self.raw, self.case)
                self.assertEqual(result['raw_valid'], valid)
                if not valid:
                    self.assertEqual(result['validation_errors']['path'], 'invalid_path_source')
                    with self.assertRaises(ValueError):
                        probe.bindOutput(self.raw, self.case)

    def test_non_chinese_value_is_retained_and_marked_for_review(self):
        self.raw['purpose'] = {'value': 'Blocks ads', 'ref_id': 'r1'}
        result = probe.checkOutput(self.raw, self.case)
        self.assertTrue(result['raw_valid'])
        self.assertIn('purpose', result['language_review_fields'])
        self.assertEqual(probe.bindOutput(self.raw, self.case)['purpose']['value'], 'Blocks ads')

    def test_path_prefix_cannot_substitute_for_the_complete_documented_url(self):
        text = '[fd releases](https://github.com/sharkdp/fd/releases).'
        self.case['refs'][0].update(source_quote=text, sha256=hashlib.sha256(text.encode()).hexdigest())
        for value in ['https://github.com', 'https://github.com/sharkdp',
                      'https://github.com/sharkdp/fd']:
            with self.subTest(value=value):
                self.raw['path'] = {'value': value, 'ref_id': 'r1'}
                self.assertFalse(probe.checkOutput(self.raw, self.case)['raw_valid'])
                with self.assertRaises(ValueError):
                    probe.bindOutput(self.raw, self.case)
        self.raw['path'] = {'value': 'https://github.com/sharkdp/fd/releases', 'ref_id': 'r1'}
        self.assertTrue(probe.checkOutput(self.raw, self.case)['raw_valid'])

    def test_frozen_fixture_hash_is_identical_to_v2(self):
        path = Path('tests/fixtures/model_probe/cases.json')
        self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(),
                         '96978ccade1edc8841ad23d7aef2676734157c6b2826a6707d5dbcabe64917bf')

    def test_fixed_4b_model_pin_keeps_official_runtime_and_resource_limits(self):
        pins = json.loads(Path('scripts/model_probe_pins.json').read_text())
        self.assertEqual(pins['runtime']['tag'], 'b11756')
        self.assertEqual(pins['model']['revision'], 'bc640142c66e1fdd12af0bd68f40445458f3869b')
        self.assertEqual(pins['model']['size'], 2889513184)
        self.assertEqual(pins['model']['sha256'], 'aca596860e8cb40af6539e3f2ea40df305f42515deac56d49c08d39a02e6533f')


if __name__ == '__main__':
    unittest.main()
