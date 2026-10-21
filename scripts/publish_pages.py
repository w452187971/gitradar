"""用内置令牌请求一次分支式 Pages 构建，并确认同 SHA 已 built。"""
from __future__ import annotations

import datetime as dt
import json
import os
from pathlib import Path
import re
import subprocess
import time
from typing import Callable, cast
import urllib.error
import urllib.request

JsonObject = dict[str, object]
Request = Callable[[str, str], JsonObject]
MAX_POLLS = 30
POLL_SECONDS = 20
DEADLINE_SECONDS = 600
MAX_RESPONSE_BYTES = 1024 * 1024


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req: urllib.request.Request, fp: object, code: int,
                         msg: str, headers: object, newurl: str) -> None:
        # 构建 POST 不可自动重发，认证也不随任何跳转转交。
        return None


class PagesClient:
    def __init__(self, token: str):
        if not token:
            raise ValueError('GH_API_TOKEN is required')
        self.token = token
        self.deadline = time.monotonic() + DEADLINE_SECONDS

    def request(self, method: str, path: str) -> JsonObject:
        route = r'/repos/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+(?:/pages(?:/builds(?:/latest)?)?|/branches/main)?'
        if not re.fullmatch(route, path) or method not in ('GET', 'POST'):
            raise ValueError('Only fixed GitHub API publication endpoints are accepted')
        if method == 'POST' and not path.endswith('/pages/builds'):
            raise ValueError('Only a Pages build may be requested')
        remaining = self.deadline - time.monotonic()
        if remaining <= 0:
            raise RuntimeError('Pages publication deadline exceeded')
        request = urllib.request.Request('https://api.github.com' + path, method=method,
            data=b'' if method == 'POST' else None,
            headers={'Authorization': 'Bearer ' + self.token, 'Accept': 'application/vnd.github+json',
                     'X-GitHub-Api-Version': '2026-03-10', 'User-Agent': 'GitRadar-Pages'})
        return self._exchange(request, min(30, remaining), 201 if method == 'POST' else 200)

    def _exchange(self, request: urllib.request.Request, timeout: float, expected: int) -> JsonObject:
        try:
            with urllib.request.build_opener(NoRedirect()).open(request, timeout=timeout) as response:
                if response.status != expected:
                    raise RuntimeError(f'GitHub API HTTP {response.status}')
                raw = response.read(MAX_RESPONSE_BYTES + 1)
        except urllib.error.HTTPError as error:
            raise RuntimeError(f'GitHub API HTTP {error.code}') from None
        except (OSError, TimeoutError) as error:
            raise RuntimeError('GitHub API transport failed: ' + type(error).__name__) from None
        if time.monotonic() > self.deadline:
            raise RuntimeError('Pages publication deadline exceeded')
        if len(raw) > MAX_RESPONSE_BYTES:
            raise RuntimeError('GitHub API response exceeds limit')
        try:
            payload = json.loads(raw)
        except (ValueError, UnicodeError):
            raise RuntimeError('GitHub API returned invalid JSON') from None
        if not isinstance(payload, dict):
            raise RuntimeError('GitHub API response must be an object')
        return cast(JsonObject, payload)


def record(value: object) -> JsonObject:
    return cast(JsonObject, value) if isinstance(value, dict) else {}


def checkHead(request: Request, base: str, expectedSha: str) -> None:
    actual = record(request('GET', base + '/branches/main').get('commit')).get('sha')
    if actual != expectedSha:
        raise RuntimeError('Remote main SHA differs from the publication SHA')


def checkConfiguration(request: Request, base: str) -> None:
    if request('GET', base).get('default_branch') != 'main':
        raise RuntimeError('Pages configuration requires main as default branch')
    site = request('GET', base + '/pages')
    if (site.get('build_type') != 'legacy'
            or record(site.get('source')) != {'branch': 'main', 'path': '/'}):
        raise RuntimeError('Pages configuration must remain legacy main:/')


def matchingBuild(build: JsonObject, expectedSha: str) -> bool:
    if build.get('commit') != expectedSha:
        return False
    if build.get('status') in ('errored', 'error', 'failed', 'cancelled'):
        raise RuntimeError('Pages build failed for the publication SHA')
    return build.get('status') == 'built'


def publishPages(repository: str, branch: str, expectedSha: str, request: Request,
                 sleep: Callable[[float], None] = time.sleep, maxPolls: int = MAX_POLLS) -> JsonObject:
    if branch != 'refs/heads/main':
        raise ValueError('Pages publication is only allowed on main')
    if not re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+', repository):
        raise ValueError('Invalid GitHub repository')
    if not re.fullmatch(r'[0-9a-f]{40}', expectedSha) or not 1 <= maxPolls <= MAX_POLLS:
        raise ValueError('Invalid publication SHA or polling limit')
    base = '/repos/' + repository
    checkConfiguration(request, base)
    checkHead(request, base, expectedSha)
    latest = request('GET', base + '/pages/builds/latest')
    # 旧失败可以重新请求一次构建；已构建同一 SHA 则无需重复提交。
    if latest.get('status') == 'built' and latest.get('commit') == expectedSha:
        checkHead(request, base, expectedSha)
        return {'status': 'built', 'commit': expectedSha, 'requested': False, 'polls': 0}
    checkHead(request, base, expectedSha)
    accepted = request('POST', base + '/pages/builds')
    if accepted.get('status') not in ('queued', 'building', 'built'):
        raise RuntimeError('Pages build request did not return an accepted state')
    return waitForBuild(request, base, expectedSha, sleep, maxPolls)


def waitForBuild(request: Request, base: str, expectedSha: str,
                 sleep: Callable[[float], None], maxPolls: int) -> JsonObject:
    for attempt in range(maxPolls):
        checkHead(request, base, expectedSha)
        latest = request('GET', base + '/pages/builds/latest')
        if matchingBuild(latest, expectedSha):
            checkHead(request, base, expectedSha)
            return {'status': 'built', 'commit': expectedSha, 'requested': True, 'polls': attempt + 1}
        if attempt + 1 < maxPolls:
            sleep(POLL_SECONDS)
    raise RuntimeError('Publication SHA not built within the bounded polling window')


def main() -> int:
    report: JsonObject = {'status': 'failed', 'checked_at': dt.datetime.now(dt.timezone.utc).isoformat()}
    try:
        sha = subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip()
        client = PagesClient(os.environ.get('GH_API_TOKEN', ''))
        report['commit'] = sha
        report.update(publishPages(os.environ.get('GITHUB_REPOSITORY', ''),
                      os.environ.get('GITHUB_REF', ''), sha, client.request))
    except (OSError, ValueError, RuntimeError, subprocess.CalledProcessError) as error:
        report['error'] = str(error)
    report['checked_at'] = dt.datetime.now(dt.timezone.utc).isoformat()
    Path('pages-publication.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report))
    return 0 if report['status'] == 'built' else 1


if __name__ == '__main__':
    raise SystemExit(main())
