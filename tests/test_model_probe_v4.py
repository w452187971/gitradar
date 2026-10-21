"""两步诊断的结构、原文完整性与失败可见性；不运行权重。"""
import copy
import hashlib
import json
from pathlib import Path
import tempfile
from unittest.mock import patch
import unittest

from scripts import probe_local_model as probe


class ModelProbeV4Tests(unittest.TestCase):
    def setUp(self):
        text = '# Product\n\nAn application.\n\n## Restrictions\n\nDoes not run on Windows.\n'
        self.case = {'full_name': 'test/public', 'kind': 'desktop', 'refs': [
            {'ref_id': 'r1', 'source_quote': text, 'sha256': hashlib.sha256(text.encode()).hexdigest()}]}
        self.selection = {name: {'ref_id': None, 'paragraph_id': None, 'relation': 'unknown'} for name in probe.FIELDS}
        self.selection['purpose'] = {'ref_id': 'r1', 'paragraph_id': 'r1:p2', 'relation': 'project'}
        self.output = {name: {'value': None, 'ref_id': None} for name in probe.FIELDS}
        self.output['purpose'] = {'value': '一个应用程序', 'ref_id': 'r1'}

    def response(self, output, finish='stop', tokens=40):
        return [{'prompt': 'full context'}, {'tokens': [1] * 200}, {'choices': [{
            'message': {'content': json.dumps(output)}, 'finish_reason': finish}],
            'usage': {'completion_tokens': tokens, 'prompt_tokens': 200, 'total_tokens': 200 + tokens},
            'timings': {'prompt_ms': 1, 'predicted_ms': 2}}]

    def test_paragraph_packet_reconstructs_every_original_character(self):
        packet = probe.paragraphPacket(self.case)
        self.assertEqual(''.join(p['text'] for p in packet[0]['paragraphs']), self.case['refs'][0]['source_quote'])
        self.assertEqual([p['paragraph_id'] for p in packet[0]['paragraphs']], ['r1:p1', 'r1:p2', 'r1:p3', 'r1:p4'])
        for paragraph in packet[0]['paragraphs']:
            self.assertEqual(paragraph['sha256'], hashlib.sha256(paragraph['text'].encode()).hexdigest())
        stage1 = probe.selectionPayload(self.case)
        stage2 = probe.translationPayload(self.case, self.selection)
        for payload in [stage1, stage2]:
            context = json.loads(payload['messages'][1]['content'].removesuffix('\n/no_think'))['refs']
            self.assertEqual(context, probe.promptPacket(self.case))
            self.assertEqual(''.join(part['text'] for part in context[0]['paragraphs']), self.case['refs'][0]['source_quote'])
        schema = stage1['response_format']['json_schema']['schema']
        field = schema['properties']['purpose']['properties']
        self.assertEqual(set(field), {'ref_id', 'paragraph_id', 'relation'})
        self.assertEqual(field['relation']['enum'], ['project', 'dependency', 'third_party', 'unknown'])
        self.assertNotIn('value', field)

    def test_paragraph_roundtrip_preserves_whitespace_and_rejects_changed_source_hash(self):
        for text in ['\n\nA\n\n\nB\n', '\r\n# Title\r\n\r\nRequires X.\r\n', '', '\n',
                     '```text\nA\n\nB\n```\n\nNot supported.']:
            case = copy.deepcopy(self.case)
            case['refs'][0].update(source_quote=text, sha256=hashlib.sha256(text.encode()).hexdigest())
            packet = probe.paragraphPacket(case)
            self.assertEqual(''.join(part['text'] for part in packet[0]['paragraphs']), text)
        changed = copy.deepcopy(self.case)
        changed['refs'][0]['source_quote'] += 'new conditions'
        with patch('scripts.probe_local_model.localJson') as request:
            with tempfile.TemporaryDirectory() as directory:
                result = probe.runCase(changed, 12345, Path(directory), 1)
            self.assertEqual(request.call_count, 0)
            self.assertIn('hash mismatch', result['error'])

    def test_model_prompts_omit_machine_hash_metadata_without_editing_source_text(self):
        literal = 'SHA256=' + 'ab' * 32
        self.case['refs'][0]['source_quote'] += '\n' + literal
        text = self.case['refs'][0]['source_quote']
        self.case['refs'][0]['sha256'] = hashlib.sha256(text.encode()).hexdigest()
        for payload in [probe.selectionPayload(self.case), probe.translationPayload(self.case, self.selection)]:
            context = json.loads(payload['messages'][1]['content'].removesuffix('\n/no_think'))
            for ref in context['refs']:
                self.assertEqual(set(ref), {'ref_id', 'paragraphs'})
                for paragraph in ref['paragraphs']:
                    self.assertEqual(set(paragraph), {'paragraph_id', 'text'})
            rebuilt = ''.join(part['text'] for part in context['refs'][0]['paragraphs'])
            self.assertEqual(rebuilt, text)
            self.assertIn(literal, rebuilt)
        self.assertIn('sha256', probe.paragraphPacket(self.case)[0]['paragraphs'][0])

    def test_selector_rejects_free_text_foreign_or_cross_reference_paragraphs(self):
        for field in [dict(self.selection['purpose'], quote='made up'),
                      {'ref_id': 'r1', 'paragraph_id': 'foreign', 'relation': 'project'},
                      {'ref_id': None, 'paragraph_id': None, 'relation': 'project'},
                      {'ref_id': 'other', 'paragraph_id': 'r1:p2', 'relation': 'project'}]:
            selection = copy.deepcopy(self.selection)
            selection['purpose'] = field
            self.assertFalse(probe.checkSelection(selection, self.case)['selection_valid'])
        self.assertTrue(probe.checkSelection(self.selection, self.case)['selection_valid'])

    def test_two_stages_keep_raw_selection_and_bound_evidence_separate(self):
        original = copy.deepcopy(self.case)
        responses = self.response(self.selection) + self.response(self.output)
        with tempfile.TemporaryDirectory() as directory:
            with patch('scripts.probe_local_model.localJson', side_effect=responses) as request:
                result = probe.runCase(self.case, 12345, Path(directory), 1)
            self.assertTrue((Path(directory) / 'case-01-stage1.txt').exists())
            self.assertTrue((Path(directory) / 'case-01-stage2.txt').exists())
        self.assertEqual(request.call_count, 6)
        self.assertEqual(result['stage1']['raw_model_output'], self.selection)
        self.assertEqual(result['stage2']['raw_model_output'], self.output)
        self.assertEqual(result['selected_evidence']['purpose']['text'], 'An application.\n\n')
        self.assertEqual(result['relation_status'], 'model_judgment_unverified')
        self.assertEqual(result['semantic_status'], 'human_review_required')
        self.assertIsNotNone(result['runtime_bound_output'])
        self.assertEqual(self.case, original)
        self.assertEqual(result['generation_tokens'], 80)
        for name, maximum, call in [('stage1', 300, 2), ('stage2', 400, 5)]:
            self.assertEqual(result[name]['max_tokens'], maximum)
            self.assertEqual(result[name]['token_budget']['reserved_output_tokens'], maximum)
            self.assertEqual(request.call_args_list[call].args[2]['max_tokens'], maximum)
        self.assertEqual(result['status'], 'raw_contract_passed_semantics_pending')

    def test_translation_cannot_use_non_project_relation_or_new_field_source(self):
        for relation, refId in [('third_party', 'r1'), ('dependency', 'r1'), ('project', 'other')]:
            selection = copy.deepcopy(self.selection)
            selection['purpose']['relation'] = relation
            output = copy.deepcopy(self.output)
            output['purpose']['ref_id'] = refId
            with tempfile.TemporaryDirectory() as directory:
                with patch('scripts.probe_local_model.localJson', side_effect=self.response(selection) + self.response(output)):
                    result = probe.runCase(self.case, 12345, Path(directory), 1)
            self.assertEqual(result['raw_model_output'], output)
            self.assertIsNone(result['runtime_bound_output'])
            self.assertFalse(result['raw_valid'])

    def test_truncation_or_over_budget_stage_never_continues_or_binds(self):
        for responses, calls in [(self.response(self.selection, finish='length'), 3),
                                 (self.response(self.selection, tokens=301), 3),
                                 (self.response(self.selection) + self.response(self.output, finish='length'), 6),
                                 (self.response(self.selection) + self.response(self.output, tokens=401), 6)]:
            with tempfile.TemporaryDirectory() as directory:
                with patch('scripts.probe_local_model.localJson', side_effect=responses) as request:
                    result = probe.runCase(self.case, 12345, Path(directory), 1)
            self.assertEqual(request.call_count, calls)
            self.assertIsNone(result['runtime_bound_output'])
            self.assertEqual(result['status'], 'failed')
            self.assertIsNotNone(result['stage1']['raw_model_output'])

    def test_no_source_still_calls_both_stages_and_exposes_translation_guess(self):
        case = {'full_name': 'test/public', 'kind': 'missing', 'refs': [], 'controls': ['all_fields_unknown']}
        selection = {name: {'ref_id': None, 'paragraph_id': None, 'relation': 'unknown'} for name in probe.FIELDS}
        output = copy.deepcopy(self.output)
        output['purpose']['ref_id'] = None
        with tempfile.TemporaryDirectory() as directory:
            with patch('scripts.probe_local_model.localJson', side_effect=self.response(selection) + self.response(output)) as request:
                result = probe.runCase(case, 12345, Path(directory), 1)
        self.assertEqual(request.call_count, 6)
        self.assertTrue(result['stage1']['inference_attempted'])
        self.assertTrue(result['stage2']['inference_attempted'])
        self.assertEqual(result['unknown_control'], {'passed': 7, 'total': 8})
        self.assertEqual(result['raw_model_output']['purpose']['value'], '一个应用程序')
        self.assertIsNone(result['runtime_bound_output'])

    def test_path_cannot_jump_to_an_unselected_paragraph_of_the_same_reference(self):
        text = 'Install https://example.org/install\n\nDependency https://example.org/dependency'
        self.case['refs'][0].update(source_quote=text, sha256=hashlib.sha256(text.encode()).hexdigest())
        self.selection['path'] = {'ref_id': 'r1', 'paragraph_id': 'r1:p1', 'relation': 'project'}
        self.output['path'] = {'value': 'https://example.org/dependency', 'ref_id': 'r1'}
        with tempfile.TemporaryDirectory() as directory:
            with patch('scripts.probe_local_model.localJson', side_effect=self.response(self.selection) + self.response(self.output)):
                result = probe.runCase(self.case, 12345, Path(directory), 1)
        self.assertEqual(result['validation_errors']['path'], 'path_not_in_selected_paragraph')
        self.assertIsNone(result['runtime_bound_output'])
        self.assertEqual(result['raw_model_output']['path']['value'], 'https://example.org/dependency')

    def test_deadline_keeps_current_case_and_completed_stage1_for_failure_report(self):
        report = {'cases': []}
        responses = self.response(self.selection) + [probe.ProbeDeadlineExceeded()]
        with tempfile.TemporaryDirectory() as directory:
            with patch('scripts.probe_local_model.runSchemaCanary', return_value={'status': 'passed'}):
                with patch('scripts.probe_local_model.localJson', side_effect=responses):
                    with self.assertRaises(probe.ProbeDeadlineExceeded):
                        probe.runDevelopmentProbe([self.case] * 6, 12345, report, Path(directory))
        self.assertEqual(len(report['cases']), 1)
        result = report['cases'][0]
        self.assertEqual(result['stage1']['raw_model_output'], self.selection)
        self.assertEqual(result['stage1']['status'], 'completed')
        self.assertEqual(result['stage2']['status'], 'failed')
        self.assertEqual(result['active_stage'], 'stage2')
        self.assertIsNone(result['runtime_bound_output'])
        probe.summarize(report)
        self.assertEqual(report['metrics']['requested'], 6)
        self.assertEqual(report['metrics']['attempted'], 1)
        self.assertEqual(report['status'], 'failed_unverified')

    def test_invalid_selector_and_context_overflow_never_reach_stage2(self):
        invalid = copy.deepcopy(self.selection)
        invalid['purpose']['paragraph_id'] = 'foreign'
        for responses, calls in [(self.response(invalid), 3),
                                 ([{'prompt': 'large'}, {'tokens': [1] * 4000}], 2)]:
            with tempfile.TemporaryDirectory() as directory:
                with patch('scripts.probe_local_model.localJson', side_effect=responses) as request:
                    result = probe.runCase(self.case, 12345, Path(directory), 1)
            self.assertEqual(request.call_count, calls)
            self.assertEqual(result['stage2']['status'], 'not_attempted')
            self.assertIsNone(result['runtime_bound_output'])
            self.assertEqual(result['status'], 'failed')

    def test_generation_allowance_is_total_700_not_700_per_stage(self):
        self.assertEqual(probe.selectionPayload(self.case)['max_tokens'], 300)
        self.assertEqual(probe.translationPayload(self.case, self.selection)['max_tokens'], 400)
        self.assertEqual(probe.buildReport()['version'], 4)
        self.assertEqual(probe.buildReport()['limits']['max_tokens'], 700)


if __name__ == '__main__':
    unittest.main()
