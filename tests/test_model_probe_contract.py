"""b11756 已核对的 HTTP 解析契约复现；真实二进制另由远程 canary 检验。"""
import copy
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
from pathlib import Path
import tempfile
import threading
from unittest.mock import patch
import unittest

from scripts import probe_local_model as probe
from scripts.probe_local_model import (
    localJson, requestPayload, responseSchema,
)


class B11756ContractHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        # 冻结官方 server-common.cpp:1357-1382 的请求契约，绝不宣称执行了上游 C++。
        body = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
        responseFormat = body.get('response_format', {})
        schema = body.get('json_schema')
        if responseFormat.get('type') == 'json_schema':
            schema = responseFormat.get('json_schema', {}).get('schema', {})
        elif responseFormat.get('type') == 'json_object':
            schema = responseFormat.get('schema', {})
        if schema == {}:
            schema = {'type': 'object'}
        data = json.dumps({'parsed_schema': schema}).encode()
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, format, *args):
        return


class ModelProbeContractTests(unittest.TestCase):
    def test_actual_http_body_delivers_nested_schema_to_pinned_contract(self):
        server = HTTPServer(('127.0.0.1', 0), B11756ContractHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            payload = requestPayload({'full_name': 'test/public', 'refs': []})
            result = localJson(server.server_port, '/v1/chat/completions', payload)
            self.assertEqual(result['parsed_schema'], responseSchema())
            legacy = copy.deepcopy(payload)
            legacy['response_format'] = {'type': 'json_schema', 'schema': responseSchema()}
            result = localJson(server.server_port, '/v1/chat/completions', legacy)
            self.assertEqual(result['parsed_schema'], {'type': 'object'})
        finally:
            server.shutdown()
            thread.join(timeout=2)
            server.server_close()

    def canaryResponses(self, output):
        return [{'prompt': 'canary'}, {'tokens': [1] * 40}, {'choices': [{
            'message': {'content': json.dumps(output)}, 'finish_reason': 'stop'}],
            'timings': {'prompt_ms': 1, 'predicted_ms': 2}}]

    def test_schema_canary_requires_exact_quote_object_not_any_json(self):
        for output, status in [(probe.CANARY_OUTPUT, 'passed'), ({'purpose': 'SHAPE_BYPASS'}, 'failed')]:
            with self.subTest(output=output), tempfile.TemporaryDirectory() as directory:
                with patch('scripts.probe_local_model.localJson', side_effect=self.canaryResponses(output)) as request:
                    result = probe.runSchemaCanary(12345, Path(directory))
                self.assertEqual(result['status'], status)
                sent = request.call_args_list[-1].args[2]
                self.assertEqual(sent['response_format']['json_schema']['schema']['properties']['purpose']['type'], 'object')
                self.assertIn('SHAPE_BYPASS', sent['messages'][0]['content'])
                self.assertTrue((Path(directory) / 'case-00-schema-canary.txt').exists())

    def test_failed_canary_stops_all_six_cases_and_marks_infrastructure_failure(self):
        report = {'cases': []}
        with patch('scripts.probe_local_model.runSchemaCanary', return_value={'status': 'failed'}):
            with patch('scripts.probe_local_model.runCase') as run:
                with self.assertRaisesRegex(RuntimeError, 'canary'):
                    probe.runDevelopmentProbe([{}] * 6, 12345, report, Path('/tmp'))
        self.assertEqual(run.call_count, 0)
        self.assertEqual(report['cases'], [])
        self.assertEqual(report['failure_kind'], 'schema_canary_infrastructure')

    def test_passed_canary_runs_all_six_including_no_source_control(self):
        cases = probe.loadCases(Path('tests/fixtures/model_probe/cases.json'))
        report = {'cases': []}
        with patch('scripts.probe_local_model.runSchemaCanary', return_value={'status': 'passed'}):
            with patch('scripts.probe_local_model.runCase', return_value={'status': 'pending'}) as run:
                probe.runDevelopmentProbe(cases, 12345, report, Path('/tmp'))
        self.assertEqual(run.call_count, 6)
        self.assertEqual(run.call_args_list[-1].args[0]['full_name'], 'squoosh/squoosh')
        self.assertEqual(run.call_args_list[-1].args[0]['refs'], [])
        self.assertEqual(len(report['cases']), 6)

    def test_main_prompt_serializes_the_nested_output_shape(self):
        payload = requestPayload({'full_name': 'test/public', 'refs': []})
        template = json.loads(payload['messages'][0]['content'].split('OUTPUT_TEMPLATE=', 1)[1])
        self.assertEqual(set(template['purpose']), {'value', 'source_quote', 'ref_id'})
        self.assertEqual(set(template), set(responseSchema()['properties']))


if __name__ == '__main__':
    unittest.main()
