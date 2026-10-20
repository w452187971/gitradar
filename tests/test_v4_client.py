import datetime as dt
import unittest

from gitradar.github_client import GitHubClient, HttpResponse, BudgetExceeded
from gitradar.models import Budget


NOW = '2026-10-20T12:00:00Z'


def node(identity='R1', name='a/tool', stars=10):
    return {'id': identity, 'nameWithOwner': name, 'stargazerCount': stars,
            'createdAt': '2025-01-01T00:00:00Z', 'isArchived': False, 'isFork': False,
            'url': 'https://github.com/' + name}


class ClientTests(unittest.TestCase):
    def client(self, responses, token='test-token'):
        self.calls = []
        def transport(method, url, headers, body):
            self.calls.append((method, url, headers, body))
            response = responses.pop(0)
            if isinstance(response, Exception):
                raise response
            return response
        return GitHubClient(token=token, transport=transport, now=lambda: NOW, sleep=lambda _: None)

    def test_partial_graphql_matches_node_identity_not_position(self):
        client = self.client([HttpResponse(200, {}, {'data': {'nodes': [node('R2', 'b/tool'), None],
            'rateLimit': {'cost': 2, 'remaining': 998}}, 'errors': [{'message': 'one missing'}]})])
        batch = client.fetchObservations([{'full_name': 'a/tool', 'node_id': 'R1'},
                                          {'full_name': 'b/tool', 'node_id': 'R2'}], Budget())
        self.assertEqual([item['status'] for item in batch['observations']], ['failed', 'success'])
        self.assertEqual(batch['usage']['graphql_points'], 2)
        self.assertTrue(batch['errors'])

    def test_http_200_errors_are_not_observations(self):
        client = self.client([HttpResponse(200, {}, {'errors': [{'message': 'denied'}]})])
        batch = client.fetchObservations([{'full_name': 'a/tool', 'node_id': 'R1'}], Budget())
        self.assertEqual(batch['observations'][0]['status'], 'failed')
        self.assertEqual(batch['usage']['graphql_points'], 0)
        self.assertEqual(batch['usage']['graphql_unmeasured_requests'], 1)

    def test_batches_are_at_most_fifty(self):
        responses = [HttpResponse(200, {}, {'data': {'nodes': [node('R'+str(i), f'a/p{i}')
            for i in range(start, end)], 'rateLimit': {'cost': 1, 'remaining': 999}}})
            for start, end in [(0, 50), (50, 51)]]
        batch = self.client(responses).fetchObservations(
            [{'full_name': f'a/p{i}', 'node_id': 'R'+str(i)} for i in range(51)], Budget())
        self.assertEqual(len(self.calls), 2)
        self.assertEqual(sum(o['status'] == 'success' for o in batch['observations']), 51)

    def test_retry_counts_against_category_and_total(self):
        budget = Budget(content_requests=2)
        client = self.client([HttpResponse(500, {}, {}), HttpResponse(200, {}, {'ok': True})])
        self.assertEqual(client.requestRest('/repos/a/tool/readme', budget)['ok'], True)
        self.assertEqual(client.usage.rest_requests, 2)
        self.assertEqual(client.usage.retries, 1)
        with self.assertRaises(BudgetExceeded):
            client.requestRest('/repos/a/tool/readme', budget)
        self.assertEqual(len(self.calls), 2)

    def test_limits_search_and_optional_work_from_headers(self):
        client = self.client([HttpResponse(200, {'X-RateLimit-Remaining': '199'}, {})])
        client.requestRest('/repos/a/tool/readme', Budget())
        with self.assertRaises(BudgetExceeded):
            client.requestRest('/repos/a/tool/readme', Budget())
        other = self.client([HttpResponse(200, {}, {})])
        other.requestRest('/search/repositories?q=x', Budget(search_requests=1), 'search')
        with self.assertRaises(BudgetExceeded):
            other.requestRest('/search/repositories?q=x', Budget(search_requests=1), 'search')

    def test_rate_limit_stops_without_retry_and_records_reset(self):
        client = self.client([HttpResponse(429, {'Retry-After': '30', 'X-RateLimit-Reset': '999'}, {})])
        batch = client.fetchObservations([{'full_name': 'a/tool', 'node_id': 'R1'}], Budget())
        self.assertEqual(len(self.calls), 1)
        self.assertEqual(batch['observations'][0]['status'], 'failed')
        self.assertEqual(batch['usage']['retry_after'], 30)

    def test_etag_reuses_only_authenticated_matching_cache(self):
        client = self.client([HttpResponse(200, {'ETag': '"v1"'}, {'node_id': 'R1', 'x': 1}),
                              HttpResponse(304, {}, None)])
        cache = {}
        original = client.requestRest('/repos/a/tool', Budget(), 'identity', cache, 'R1')
        self.assertEqual(client.requestRest('/repos/a/tool', Budget(), 'identity', cache, 'R1'), original)
        self.assertEqual(self.calls[1][2]['If-None-Match'], '"v1"')
        self.assertEqual(client.usage.not_modified, 1)
        unsafe = self.client([HttpResponse(304, {}, None)], token=None)
        with self.assertRaises(ValueError):
            unsafe.requestRest('/repos/a/tool', Budget(), 'identity', cache, 'R1')

    def test_graphql_budget_stops_later_batches(self):
        client = self.client([HttpResponse(200, {}, {'data': {'nodes': [node()],
                              'rateLimit': {'cost': 600, 'remaining': 400}}})])
        batch = client.fetchObservations([{'full_name': f'a/{i}', 'node_id': f'R{i}'}
                                           for i in range(51)], Budget())
        self.assertEqual(len(self.calls), 1)
        self.assertEqual(batch['observations'][-1]['status'], 'deferred')

    def test_graphql_rate_limit_in_200_stops_later_batches(self):
        client = self.client([HttpResponse(200, {}, {'errors': [{'type': 'RATE_LIMITED', 'message': 'limit'}]})])
        batch = client.fetchObservations([{'full_name': f'a/p{i}', 'node_id': f'R{i}'} for i in range(51)], Budget())
        self.assertEqual(len(self.calls), 1)
        self.assertTrue(batch['usage']['rate_limited'])
        self.assertEqual(batch['observations'][-1]['status'], 'deferred')

    def test_rest_observation_fallback_is_bounded_and_identity_verified(self):
        body = {'full_name': 'a/tool', 'node_id': 'R1', 'created_at': '2025-01-01T00:00:00Z',
                'stargazers_count': 10, 'archived': False, 'fork': False}
        client = self.client([HttpResponse(200, {}, body)])
        batch = client.fetchRestObservations([{'full_name': 'a/tool', 'node_id': 'R1'},
                                              {'full_name': 'b/tool', 'node_id': 'R2'}],
                                             Budget(identity_requests=1))
        self.assertEqual([o['status'] for o in batch['observations']], ['success', 'deferred'])
        self.assertEqual(batch['usage']['identity_requests'], 1)

    def test_rest_total_limit_includes_all_subcategories(self):
        client = self.client([HttpResponse(200, {}, {}) for _ in range(3)])
        budget = Budget(rest_requests=3)
        for category in ['content', 'path', 'identity']:
            client.requestRest('/repos/a/tool', budget, category)
        with self.assertRaises(BudgetExceeded):
            client.requestRest('/repos/a/tool', budget, 'content')
        self.assertEqual(client.usage.rest_requests, 3)
        for category, field in [('content', 'content_requests'), ('path', 'path_requests'),
                                ('identity', 'identity_requests')]:
            other = self.client([HttpResponse(200, {}, {})])
            tiny = Budget(**{field: 1})
            other.requestRest('/repos/a/tool', tiny, category)
            with self.assertRaises(BudgetExceeded):
                other.requestRest('/repos/a/tool', tiny, category)

    def test_stale_cache_with_different_identity_is_rejected(self):
        client = self.client([HttpResponse(304, {}, None)])
        cache = {'https://api.github.com/repos/a/tool': {'identity': 'R2', 'authenticated': True,
                                                      'etag': 'v1', 'body': {'node_id': 'R2'}}}
        with self.assertRaises(ValueError):
            client.requestRest('/repos/a/tool', Budget(), 'identity', cache, 'R1')

    def test_read_evidence_decodes_readme_and_keeps_failures(self):
        client = self.client([HttpResponse(200, {'ETag': '"r"'}, {'content': 'SGVsbG8=', 'encoding': 'base64',
                              'sha': 'abc', 'html_url': 'https://github.com/a/tool/blob/main/README.md'}),
                              HttpResponse(404, {}, {}), HttpResponse(200, {}, {'node_id': 'R1',
                              'license': {'spdx_id': 'MIT'}, 'description': 'A file converter'})])
        bundle = client.readProjectEvidence({'full_name': 'a/tool', 'node_id': 'R1'}, None, Budget())
        self.assertEqual(bundle['refs'][0]['text'], 'Hello')
        self.assertEqual(bundle['status'], 'partial')
        self.assertTrue(bundle['errors'])

    def test_read_evidence_splits_sections_and_records_official_license(self):
        import base64
        readme = '# Tool\nA file converter.\n\n## Installation\nSupports Windows. No account or additional software required.'
        client = self.client([HttpResponse(200, {}, {'content': base64.b64encode(readme.encode()).decode(),
                              'encoding': 'base64', 'sha': 'abc'}),
                              HttpResponse(200, {}, {'tag_name': 'v1', 'body': 'New release', 'assets': []}),
                              HttpResponse(200, {}, {'node_id': 'R1', 'license': {'spdx_id': 'MIT'}})])
        bundle = client.readProjectEvidence({'full_name': 'a/tool', 'node_id': 'R1'}, None, Budget())
        self.assertTrue(any(ref['section'] == 'Installation' for ref in bundle['refs']))
        self.assertTrue(any(ref.get('license_spdx_id') == 'MIT' for ref in bundle['refs']))
        self.assertEqual(client.usage.content_requests, 3)

    def test_search_endpoint_cannot_bypass_its_budget_by_default_category(self):
        client = self.client([HttpResponse(200, {}, {})])
        client.requestRest('/search/repositories?q=x', Budget(search_requests=1))
        self.assertEqual(client.usage.search_requests, 1)
        self.assertEqual(client.usage.rest_requests, 0)
        with self.assertRaises(BudgetExceeded):
            client.requestRest('/search/repositories?q=x', Budget(search_requests=1))

    def test_failed_graphql_without_measured_cost_stops_conservatively(self):
        client = self.client([HttpResponse(200, {}, {'errors': [{'message': 'permission denied'}]})])
        batch = client.fetchObservations([{'full_name': f'a/p{i}', 'node_id': f'R{i}'} for i in range(51)], Budget())
        self.assertEqual(len(self.calls), 1)
        self.assertEqual(batch['usage']['graphql_unmeasured_requests'], 1)
        self.assertEqual(batch['observations'][-1]['status'], 'deferred')

    def test_metadata_ref_retains_fields_for_editorial_source_revalidation(self):
        import json
        client = self.client([HttpResponse(404, {}, {}), HttpResponse(404, {}, {}),
                              HttpResponse(200, {}, {'node_id': 'R1', 'full_name': 'a/tool',
                              'homepage': 'https://example.org', 'license': {'spdx_id': 'MIT'}})])
        bundle = client.readProjectEvidence({'full_name': 'a/tool', 'node_id': 'R1'}, None, Budget())
        metadata = next(ref for ref in bundle['refs'] if ref['section'] == 'metadata')
        self.assertEqual(json.loads(metadata['text'])['homepage'], 'https://example.org')

    def test_graphql_timeout_does_not_claim_unmeasured_points_or_continue(self):
        client = self.client([TimeoutError('unknown server result')])
        batch = client.fetchObservations([{'full_name': f'a/p{i}', 'node_id': f'R{i}'} for i in range(51)], Budget())
        self.assertEqual(len(self.calls), 1)
        self.assertEqual(batch['usage']['graphql_points'], 0)
        self.assertEqual(batch['usage']['graphql_unmeasured_requests'], 1)
        self.assertEqual(batch['observations'][-1]['status'], 'deferred')
