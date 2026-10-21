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

    def test_failed_readme_reusing_multiple_old_sections_does_not_mix_them(self):
        self.old['refs'].append({'id': 'install', 'source_kind': 'readme',
                                 'text': 'A much longer installation paragraph.',
                                 'content_hash': 'install-old', 'checked_at': '2026-10-01T00:00:00Z'})
        fetched = {'refs': copy.deepcopy(self.old['refs']), 'status': 'partial', 'errors': ['timeout']}
        merged = mergeEvidence(self.old, fetched)
        self.assertEqual(merged['refs'][0]['content_hash'], 'original')
        self.assertEqual(merged['refs'][0]['checked_at'], '2026-10-01T00:00:00Z')

    def test_independent_license_file_cannot_be_refreshed_from_default_readme(self):
        self.old['refs'][0]['url'] = 'https://raw.githubusercontent.com/o/a/main/COPYING'
        self.new['refs'][0]['url'] = 'https://github.com/o/a/blob/main/README.md'
        merged = mergeEvidence(self.old, self.new)
        self.assertEqual(merged['refs'][0]['checked_at'], '2026-10-01T00:00:00Z')
        self.assertEqual(merged['refs'][0]['content_hash'], 'original')

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


    def test_bound_context_hash_change_requires_review_even_when_fragment_remains(self):
        self.old['refs'][0]['source_hash'] = hashlib.sha256(b'Official purpose.').hexdigest()
        originalHash = self.old['refs'][0]['content_hash']
        self.new['refs'][0]['text'] = 'Official purpose.\nRequires a paid account and companion software.'
        self.new['refs'][0]['content_hash'] = hashlib.sha256(self.new['refs'][0]['text'].encode()).hexdigest()
        merged = mergeEvidence(self.old, self.new)
        ref = next(r for r in merged['refs'] if r['id'] == 'intro')
        self.assertTrue(ref['context_changed'])
        self.assertEqual(ref['content_hash'], originalHash)
        self.assertEqual(ref['source_hash'], self.new['refs'][0]['content_hash'])
        again = mergeEvidence(merged, self.new)
        self.assertTrue(next(r for r in again['refs'] if r['id'] == 'intro')['context_changed'])

    def test_web_fragment_same_id_still_compares_full_source_hash(self):
        self.old['refs'][0].update(source_kind='official_site', source_hash='old-full-source')
        current = copy.deepcopy(self.old['refs'][0])
        current.update(source_hash='new-full-source', checked_at='2026-10-20T00:00:00Z')
        merged = mergeEvidence(self.old, {'refs': [current]})
        self.assertTrue(merged['refs'][0]['context_changed'])
        self.assertEqual(merged['refs'][0]['source_hash'], 'new-full-source')

    def test_repository_extra_star_field_does_not_revoke_bound_metadata(self):
        self.old['refs'][0].update(source_kind='repository', text='{"license": "MIT"}', source_hash='old')
        self.new['refs'][0].update(source_kind='repository', text='{"license": "MIT", "stargazers_count": 150}')
        ref = mergeEvidence(self.old, self.new)['refs'][0]
        self.assertEqual(ref['content_hash'], 'original')
        self.assertFalse(ref.get('context_changed'))

    def test_new_release_cannot_keep_reviewed_platform_fragment(self):
        self.old['refs'][0].update(source_kind='release', text='Windows', source_version='v1',
                                   source_hash=hashlib.sha256(b'v1 Windows').hexdigest())
        self.new['refs'][0].update(source_kind='release', text='Windows', source_version='v2',
                                   content_hash=hashlib.sha256(b'v2 Windows').hexdigest())
        ref = mergeEvidence(self.old, self.new)['refs'][0]
        self.assertTrue(ref['context_changed'])

    def test_real_seed_context_addition_withdraws_previous_qualification(self):
        import json
        from pathlib import Path
        from gitradar.content import deriveFacts, resolveContent
        root = Path(__file__).resolve().parents[1]
        previous = json.loads((root/'data/seed-evidence.json').read_text())['projects']['localsend/localsend']
        editorial = json.loads((root/'data/curation.json').read_text())['projects']['localsend/localsend']
        originalEditorial = copy.deepcopy(editorial)
        oldRefs = [ref for ref in previous['refs'] if ref['source_kind'] == 'readme']
        text = '\n'.join(ref['text'] for ref in oldRefs) + '\nRequires a paid account to transfer files.'
        source = {'id': 'readme:current', 'url': oldRefs[0]['url'], 'source_kind': 'readme',
                  'text': text, 'content_hash': hashlib.sha256(text.encode()).hexdigest(),
                  'checked_at': '2026-10-20T20:00:00Z', 'status': 200}
        merged = mergeEvidence(previous, {'refs': [source]})
        content = resolveContent(deriveFacts(merged), editorial, '2026-10-20T20:00:00Z')
        self.assertEqual(content['effective_status'], 'review_required')
        self.assertFalse(content['eligibility']['eligible'])
        self.assertIn('context_changed:intro', content['invalidation_reasons'])
        self.assertEqual(editorial, originalEditorial)

    def test_unchanged_official_document_span_preserves_reviewed_hash_and_context(self):
        text = 'License document header\nOriginal license grant.\nEnd of document.'
        digest = hashlib.sha256(text.encode()).hexdigest()
        self.old['refs'][0].update(source_kind='official_document', text='Original license grant.', source_hash=digest)
        self.new['refs'][0].update(source_kind='official_document', text=text, content_hash=digest)
        ref = mergeEvidence(self.old, self.new)['refs'][0]
        self.assertEqual(ref['content_hash'], 'original')
        self.assertEqual(ref['text'], 'Original license grant.')
        self.assertFalse(ref.get('context_changed'))
        changed = copy.deepcopy(self.new)
        changed['refs'][0]['text'] += '\nRequires a paid account.'
        changed['refs'][0]['content_hash'] = hashlib.sha256(changed['refs'][0]['text'].encode()).hexdigest()
        guarded = mergeEvidence(self.old, changed)['refs'][0]
        self.assertTrue(guarded['context_changed'])
        self.assertEqual(guarded['content_hash'], 'original')

    def test_repository_license_document_cannot_match_root_metadata(self):
        self.old['refs'][0].update(source_kind='repository', url='https://api.github.com/repos/o/a/license',
                                   text='License title.', source_hash=hashlib.sha256(b'License title.\nGrant.').hexdigest())
        self.new['refs'][0].update(source_kind='repository', url='https://api.github.com/repos/o/a',
                                   text='{"license": "MIT"}')
        ref = mergeEvidence(self.old, self.new)['refs'][0]
        self.assertEqual(ref['content_hash'], 'original')
        self.assertEqual(ref['checked_at'], '2026-10-01T00:00:00Z')
        actual = copy.deepcopy(self.new)
        actual['refs'][0].update(url=self.old['refs'][0]['url'], text='License title.\nGrant.')
        actual['refs'][0]['content_hash'] = hashlib.sha256(actual['refs'][0]['text'].encode()).hexdigest()
        refreshed = mergeEvidence(self.old, actual)['refs'][0]
        self.assertEqual(refreshed['content_hash'], 'original')
        self.assertFalse(refreshed.get('context_changed'))

    def test_confirmed_source_identity_flag_is_merged_without_losing_prior_unknowns(self):
        self.old['critical_unknowns'] = ['account_review']
        self.new['critical_unknowns'] = ['identity_conflict']
        merged = mergeEvidence(self.old, self.new)
        self.assertEqual(set(merged['critical_unknowns']), {'account_review', 'identity_conflict'})
        ordinarySuccess = copy.deepcopy(self.new)
        ordinarySuccess['critical_unknowns'] = []
        later = mergeEvidence(merged, ordinarySuccess)
        self.assertIn('identity_conflict', later['critical_unknowns'])
        self.assertIn('account_review', later['critical_unknowns'])

    def test_identity_change_does_not_clear_an_independent_context_change(self):
        self.old['critical_unknowns'] = ['identity_conflict']
        self.old['refs'][0].update(context_changed=True, source_hash='same-source')
        self.new['refs'][0]['content_hash'] = 'same-source'
        merged = mergeEvidence(self.old, self.new)
        self.assertTrue(merged['refs'][0]['context_changed'])
        self.assertIn('identity_conflict', merged['critical_unknowns'])

    def multiPathInput(self):
        paths = [{'url': 'https://official.example/first'}, {'url': 'https://official.example/second'}]
        project = {'full_name': 'o/a', 'content': {'official_urls': ['https://official.example'],
                   'usage_paths': paths, 'claims': {'usage_paths': ['intro']}}}
        return project, {'projects': {'o/a': copy.deepcopy(self.old)}}

    def test_second_path_404_blocks_shared_claim_instead_of_inheriting_first_success(self):
        project, evidence = self.multiPathInput()
        statuses = [200, 404]
        client = GitHubClient(transport=lambda *args: HttpResponse(statuses.pop(0), {}, None))
        result = refreshPaths([project], evidence, client, Budget(), '2026-10-20T00:00:00Z')
        ref = result['projects']['o/a']['refs'][0]
        self.assertEqual(client.usage.path_requests, 2)
        self.assertEqual(ref['path_checks']['https://official.example/first']['status'], 200)
        self.assertEqual(ref['path_checks']['https://official.example/second']['status'], 404)
        self.assertEqual(ref['path_status'], 404)

    def test_second_path_budget_deferred_does_not_inherit_first_clock(self):
        project, evidence = self.multiPathInput()
        evidence['projects']['o/a']['refs'][0]['path_checked_at'] = '2026-10-01T00:00:00Z'
        client = GitHubClient(transport=lambda *args: HttpResponse(200, {}, None))
        result = refreshPaths([project], evidence, client, Budget(path_requests=1), '2026-10-20T00:00:00Z')
        ref = result['projects']['o/a']['refs'][0]
        self.assertEqual(client.usage.path_requests, 1)
        self.assertEqual(ref['path_checked_at'], '2026-10-01T00:00:00Z')
        self.assertNotEqual(ref['path_checks']['https://official.example/second']['status'], 200)

if __name__ == '__main__':
    unittest.main()
