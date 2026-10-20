import copy
import hashlib
import unittest

from gitradar.evidence import mergeEvidence, refreshPaths
from gitradar.github_client import GitHubClient, HttpResponse
from gitradar.models import Budget


class EvidenceRefreshTests(unittest.TestCase):
    def setUp(self):
        self.old = {'full_name': 'o/a', 'node_id': 'N1', 'facts': {'purpose': {'value': '用途'}},
                    'refs': [{'id': 'intro', 'source_kind': 'readme', 'text': 'Official purpose.',
                              'content_hash': 'original', 'checked_at': '2026-10-01T00:00:00Z'}]}
        self.new = {'full_name': 'o/a', 'node_id': 'N1', 'status': 'success',
                    'refs': [{'id': 'readme:new', 'source_kind': 'readme',
                              'text': '# A\nOfficial purpose.\nNew sponsor badge',
                              'content_hash': 'new-source', 'checked_at': '2026-10-20T00:00:00Z'}]}

    def test_unrelated_readme_change_retains_verified_fragment_hash(self):
        merged = mergeEvidence(self.old, self.new)
        ref = next(r for r in merged['refs'] if r['id'] == 'intro')
        self.assertEqual(ref['content_hash'], 'original')
        self.assertEqual(ref['checked_at'], '2026-10-20T00:00:00Z')

    def test_changed_core_statement_revokes_bound_hash(self):
        self.new['refs'][0]['text'] = 'The old capability has been removed.'
        merged = mergeEvidence(self.old, self.new)
        ref = next(r for r in merged['refs'] if r['id'] == 'intro')
        self.assertNotEqual(ref['content_hash'], 'original')

    def test_failed_source_does_not_refresh_evidence_date(self):
        merged = mergeEvidence(self.old, {'refs': [], 'status': 'failed', 'errors': ['timeout']})
        self.assertEqual(merged['refs'][0]['checked_at'], '2026-10-01T00:00:00Z')

    def test_merging_does_not_mutate_editor_or_previous_evidence(self):
        original = copy.deepcopy(self.old)
        mergeEvidence(self.old, self.new)
        self.assertEqual(original, self.old)

    def test_generated_source_versions_do_not_accumulate_forever(self):
        previous = copy.deepcopy(self.old)
        for version in range(8):
            fetched = copy.deepcopy(self.new)
            fetched['refs'][0]['id'] = f'readme:version:{version}'
            fetched['refs'][0]['text'] += str(version)
            previous = mergeEvidence(previous, fetched)
        self.assertEqual(len(previous['refs']), 2)

    def test_head_check_never_sends_token_to_official_website(self):
        seen = []
        def transport(method, url, headers, body):
            seen.append((method, url, headers))
            return HttpResponse(200, {}, None)
        client = GitHubClient('secret', transport=transport)
        project = {'full_name': 'o/a', 'content': {'official_urls': ['https://official.example'],
                   'usage_paths': [{'url': 'https://official.example/download'}],
                   'claims': {'usage_paths': ['intro']}}}
        result = refreshPaths([project], {'projects': {'o/a': self.old}}, client, Budget(), '2026-10-20T00:00:00Z')
        ref = result['projects']['o/a']['refs'][0]
        self.assertEqual(seen[0][:2], ('HEAD', 'https://official.example/download'))
        self.assertNotIn('Authorization', seen[0][2])
        self.assertEqual(ref['path_checked_at'], '2026-10-20T00:00:00Z')
        self.assertEqual(ref['checked_at'], '2026-10-01T00:00:00Z')

    def test_confirmed_missing_path_is_marked_without_freshening_date(self):
        client = GitHubClient(transport=lambda *args: HttpResponse(404, {}, None))
        project = {'full_name': 'o/a', 'content': {'usage_paths': [{'url': 'https://github.com/o/a/releases'}],
                   'claims': {'usage_paths': ['intro']}}}
        result = refreshPaths([project], {'projects': {'o/a': self.old}}, client, Budget(), '2026-10-20T00:00:00Z')
        ref = result['projects']['o/a']['refs'][0]
        self.assertEqual(ref['path_status'], 404)
        self.assertNotIn('path_checked_at', ref)


if __name__ == '__main__':
    unittest.main()
