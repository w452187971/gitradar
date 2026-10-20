import copy
import hashlib
import unittest

from gitradar.content import deriveFacts, resolveContent
from gitradar.evidence import mergeEvidence
from gitradar.github_client import GitHubClient, HttpResponse
from gitradar.models import Budget
from gitradar.sources import SourceRequest, visibleSourceText
from test_v4_content import NOW, sampleContent


HTML = ('<h1>Download</h1><p>Requires <a href="/msvc">MSVC</a> Redistributable.</p>'
        '<p>No account required.</p>')
TEXT = 'Download\nRequires MSVC Redistributable.\nNo account required.'


class SourceNormalizationTests(unittest.TestCase):
    def test_inline_elements_preserve_seed_sentence_and_spaces(self):
        self.assertEqual(visibleSourceText(HTML, 'text/html'), TEXT)

    def test_blocks_and_original_newlines_match_seed_v1(self):
        html = '<div> One <b>two</b>  three\n four </div><h2>Five</h2><ul><li>Six</li></ul>'
        self.assertEqual(visibleSourceText(html, 'text/html'), 'One two  three\nfour\nFive\nSix')

    def test_html_entities_and_utf8_preserve_visible_words(self):
        html = '<p>中文 <a>A&amp;B</a> &#x2014; 安装</p>'.encode()
        self.assertEqual(visibleSourceText(html, 'text/html; charset=utf-8'), '中文 A&B — 安装')

    def test_script_style_are_excluded_without_losing_surrounding_text(self):
        html = '<p>Requires <script>bad()</script><style>.bad{}</style>an account.</p>'
        self.assertEqual(visibleSourceText(html, 'text/html'), 'Requires an account.')

    def test_plain_text_is_not_renormalized(self):
        text = '  README\n\nRequires two  spaces.\n'
        self.assertEqual(visibleSourceText(text, 'text/plain'), text)

    def test_seed_v1_can_be_selected_and_unknown_versions_fail_closed(self):
        self.assertEqual(visibleSourceText(HTML, 'text/html', 'seed_v1'), TEXT)
        with self.assertRaises(ValueError):
            visibleSourceText(HTML, 'text/html', 'future_version')

    def reviewedBundle(self):
        facts, editorial = sampleContent()
        refs = copy.deepcopy(facts['evidence_refs'])
        for ref in refs:
            ref.update(url='https://official.example/download', source_kind='official_site',
                       text='Requires MSVC Redistributable.',
                       source_hash=hashlib.sha256(TEXT.encode()).hexdigest())
        bundle = {'full_name': 'demo/search', 'node_id': 'R1', 'refs': refs,
                  'official_urls': ['https://official.example'],
                  'facts': {key: {'value': editorial[key], 'ref_ids': [key], 'complete': True}
                            for key in editorial['claims']}}
        editorial['official_urls'] = bundle['official_urls']
        return bundle, editorial

    def refresh(self, bundle, html):
        def transport(method, url, headers, body):
            self.assertEqual(method, 'GET')
            self.assertEqual(url, 'https://official.example/download')
            self.assertNotIn('Authorization', headers)
            return HttpResponse(200, {'Content-Type': 'text/html'}, html)
        client = GitHubClient(token=None, transport=transport, now=lambda: NOW)
        source = SourceRequest('https://official.example/download',
                               'https://official.example/download', 'official_site', True,
                               bundle['refs'])
        refs = client.readEvidenceSource(source, bundle, Budget(), {})
        return mergeEvidence(bundle, {'refs': refs})

    def test_unchanged_inline_html_keeps_reviewed_eligibility(self):
        bundle, editorial = self.reviewedBundle()
        original = copy.deepcopy(editorial)
        self.assertTrue(resolveContent(deriveFacts(bundle), editorial, NOW)['eligibility']['eligible'])
        merged = self.refresh(bundle, HTML)
        content = resolveContent(deriveFacts(merged), editorial, NOW)
        self.assertTrue(content['eligibility']['eligible'], content['invalidation_reasons'])
        for old in bundle['refs']:
            current = next(ref for ref in merged['refs'] if ref['id'] == old['id'])
            self.assertEqual(current['source_hash'], old['source_hash'])
            self.assertEqual(current['content_hash'], old['content_hash'])
            self.assertFalse(current.get('context_changed'))
        self.assertEqual(editorial, original)

    def test_added_account_or_payment_still_withdraws_same_fragment(self):
        for condition in ('Requires a paid subscription.', 'Requires an account.'):
            with self.subTest(condition=condition):
                bundle, editorial = self.reviewedBundle()
                merged = self.refresh(bundle, HTML + '<p>' + condition + '</p>')
                content = resolveContent(deriveFacts(merged), editorial, NOW)
                self.assertFalse(content['eligibility']['eligible'])
                self.assertIn('context_changed:prerequisites', content['invalidation_reasons'])
                current = next(ref for ref in merged['refs'] if ref['id'] == 'prerequisites')
                self.assertEqual(current['content_hash'], editorial['evidence_hashes']['prerequisites'])
                self.assertNotEqual(current['source_hash'], bundle['refs'][0]['source_hash'])
