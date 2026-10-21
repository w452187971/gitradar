import copy
import hashlib
import json
from pathlib import Path
import unittest

from gitradar.content import deriveFacts, resolveContent
from gitradar.evidence import mergeEvidence
from gitradar.github_client import GitHubClient
from gitradar.sources import SourceRequest


NOW = '2026-10-21T01:23:06.724896Z'
URL = 'https://github.com/FreeTubeApp/FreeTube/releases'
FIXTURE = Path(__file__).parent / 'fixtures/freetube-navigation.json'


def digest(text):
    return hashlib.sha256(text.encode()).hexdigest()


class GithubNavigationContextTests(unittest.TestCase):
    def setUp(self):
        fixture = json.loads(FIXTURE.read_text())
        self.bundle = fixture['bundle']
        self.editorial = fixture['editorial']
        self.oldText = self.whole(self.bundle)['text']
        self.newText = self.oldText.replace('Pull requests11\xa0(11)', 'Pull requests12\xa0(12)', 1)
        self.assertEqual(digest(self.oldText), fixture['provenance']['old_full_sha256'])
        self.assertEqual(digest(self.newText), fixture['provenance']['new_full_sha256'])

    def whole(self, bundle):
        return next(ref for ref in bundle['refs'] if ref.get('section') == 'source')

    def path(self, bundle):
        return next(ref for ref in bundle['refs'] if ref['id'] == 'path')

    def fetched(self, text, previous=None):
        previous = previous or self.bundle
        olds = [ref for ref in previous['refs'] if ref.get('url') == URL]
        source = SourceRequest(URL, URL, 'official_site', True, olds)
        refs = GitHubClient(now=lambda: NOW).webEvidence(text, source, previous)
        return {'full_name': previous['full_name'], 'node_id': previous['node_id'],
                'refs': refs, 'critical_unknowns': [], 'status': 'success'}

    def content(self, bundle, editorial=None):
        return resolveContent(deriveFacts(bundle), editorial or self.editorial, NOW)

    def rebase(self, text):
        whole = self.whole(self.bundle)
        whole.update(text=text, content_hash=digest(text), source_version=digest(text),
                     id='official_site:source:' + digest(text))
        self.path(self.bundle)['source_hash'] = digest(text)

    def assertBlocked(self, fetched):
        merged = mergeEvidence(self.bundle, fetched)
        self.assertTrue(self.path(merged).get('context_changed'))
        self.assertFalse(self.content(merged)['eligibility']['eligible'])
        self.assertNotIn('navigation_equivalent_hash', self.path(merged))

    def test_real_freetube_navigation_count_does_not_revoke_reviewed_content(self):
        original = copy.deepcopy(self.bundle)
        self.assertTrue(self.content(self.bundle)['eligibility']['eligible'])
        merged = mergeEvidence(self.bundle, self.fetched(self.newText))
        self.assertTrue(self.content(merged)['eligibility']['eligible'])
        self.assertFalse(self.path(merged).get('context_changed'))
        self.assertEqual(self.path(merged)['source_hash'], digest(self.newText))
        self.assertEqual(self.path(merged)['navigation_equivalent_hash'], digest(self.oldText))
        self.assertEqual(self.path(merged)['content_hash'], self.path(self.bundle)['content_hash'])
        self.assertEqual(self.bundle, original)

    def test_increasing_decreasing_and_repeated_counts_keep_the_original_review_hash(self):
        previous = self.bundle
        for count in (12, 9, 100, 0, 0, 1):
            with self.subTest(count=count):
                text = self.oldText.replace('Pull requests11\xa0(11)', f'Pull requests{count}\xa0({count})', 1)
                previous = mergeEvidence(previous, self.fetched(text, previous))
                self.assertTrue(self.content(previous)['eligibility']['eligible'])
                self.assertEqual(self.path(previous)['source_hash'], digest(text))
                self.assertEqual(self.path(previous)['navigation_equivalent_hash'], digest(self.oldText))

    def test_body_line_named_pull_requests_is_not_a_navigation_counter(self):
        self.rebase(self.oldText + '\nPull requests11\xa0(11)')
        changed = self.whole(self.bundle)['text'].rsplit('Pull requests11\xa0(11)', 1)[0] + 'Pull requests12\xa0(12)'
        self.assertBlocked(self.fetched(changed))

    def test_added_conditions_versions_or_urls_still_revoke_even_when_fragment_remains(self):
        for addition in ('Requires a paid account.', 'Windows 12 only.', 'License changed to proprietary.',
                         'v0.26 stable release replaces Beta.', 'Download https://example.invalid/new-installer'):
            with self.subTest(addition=addition):
                self.assertIn(self.path(self.bundle)['text'], self.newText)
                self.assertBlocked(self.fetched(self.newText + '\n' + addition))

    def test_missing_or_unmatched_old_complete_source_fails_closed(self):
        for mismatch in ('missing', 'wrong_hash', 'wrong_id', 'wrong_bound_hash'):
            with self.subTest(mismatch=mismatch):
                self.setUp()
                if mismatch == 'missing':
                    self.bundle['refs'].remove(self.whole(self.bundle))
                elif mismatch == 'wrong_hash':
                    self.whole(self.bundle)['content_hash'] = '0' * 64
                elif mismatch == 'wrong_id':
                    self.whole(self.bundle)['id'] = 'official_site:fragment:' + digest(self.oldText)
                else:
                    self.path(self.bundle)['source_hash'] = '0' * 64
                self.assertBlocked(self.fetched(self.newText))

    def test_mismatched_new_full_source_url_or_missing_full_text_fails_closed(self):
        for mismatch in ('url', 'missing', 'hash'):
            with self.subTest(mismatch=mismatch):
                fetched = self.fetched(self.newText)
                whole = self.whole(fetched)
                if mismatch == 'missing':
                    fetched['refs'].remove(whole)
                elif mismatch == 'url':
                    whole['url'] = 'https://github.com/another/repository/releases'
                else:
                    whole['content_hash'] = '0' * 64
                self.assertBlocked(fetched)

    def test_identity_conflict_and_existing_context_sticky_are_never_cleared(self):
        for sticky in ('identity', 'context'):
            with self.subTest(sticky=sticky):
                self.setUp()
                fetched = self.fetched(self.newText)
                if sticky == 'identity':
                    fetched['node_id'] = 'DIFFERENT_REPOSITORY'
                else:
                    self.path(self.bundle).update(context_changed=True, previous_source_hash='original-review')
                self.assertBlocked(fetched)
                merged = mergeEvidence(self.bundle, fetched)
                if sticky == 'context':
                    self.assertEqual(self.path(merged)['previous_source_hash'], 'original-review')
                else:
                    self.assertIn('identity_conflict', merged['critical_unknowns'])

    def test_duplicate_complete_sources_and_unknown_navigation_fail_closed(self):
        for ambiguity in ('duplicate_old', 'duplicate_new', 'unknown', 'second_nav'):
            with self.subTest(ambiguity=ambiguity):
                self.setUp()
                text = self.newText
                if ambiguity == 'duplicate_old':
                    self.bundle['refs'].append(copy.deepcopy(self.whole(self.bundle)))
                elif ambiguity == 'unknown':
                    text = text.replace('Security and quality\nInsights', 'Unknown tab\nInsights', 1)
                elif ambiguity == 'second_nav':
                    text += '\nRepository navigation'
                fetched = self.fetched(text)
                if ambiguity == 'duplicate_new':
                    fetched['refs'].append(copy.deepcopy(self.whole(fetched)))
                self.assertBlocked(fetched)

    def test_explicit_context_review_must_match_the_proven_navigation_equivalence(self):
        merged = mergeEvidence(self.bundle, self.fetched(self.newText))
        editorial = copy.deepcopy(self.editorial)
        editorial['evidence_context_hashes'] = {'path': digest(self.oldText)}
        self.assertTrue(self.content(merged, editorial)['eligibility']['eligible'])
        editorial['evidence_context_hashes']['path'] = 'a-different-reviewed-source'
        self.assertFalse(self.content(merged, editorial)['eligibility']['eligible'])

    def test_existing_sticky_cannot_use_a_navigation_equivalence_to_bypass_review(self):
        merged = mergeEvidence(self.bundle, self.fetched(self.newText))
        self.path(merged)['context_changed'] = True
        editorial = copy.deepcopy(self.editorial)
        editorial['evidence_context_hashes'] = {'path': digest(self.oldText)}
        self.assertFalse(self.content(merged, editorial)['eligibility']['eligible'])

    def test_non_string_or_missing_repository_identity_does_not_prove_equivalence(self):
        for identity in (None, '', 42):
            with self.subTest(identity=identity):
                self.setUp()
                self.bundle['node_id'] = identity
                self.assertBlocked(self.fetched(self.newText))

    def test_new_body_change_after_navigation_equivalence_revokes_the_old_review(self):
        previous = mergeEvidence(self.bundle, self.fetched(self.newText))
        merged = mergeEvidence(previous, self.fetched(self.newText + '\nRequires payment.', previous))
        self.assertTrue(self.path(merged).get('context_changed'))
        self.assertNotIn('navigation_equivalent_hash', self.path(merged))
        self.assertFalse(self.content(merged)['eligibility']['eligible'])


if __name__ == '__main__':
    unittest.main()
