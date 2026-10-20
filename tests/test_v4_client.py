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

    def test_confirmed_deleted_seed_sources_revoke_recommendation(self):
        import json
        from pathlib import Path
        from gitradar.content import deriveFacts, resolveContent
        from gitradar.evidence import mergeEvidence
        root = Path(__file__).resolve().parents[1]
        previous = json.loads((root/'data/seed-evidence.json').read_text())['projects']['localsend/localsend']
        editorial = json.loads((root/'data/curation.json').read_text())['projects']['localsend/localsend']
        client = GitHubClient('secret', transport=lambda *args: HttpResponse(404, {}, {}), now=lambda: NOW)
        fetched = client.readProjectEvidence(previous, previous, Budget())
        content = resolveContent(deriveFacts(mergeEvidence(previous, fetched)), editorial, '2026-10-20T20:00:00Z')
        self.assertFalse(content['eligibility']['eligible'])
        self.assertTrue(any(ref['status'] == 404 for ref in fetched['refs']))
        self.assertEqual(previous['refs'][0]['status'], 200)

    def test_graphql_critical_null_and_field_errors_fail_only_affected_nodes(self):
        for field in ['isArchived', 'isFork', 'id', 'nameWithOwner', 'stargazerCount', 'createdAt']:
            for nullValue in [True, False]:
                with self.subTest(field=field, null=nullValue):
                    bad = node()
                    if nullValue:
                        bad[field] = None
                    payload = {'data': {'r0': bad, 'r1': node('R2', 'b/tool'),
                               'rateLimit': {'cost': 1, 'remaining': 999}},
                               'errors': [{'message': 'failed critical field', 'path': ['r0', field]}]}
                    batch = self.client([HttpResponse(200, {}, payload)]).fetchObservations(
                        [{'full_name': 'a/tool'}, {'full_name': 'b/tool'}], Budget())
                    self.assertEqual([o['status'] for o in batch['observations']], ['failed', 'success'])

    def test_bound_sources_are_fetched_by_unique_url_before_optional_defaults(self):
        import base64
        old = {'full_name': 'a/tool', 'node_id': 'R1', 'official_urls': ['https://official.example'],
               'facts': {'license': {'ref_ids': ['license']}}, 'refs': [
                   {'id': 'license', 'url': 'https://raw.githubusercontent.com/a/tool/main/COPYING',
                    'source_kind': 'readme', 'text': 'MIT license', 'checked_at': '2026-10-01T00:00:00Z'},
                   {'id': 'install', 'url': 'https://github.com/a/tool/blob/main/docs/install.md',
                    'source_kind': 'readme', 'text': 'Install the tool.'},
                   {'id': 'web', 'url': 'https://official.example/help', 'source_kind': 'official_site', 'text': 'Install'},
                   {'id': 'path', 'url': 'https://official.example/help', 'source_kind': 'official_site', 'text': 'Install'}]}
        encoded = lambda text: {'encoding': 'base64', 'content': base64.b64encode(text.encode()).decode(), 'sha': 'new'}
        client = self.client([HttpResponse(200, {}, encoded('MIT license')),
                              HttpResponse(200, {}, encoded('Install the tool.')),
                              HttpResponse(200, {'Content-Type': 'text/html'}, '<h1>Install</h1><script>wrong</script><p>Safely.</p>')])
        fetched = client.readProjectEvidence(old, old, Budget(content_requests=3))
        self.assertEqual(len(self.calls), 3)
        self.assertIn('/contents/COPYING?ref=main', self.calls[0][1])
        self.assertIn('/contents/docs/install.md?ref=main', self.calls[1][1])
        self.assertEqual(self.calls[2][1], 'https://official.example/help')
        self.assertNotIn('Authorization', self.calls[2][2])
        self.assertTrue(any(ref['url'] == old['refs'][0]['url'] and ref['text'] == 'MIT license' for ref in fetched['refs']))
        web = next(ref for ref in fetched['refs'] if ref['url'] == 'https://official.example/help')
        self.assertEqual(web['text'], 'Install\nSafely.')
        self.assertEqual(web['checked_at'], NOW)

    def test_website_revalidation_requires_verified_origin_and_caps_body(self):
        old = {'full_name': 'a/tool', 'node_id': 'R1', 'official_urls': ['https://official.example'],
               'refs': [{'id': 'bad', 'url': 'https://evil.example/help', 'source_kind': 'official_site'},
                        {'id': 'large', 'url': 'https://official.example/help', 'source_kind': 'official_document'}]}
        client = self.client([HttpResponse(200, {}, 'x'*(1024*1024+1))])
        fetched = client.readProjectEvidence(old, old, Budget(content_requests=1))
        self.assertEqual(len(self.calls), 1)
        self.assertEqual(self.calls[0][1], 'https://official.example/help')
        self.assertTrue(fetched['errors'])
        self.assertFalse(any(ref.get('checked_at') == NOW for ref in fetched['refs']))

    def test_timeout_keeps_bound_source_text_and_old_date(self):
        old = {'full_name': 'a/tool', 'node_id': 'R1', 'official_urls': [], 'refs': [
            {'id': 'license', 'url': 'https://raw.githubusercontent.com/a/tool/main/LICENSE',
             'source_kind': 'readme', 'text': 'Original', 'status': 200, 'checked_at': '2026-10-01T00:00:00Z'}]}
        client = self.client([TimeoutError('offline')])
        fetched = client.readProjectEvidence(old, old, Budget(content_requests=1))
        ref = next(ref for ref in fetched['refs'] if ref['id'] == 'license')
        self.assertEqual(ref['checked_at'], '2026-10-01T00:00:00Z')
        self.assertEqual(ref['status'], 200)
        self.assertEqual(ref['text'], 'Original')

    def test_real_transport_reads_html_and_caps_stream_to_one_mebibyte(self):
        from unittest.mock import Mock, patch
        from gitradar.github_client import httpTransport
        class Response:
            status = 200
            headers = {'Content-Type': 'text/html'}
            def __enter__(self):
                return self
            def __exit__(self, *args):
                return False
            def read(self, limit=-1):
                self.limit = limit
                return b'<h1>Visible</h1>'
        response = Response()
        opener = Mock()
        opener.open.return_value = response
        with patch('urllib.request.build_opener', return_value=opener):
            result = httpTransport('GET', 'https://official.example/help', {'User-Agent': 'test'}, None)
        self.assertEqual(result.body, '<h1>Visible</h1>')
        self.assertEqual(response.limit, 1024*1024+1)

    def test_redirect_handler_never_forwards_auth_to_other_origin(self):
        import urllib.request
        from gitradar.github_client import SameOriginRedirectHandler
        handler = SameOriginRedirectHandler()
        request = urllib.request.Request('https://api.github.com/repos/a/tool',
                                         headers={'Authorization': 'Bearer secret'})
        redirected = handler.redirect_request(request, None, 302, 'redirect', {}, 'https://evil.example/path')
        self.assertIsNone(redirected)

    def test_external_confirmed_gone_retains_old_date_and_typed_status(self):
        old = {'full_name': 'a/tool', 'node_id': 'R1', 'official_urls': ['https://official.example'],
               'refs': [{'id': 'site', 'url': 'https://official.example/help', 'source_kind': 'official_document',
                         'status': 200, 'text': 'Was here', 'checked_at': '2026-10-01T00:00:00Z'}]}
        client = self.client([HttpResponse(410, {}, None)])
        fetched = client.readProjectEvidence(old, old, Budget(content_requests=1))
        ref = next(ref for ref in fetched['refs'] if ref['id'] == 'site')
        self.assertEqual(ref['status'], 410)
        self.assertEqual(ref['checked_at'], '2026-10-01T00:00:00Z')
        self.assertEqual(ref['text'], 'Was here')

    def test_github_file_document_keeps_kind_and_revalidates_exact_text(self):
        import base64
        old = {'full_name': 'a/tool', 'node_id': 'R1', 'refs': [
            {'id': 'doc', 'url': 'https://github.com/a/tool/blob/main/docs/setup.md',
             'source_kind': 'official_document', 'text': 'Original instructions.'}]}
        client = self.client([HttpResponse(200, {}, {'encoding': 'base64', 'sha': 'v2',
                              'content': base64.b64encode(b'Original instructions.').decode()})])
        fetched = client.readProjectEvidence(old, old, Budget(content_requests=1))
        doc = next(ref for ref in fetched['refs'] if ref['url'] == old['refs'][0]['url'])
        self.assertEqual(doc['text'], 'Original instructions.')
        self.assertEqual(doc['source_kind'], 'official_document')

    def test_null_critical_state_without_graphql_errors_is_failed(self):
        for field in ['isArchived', 'isFork']:
            bad = node()
            bad.pop(field)
            payload = {'data': {'nodes': [bad], 'rateLimit': {'cost': 1, 'remaining': 999}}}
            batch = self.client([HttpResponse(200, {}, payload)]).fetchObservations(
                [{'full_name': 'a/tool', 'node_id': 'R1'}], Budget())
            self.assertEqual(batch['observations'][0]['status'], 'failed')

    def test_graphql_nodes_error_path_matches_reordered_node_identity(self):
        payload = {'data': {'nodes': [node('R2', 'b/tool'), node()],
                           'rateLimit': {'cost': 1, 'remaining': 999}},
                   'errors': [{'message': 'archived unavailable', 'path': ['nodes', 1, 'isArchived']}]}
        batch = self.client([HttpResponse(200, {}, payload)]).fetchObservations(
            [{'full_name': 'a/tool', 'node_id': 'R1'}, {'full_name': 'b/tool', 'node_id': 'R2'}], Budget())
        self.assertEqual([o['status'] for o in batch['observations']], ['failed', 'success'])

    def test_official_page_fragment_only_refreshes_when_still_present(self):
        from gitradar.evidence import mergeEvidence
        old = {'full_name': 'a/tool', 'node_id': 'R1', 'official_urls': ['https://official.example'],
               'refs': [{'id': 'doc', 'url': 'https://official.example/install',
                         'source_kind': 'official_site', 'text': 'Requires Windows 11.',
                         'content_hash': 'edited-source-hash', 'checked_at': '2026-10-01T00:00:00Z'}]}
        for text, unchanged in [('<nav>Menu</nav><p>Requires Windows 11.</p>', True),
                                ('<p>Requires Windows 12.</p>', False)]:
            client = self.client([HttpResponse(200, {'Content-Type': 'text/html'}, text)])
            fetched = client.readProjectEvidence(old, old, Budget(content_requests=1))
            merged = mergeEvidence(old, fetched)
            document = next(ref for ref in merged['refs'] if ref['id'] == 'doc')
            self.assertEqual(document['content_hash'] == 'edited-source-hash', unchanged)
            self.assertEqual(document['checked_at'], NOW)

    def test_rest_not_found_status_is_machine_readable(self):
        for status in [404, 410]:
            client = self.client([HttpResponse(status, {}, {})])
            batch = client.fetchRestObservations([{'full_name': 'a/tool', 'node_id': 'R1'}], Budget())
            self.assertEqual(batch['observations'][0]['status'], 'not_found')
            self.assertEqual(batch['observations'][0]['http_status'], status)

    def test_graphql_null_is_unknown_unless_repository_path_confirms_not_found(self):
        for errors, confirmed in [([], False), ([{'type': 'NOT_FOUND', 'path': ['r0']}], True),
                                  ([{'type': 'NOT_FOUND', 'path': ['r1']}], False),
                                  ([{'type': 'NOT_FOUND', 'path': ['r0', 'license']}], False)]:
            payload = {'data': {'r0': None, 'rateLimit': {'cost': 1, 'remaining': 999}}, 'errors': errors}
            batch = self.client([HttpResponse(200, {}, payload)]).fetchObservations([{'full_name': 'a/tool'}], Budget())
            result = batch['observations'][0]
            self.assertEqual(result.get('http_status') == 404, confirmed)
            self.assertEqual(result['status'], 'not_found' if confirmed else 'failed')

    def test_graphql_error_only_response_can_confirm_repository_not_found(self):
        payload = {'errors': [{'type': 'NOT_FOUND', 'path': ['r0']}]}
        batch = self.client([HttpResponse(200, {}, payload)]).fetchObservations([{'full_name': 'a/tool'}], Budget())
        self.assertEqual(batch['observations'][0]['http_status'], 404)
        self.assertEqual(batch['observations'][0]['status'], 'not_found')

    def test_graphql_multiple_null_nodes_do_not_share_not_found_confirmation(self):
        payload = {'data': {'nodes': [None, None], 'rateLimit': {'cost': 1, 'remaining': 999}},
                   'errors': [{'type': 'NOT_FOUND', 'path': ['nodes', 0]}]}
        batch = self.client([HttpResponse(200, {}, payload)]).fetchObservations(
            [{'full_name': 'a/tool', 'node_id': 'R1'}, {'full_name': 'b/tool', 'node_id': 'R2'}], Budget())
        self.assertEqual([o['status'] for o in batch['observations']], ['not_found', 'failed'])
        self.assertNotIn('http_status', batch['observations'][1])

    def repositorySource(self):
        import json
        from pathlib import Path
        from gitradar.sources import SourceRequest
        old = json.loads((Path(__file__).resolve().parents[1]/'data/seed-evidence.json').read_text())['projects']['HandBrake/HandBrake']
        original = next(ref for ref in old['refs'] if ref['source_kind'] == 'repository')
        payload = json.loads(original['text'])
        payload.update(stargazers_count=99999, permissions={'push': False}, temp_clone_token='fixture-never-persist')
        client = self.client([HttpResponse(200, {'ETag': 'metadata-v1'}, payload)])
        source = SourceRequest(original['url'], original['url'], 'repository', old_refs=[original])
        self.metadataCache = {}
        fetched = client.readEvidenceSource(source, old, Budget(), self.metadataCache)
        return old, original, payload, fetched

    def test_requested_source_url_does_not_rewrite_repository_html_url_fact(self):
        import json
        from gitradar.evidence import mergeEvidence
        old, original, payload, fetched = self.repositorySource()
        metadata = next(ref for ref in fetched if ref['section'] == 'metadata')
        self.assertEqual(metadata['url'], original['url'])
        self.assertEqual(json.loads(metadata['text'])['html_url'], payload['html_url'])
        merged = mergeEvidence(old, {'refs': fetched})
        actual = next(ref for ref in merged['refs'] if ref['id'] == original['id'])
        self.assertEqual(actual['content_hash'], original['content_hash'])

    def test_repository_evidence_serializes_only_public_product_fact_fields(self):
        import json
        _, _, _, fetched = self.repositorySource()
        metadata = next(ref for ref in fetched if ref['section'] == 'metadata')
        body = json.loads(metadata['text'])
        self.assertNotIn('temp_clone_token', body)
        self.assertNotIn('permissions', body)
        self.assertNotIn('stargazers_count', body)
        self.assertNotIn('fixture-never-persist', metadata['text'])
        self.assertIn('license', body)

    def test_repository_etag_cache_does_not_persist_unneeded_authenticated_fields(self):
        _, original, _, _ = self.repositorySource()
        cached = self.metadataCache[original['url']]['body']
        self.assertNotIn('temp_clone_token', cached)
        self.assertNotIn('permissions', cached)

    def test_repository_identity_failure_still_filters_the_returned_etag_cache(self):
        previous = {'full_name': 'a/tool', 'node_id': 'R1', 'refs': [{
            'id': 'metadata', 'source_kind': 'repository',
            'url': 'https://api.github.com/repos/a/tool', 'text': '{}'}]}
        payload = {'node_id': 'REPLACEMENT_NODE', 'full_name': 'a/tool',
                   'permissions': {'push': False}, 'temp_clone_token': 'synthetic-never-persist',
                   'stargazers_count': 99999}
        client = self.client([HttpResponse(200, {'ETag': 'different-identity'}, payload)])
        result = client.readProjectEvidence(previous, previous, Budget(content_requests=1))
        self.assertTrue(any('identity changed' in error for error in result['errors']))
        cached = result['cache']['https://api.github.com/repos/a/tool']['body']
        self.assertEqual(cached, {'node_id': 'REPLACEMENT_NODE', 'full_name': 'a/tool'})
        self.assertNotIn('synthetic-never-persist', str(result))

    def test_repository_kind_license_endpoint_is_fetched_as_the_bound_document(self):
        import base64
        previous = {'full_name': 'a/tool', 'node_id': 'R1', 'refs': [{
            'id': 'license_document_review', 'source_kind': 'repository',
            'url': 'https://api.github.com/repos/a/tool/license', 'text': 'License title.',
            'content_hash': 'reviewed-span', 'checked_at': '2026-10-01T00:00:00Z'}]}
        payload = {'encoding': 'base64', 'content': base64.b64encode(b'License title.\nThe full grant.').decode(),
                   'sha': 'license-sha', 'node_id': 'CONTENT_BLOB_ID',
                   'html_url': 'https://github.com/a/tool/blob/main/LICENSE'}
        client = self.client([HttpResponse(200, {}, payload)])
        fetched = client.readProjectEvidence(previous, previous, Budget(content_requests=1))
        self.assertEqual(self.calls[0][1], 'https://api.github.com/repos/a/tool/license')
        document = next(ref for ref in fetched['refs'] if ref.get('text') == 'License title.\nThe full grant.')
        self.assertEqual(document['source_kind'], 'repository')
        self.assertEqual(document['url'], previous['refs'][0]['url'])
        self.assertEqual(document['checked_at'], NOW)
