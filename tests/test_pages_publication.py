"""Pages 成功必须由同 SHA built 证明，所有 HTTP 均离线替身。"""
import importlib.util
import io
import contextlib
import os
import tempfile
import json
from pathlib import Path
import unittest
import urllib.error
import urllib.request
from unittest.mock import patch

SHA = 'a' * 40
OTHER = 'b' * 40
BASE = '/repos/owner/repo'


def loadPublisher():
    path = Path('scripts/publish_pages.py')
    if not path.exists():
        raise AssertionError('Production Pages publisher is missing')
    spec = importlib.util.spec_from_file_location('pages_publisher', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class PagesPublicationTests(unittest.TestCase):
    def setUp(self):
        self.publisher = loadPublisher()
        self.calls = []
        self.heads = [SHA]
        self.builds = [{'status': 'built', 'commit': OTHER}]
        self.postError = None

    def request(self, method, path):
        self.calls.append((method, path))
        if path == BASE:
            return {'default_branch': 'main'}
        if path == BASE + '/pages':
            return {'build_type': 'legacy', 'source': {'branch': 'main', 'path': '/'}}
        if path == BASE + '/branches/main':
            return {'commit': {'sha': self.heads.pop(0) if len(self.heads) > 1 else self.heads[0]}}
        if path == BASE + '/pages/builds' and method == 'POST':
            if self.postError:
                raise self.postError
            return {'status': 'queued', 'url': 'https://evil.invalid/never-follow'}
        if path == BASE + '/pages/builds/latest':
            return self.builds.pop(0) if len(self.builds) > 1 else self.builds[0]
        raise AssertionError('Unexpected publication request')

    def publish(self, branch='refs/heads/main', maxPolls=3):
        return self.publisher.publishPages('owner/repo', branch, SHA, self.request,
                                           sleep=lambda seconds: None, maxPolls=maxPolls)

    def test_non_main_rejected_before_network(self):
        with self.assertRaisesRegex(ValueError, 'main'):
            self.publish('refs/heads/codex/dev')
        self.assertEqual(self.calls, [])

    def test_sha_mismatch_prevents_post(self):
        self.heads = [OTHER]
        with self.assertRaisesRegex(RuntimeError, 'SHA'):
            self.publish()
        self.assertNotIn(('POST', BASE + '/pages/builds'), self.calls)

    def test_queue_then_matching_built_posts_exactly_once(self):
        self.builds = [{'status': 'built', 'commit': OTHER}, {'status': 'queued'},
                       {'status': 'building', 'commit': SHA}, {'status': 'built', 'commit': SHA}]
        result = self.publish()
        self.assertEqual(result['commit'], SHA)
        self.assertEqual(result['status'], 'built')
        self.assertEqual(self.calls.count(('POST', BASE + '/pages/builds')), 1)
        self.assertFalse(any('evil' in path for _, path in self.calls))

    def test_already_built_requires_current_head_and_skips_post(self):
        self.builds = [{'status': 'built', 'commit': SHA}]
        self.assertEqual(self.publish()['status'], 'built')
        self.assertNotIn(('POST', BASE + '/pages/builds'), self.calls)

    def test_foreign_built_never_becomes_success_and_polling_is_bounded(self):
        with self.assertRaisesRegex(RuntimeError, 'not built'):
            self.publish()
        self.assertEqual(self.calls.count(('GET', BASE + '/pages/builds/latest')), 4)
        self.assertEqual(self.calls.count(('POST', BASE + '/pages/builds')), 1)

    def test_queued_acceptance_alone_is_failure_after_limit(self):
        self.builds = [{'status': 'queued'}]
        with self.assertRaisesRegex(RuntimeError, 'not built'):
            self.publish(maxPolls=1)

    def test_main_changes_after_request_cannot_report_success(self):
        self.heads = [SHA, SHA, OTHER]
        self.builds = [{'status': 'built', 'commit': OTHER}, {'status': 'built', 'commit': SHA}]
        with self.assertRaisesRegex(RuntimeError, 'SHA'):
            self.publish()

    def test_failed_target_build_exits_without_second_post(self):
        self.builds = [{'status': 'built', 'commit': OTHER},
                       {'status': 'errored', 'commit': SHA, 'error': {'message': 'Build failed'}}]
        with self.assertRaisesRegex(RuntimeError, 'failed'):
            self.publish()
        self.assertEqual(self.calls.count(('POST', BASE + '/pages/builds')), 1)

    def test_http_post_failure_never_retries(self):
        self.postError = RuntimeError('HTTP 403')
        with self.assertRaisesRegex(RuntimeError, 'HTTP 403'):
            self.publish()
        self.assertEqual(self.calls.count(('POST', BASE + '/pages/builds')), 1)

    def test_wrong_default_branch_or_pages_source_prevents_post(self):
        for badPath, badData in [(BASE, {'default_branch': 'dev'}),
                                 (BASE + '/pages', {'source': {'branch': 'dev', 'path': '/'}})]:
            with self.subTest(path=badPath):
                def request(method, path):
                    return badData if path == badPath else self.request(method, path)
                with self.assertRaisesRegex(RuntimeError, 'configuration'):
                    self.publisher.publishPages('owner/repo', 'refs/heads/main', SHA, request)
                self.assertNotIn(('POST', BASE + '/pages/builds'), self.calls)

    def test_http_errors_are_sanitized_and_never_retried(self):
        error = urllib.error.HTTPError('https://api.github.com', 403, 'secret-token', {}, None)
        with patch('urllib.request.OpenerDirector.open', side_effect=error) as opening:
            client = self.publisher.PagesClient('secret-token')
            with self.assertRaisesRegex(RuntimeError, '^GitHub API HTTP 403$'):
                client.request('POST', BASE + '/pages/builds')
            self.assertEqual(opening.call_count, 1)

    def test_redirect_never_forwards_authorization(self):
        handler = self.publisher.NoRedirect()
        request = urllib.request.Request('https://api.github.com/repos/owner/repo/pages/builds',
                                         headers={'Authorization': 'Bearer secret-token'})
        self.assertIsNone(handler.redirect_request(request, None, 302, '', {}, 'https://evil.invalid/'))

    def test_api_path_rejects_external_url_before_open(self):
        with patch('urllib.request.OpenerDirector.open') as opening:
            with self.assertRaises(ValueError):
                self.publisher.PagesClient('secret-token').request('GET', 'https://evil.invalid/')
            opening.assert_not_called()

    def test_deadline_expiry_prevents_another_http_request(self):
        with patch('urllib.request.OpenerDirector.open') as opening:
            client = self.publisher.PagesClient('secret-token')
            client.deadline = 0
            with self.assertRaisesRegex(RuntimeError, 'deadline'):
                client.request('GET', BASE + '/pages/builds/latest')
            opening.assert_not_called()

    def test_entrypoint_writes_success_only_after_verified_build(self):
        self.builds = [{'status': 'built', 'commit': SHA}]
        with tempfile.TemporaryDirectory() as directory:
            before = os.getcwd()
            try:
                os.chdir(directory)
                with patch.dict(os.environ, {'GH_API_TOKEN': 'secret-token',
                                'GITHUB_REF': 'refs/heads/main', 'GITHUB_REPOSITORY': 'owner/repo'}), \
                     patch('subprocess.check_output', return_value=SHA + '\n'), \
                     patch.object(self.publisher.PagesClient, 'request', side_effect=self.request), \
                     contextlib.redirect_stdout(io.StringIO()) as output:
                    self.assertEqual(self.publisher.main(), 0)
                report = json.loads(Path('pages-publication.json').read_text())
                self.assertEqual(report['commit'], SHA)
                self.assertEqual(report['status'], 'built')
                self.assertNotIn('secret-token', output.getvalue())
            finally:
                os.chdir(before)

    def test_api_post_requires_201_not_200(self):
        response = io.BytesIO(b'{"status":"queued"}')
        response.status = 200
        with patch('urllib.request.OpenerDirector.open', return_value=response):
            with self.assertRaisesRegex(RuntimeError, 'HTTP 200'):
                self.publisher.PagesClient('secret-token').request('POST', BASE + '/pages/builds')


if __name__ == '__main__':
    unittest.main()
