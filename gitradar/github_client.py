"""串行、有预算上界的 GitHub 客户端，不读取环境变量或个人凭据。"""
from __future__ import annotations

import base64
import datetime as dt
import hashlib
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import asdict, dataclass
from typing import Callable, Optional, cast

from .models import Budget, EvidenceBundle, EvidenceRef, Observation, ObservationBatch, RepositoryRef, Usage

API_ROOT = 'https://api.github.com'
NODE_FIELDS = ('id nameWithOwner stargazerCount createdAt isArchived isFork url description pushedAt '
               'primaryLanguage { name } repositoryTopics(first: 20) { nodes { topic { name } } }')


class BudgetExceeded(RuntimeError):
    """本轮已无法安全发出请求。"""


@dataclass
class HttpResponse:
    status: int
    headers: dict[str, str]
    body: object


Transport = Callable[[str, str, dict[str, str], Optional[bytes]], HttpResponse]


def utcNow() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat().replace('+00:00', 'Z')


def httpTransport(method: str, url: str, headers: dict[str, str], body: Optional[bytes]) -> HttpResponse:
    request = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        response = urllib.request.urlopen(request, timeout=35)
    except urllib.error.HTTPError as error:
        response = error
    with response:
        raw = response.read()
        try:
            payload = json.loads(raw) if raw else None
        except (ValueError, UnicodeDecodeError) as error:
            raise ValueError('GitHub returned invalid JSON.') from error
        return HttpResponse(response.status, dict(response.headers.items()), payload)


def integerHeader(headers: dict[str, str], name: str) -> Optional[int]:
    try:
        value = int(headers[name])
        return max(0, value)
    except (KeyError, ValueError):
        return None


class GitHubClient:
    def __init__(self, token: Optional[str] = None, transport: Transport = httpTransport,
                 now: Callable[[], str] = utcNow, sleep: Callable[[float], None] = time.sleep):
        self.token, self.transport, self.now, self.sleep = token, transport, now, sleep
        self.usage = Usage()
        self.lastHeaders: dict[str, str] = {}

    def headers(self) -> dict[str, str]:
        headers = {'Accept': 'application/vnd.github+json', 'User-Agent': 'GitRadar-V4'}
        if self.token:
            headers['Authorization'] = 'Bearer ' + self.token
        return headers

    def checkBudget(self, budget: Budget, category: str) -> None:
        if category not in ('search', 'content', 'path', 'identity', 'graphql'):
            raise ValueError('Unknown request budget category.')
        usage = self.usage
        if usage.rate_limited:
            raise BudgetExceeded('GitHub rate limited this client; wait for a new run.')
        remaining = getattr(usage, category + '_remaining', None)
        if category in ('content', 'path', 'identity'):
            remaining = usage.rest_remaining
        floor = 0 if category == 'search' else budget.minimum_remaining
        if remaining is not None and remaining <= floor:
            raise BudgetExceeded('GitHub response-header reserve reached.')
        if category == 'graphql':
            if (usage.graphql_points >= budget.graphql_points or usage.graphql_batches >= budget.graphql_batches
                    or usage.graphql_unmeasured_requests):
                raise BudgetExceeded('GraphQL soft budget reached.')
            return
        if getattr(usage, category + '_requests') >= getattr(budget, category + '_requests'):
            raise BudgetExceeded(category + ' request budget reached.')
        if category != 'search' and usage.rest_requests >= budget.rest_requests:
            raise BudgetExceeded('Total non-search REST budget reached.')

    def charge(self, category: str, retry: bool) -> None:
        if category == 'graphql':
            self.usage.graphql_batches += 1
        else:
            field = category + '_requests'
            setattr(self.usage, field, getattr(self.usage, field) + 1)
            if category != 'search':
                self.usage.rest_requests += 1
        self.usage.retries += int(retry)

    def readHeaders(self, response: HttpResponse, category: str) -> None:
        headers = {key.lower(): value for key, value in response.headers.items()}
        self.lastHeaders = headers
        remaining = integerHeader(headers, 'x-ratelimit-remaining')
        resource = headers.get('x-ratelimit-resource', category)
        field = 'search_remaining' if resource == 'search' else (
            'graphql_remaining' if resource == 'graphql' or category == 'graphql' else 'rest_remaining')
        if remaining is not None:
            setattr(self.usage, field, remaining)
        self.usage.reset_at = integerHeader(headers, 'x-ratelimit-reset')
        self.usage.retry_after = integerHeader(headers, 'retry-after')
        if response.status in (403, 429):
            self.usage.rate_limited = True

    def exchange(self, method: str, url: str, body: Optional[bytes], budget: Budget,
                 category: str, headers: dict[str, str]) -> HttpResponse:
        for attempt in range(budget.max_retries + 1):
            self.checkBudget(budget, category)
            self.charge(category, attempt > 0)
            try:
                response = self.transport(method, url, headers, body)
            except (OSError, TimeoutError, ValueError):
                if category == 'graphql':
                    self.usage.graphql_unmeasured_requests += 1
                    raise
                if attempt == budget.max_retries:
                    raise
                self.sleep(min(2 ** attempt, 8))
                continue
            self.readHeaders(response, category)
            if category == 'graphql' or response.status < 500 or attempt == budget.max_retries:
                return response
            self.sleep(min(2 ** attempt, 8))
        raise RuntimeError('Retry loop exhausted.')

    def authScope(self) -> str:
        return hashlib.sha256((self.token or '').encode()).hexdigest()

    def requestRest(self, path: str, budget: Budget, category: str = 'content',
                    cache: Optional[dict[str, object]] = None, identity: Optional[str] = None) -> object:
        url = path if path.startswith('https://') else API_ROOT + path
        parsed = urllib.parse.urlparse(url)
        if parsed.scheme != 'https' or parsed.netloc != 'api.github.com':
            raise ValueError('Only the GitHub API origin is accepted.')
        if parsed.path.startswith('/search/'):
            category = 'search'
        elif category == 'search':
            raise ValueError('Search budget cannot be used for non-search endpoints.')
        headers, cached = self.headers(), (cache or {}).get(url)
        entry = cast(dict[str, object], cached) if isinstance(cached, dict) else {}
        reusable = bool(self.token and identity and entry.get('identity') == identity and
                        entry.get('authenticated') and entry.get('auth_scope') == self.authScope())
        if reusable and isinstance(entry.get('etag'), str):
            headers['If-None-Match'] = cast(str, entry['etag'])
        response = self.exchange('GET', url, None, budget, category, headers)
        if response.status == 304:
            if not reusable or 'If-None-Match' not in headers or 'body' not in entry:
                raise ValueError('304 has no authenticated identity-matching cache.')
            self.usage.not_modified += 1
            return entry['body']
        if response.status != 200:
            raise ValueError(f'GitHub REST HTTP {response.status}.')
        if cache is not None and self.lastHeaders.get('etag'):
            cache[url] = {'etag': self.lastHeaders['etag'], 'identity': identity,
                          'authenticated': bool(self.token), 'auth_scope': self.authScope(), 'body': response.body}
        return response.body

    def graphql(self, refs: list[RepositoryRef], budget: Budget) -> dict[str, object]:
        if all(ref.get('node_id') for ref in refs):
            ids = json.dumps([ref['node_id'] for ref in refs])
            selection = f'nodes(ids: {ids}) {{ ... on Repository {{ {NODE_FIELDS} }} }}'
        else:
            selection = ' '.join(self.repositoryQuery(index, ref) for index, ref in enumerate(refs))
        query = '{ ' + selection + ' rateLimit { cost remaining resetAt } }'
        response = self.exchange('POST', API_ROOT + '/graphql', json.dumps({'query': query}).encode(),
                                 budget, 'graphql', self.headers())
        if response.status != 200 or not isinstance(response.body, dict):
            self.usage.graphql_unmeasured_requests += 1
            raise ValueError(f'GitHub GraphQL HTTP {response.status}.')
        payload = cast(dict[str, object], response.body)
        data = payload.get('data')
        rate = data.get('rateLimit') if isinstance(data, dict) else None
        if not isinstance(rate, dict) or type(rate.get('cost')) is not int or rate['cost'] < 0:
            self.usage.graphql_unmeasured_requests += 1
        if isinstance(rate, dict):
            cost, remaining = rate.get('cost'), rate.get('remaining')
            if type(cost) is int and cost >= 0:
                self.usage.graphql_points += cost
            if type(remaining) is int and remaining >= 0:
                self.usage.graphql_remaining = remaining
        errors = payload.get('errors')
        if isinstance(errors, list) and any(isinstance(error, dict) and
                (error.get('type') in ('RATE_LIMITED', 'RATE_LIMIT') or
                 'rate limit' in str(error.get('message', '')).lower()) for error in errors):
            self.usage.rate_limited = True
        return payload

    def repositoryQuery(self, index: int, ref: RepositoryRef) -> str:
        if ref.get('node_id'):
            return f'r{index}: node(id: {json.dumps(ref["node_id"])}) {{ ... on Repository {{ {NODE_FIELDS} }} }}'
        owner, separator, name = ref['full_name'].partition('/')
        if not separator or not owner or not name or '/' in name:
            raise ValueError('Repository name must contain owner/name.')
        return f'r{index}: repository(owner: {json.dumps(owner)}, name: {json.dumps(name)}) {{ {NODE_FIELDS} }}'

    def fetchObservations(self, refs: list[RepositoryRef], budget: Budget) -> ObservationBatch:
        observations: list[Observation] = []
        errors: list[str] = []
        observedAt = self.now()
        for offset in range(0, len(refs), 50):
            group = refs[offset:offset + 50]
            try:
                payload = self.graphql(group, budget)
                observations.extend(self.parseBatch(group, payload))
                if payload.get('errors'):
                    errors.append(json.dumps(payload['errors'], ensure_ascii=False))
            except (OSError, ValueError, BudgetExceeded) as error:
                status = 'deferred' if isinstance(error, BudgetExceeded) else 'failed'
                observations.extend(self.failedObservation(ref, str(error), status) for ref in group)
                errors.append(str(error))
        return {'observations': observations, 'observed_at': observedAt,
                'errors': errors, 'usage': cast(dict[str, object], asdict(self.usage))}

    def fetchRestObservations(self, refs: list[RepositoryRef], budget: Budget,
                              cache: Optional[dict[str, object]] = None) -> ObservationBatch:
        observations: list[Observation] = []
        errors: list[str] = []
        observedAt = self.now()
        for ref in refs:
            try:
                path = '/repos/' + urllib.parse.quote(ref['full_name'], safe='/')
                payload = self.requestRest(path, budget, 'identity', cache, ref.get('node_id'))
                observations.append(self.parseRestObservation(ref, payload))
            except (OSError, ValueError, BudgetExceeded) as error:
                status = 'deferred' if isinstance(error, BudgetExceeded) else 'failed'
                observations.append(self.failedObservation(ref, str(error), status))
                errors.append(str(error))
        return {'observations': observations, 'observed_at': observedAt,
                'errors': errors, 'usage': cast(dict[str, object], asdict(self.usage))}

    def parseRestObservation(self, ref: RepositoryRef, payload: object) -> Observation:
        if not isinstance(payload, dict):
            raise ValueError('Repository REST response must be an object.')
        observation = self.parseNode(ref, {'id': payload.get('node_id'),
            'nameWithOwner': payload.get('full_name'), 'stargazerCount': payload.get('stargazers_count'),
            'createdAt': payload.get('created_at'), 'isArchived': payload.get('archived'),
            'isFork': payload.get('fork'), 'url': payload.get('html_url'),
            'description': payload.get('description'), 'pushedAt': payload.get('pushed_at'),
            'primaryLanguage': {'name': payload.get('language')}})
        topics = payload.get('topics')
        observation['topics'] = [item for item in topics if isinstance(item, str)] if isinstance(topics, list) else []
        return observation

    def parseBatch(self, refs: list[RepositoryRef], payload: dict[str, object]) -> list[Observation]:
        data = payload.get('data')
        if not isinstance(data, dict):
            return [self.failedObservation(ref, 'GraphQL returned no data.') for ref in refs]
        nodes = data.get('nodes')
        byId = {node['id']: node for node in nodes if isinstance(node, dict) and isinstance(node.get('id'), str)} \
            if isinstance(nodes, list) else {}
        result: list[Observation] = []
        for index, ref in enumerate(refs):
            node = byId.get(ref.get('node_id')) if isinstance(nodes, list) else data.get('r' + str(index))
            try:
                result.append(self.parseNode(ref, node))
            except ValueError as error:
                result.append(self.failedObservation(ref, str(error)))
        return result

    def parseNode(self, ref: RepositoryRef, value: object) -> Observation:
        if not isinstance(value, dict) or not isinstance(value.get('id'), str):
            raise ValueError('Missing GraphQL repository node.')
        if ref.get('node_id') and ref['node_id'] != value['id']:
            raise ValueError('GraphQL node identity mismatch.')
        if type(value.get('stargazerCount')) is not int or value['stargazerCount'] < 0:
            raise ValueError('Invalid observed Star count.')
        if not isinstance(value.get('nameWithOwner'), str) or not isinstance(value.get('createdAt'), str):
            raise ValueError('Missing repository name or creation date.')
        language = value.get('primaryLanguage')
        topics = value.get('repositoryTopics', {})
        topicNodes = topics.get('nodes', []) if isinstance(topics, dict) else []
        observation: Observation = {'full_name': value['nameWithOwner'], 'node_id': value['id'],
            'created_at': value['createdAt'], 'observed_at': self.now(), 'status': 'success',
            'stargazers_count': value['stargazerCount'], 'archived': value.get('isArchived') is True,
            'fork': value.get('isFork') is True, 'html_url': value.get('url', ''),
            'description': value.get('description') or '', 'pushed_at': value.get('pushedAt'),
            'language': language.get('name') if isinstance(language, dict) else None,
            'topics': [n['topic']['name'] for n in topicNodes if isinstance(n, dict) and
                       isinstance(n.get('topic'), dict) and isinstance(n['topic'].get('name'), str)]}
        if ref.get('history_key'):
            observation['history_key'] = ref['history_key']
        return observation

    def failedObservation(self, ref: RepositoryRef, reason: str, status: str = 'failed') -> Observation:
        observation = cast(Observation, dict(ref))
        observation.update(observed_at=self.now(), status=status, error=reason)
        return observation

    def readProjectEvidence(self, ref: RepositoryRef, previousEvidence: Optional[EvidenceBundle],
                            budget: Budget) -> EvidenceBundle:
        previous = previousEvidence or {}
        cache = dict(previous.get('cache', {})) if previous.get('node_id') == ref.get('node_id') else {}
        refs: list[EvidenceRef] = []
        errors: list[str] = []
        for suffix, kind in [('readme', 'readme'), ('releases/latest', 'release'), ('', 'repository')]:
            try:
                path = '/repos/' + urllib.parse.quote(ref['full_name'], safe='/') + ('/' + suffix if suffix else '')
                payload = self.requestRest(path, budget, 'content', cache, ref.get('node_id'))
                if kind == 'repository' and isinstance(payload, dict) and ref.get('node_id') != payload.get('node_id'):
                    raise ValueError('Evidence repository identity changed.')
                refs.extend(self.evidenceRefs(payload, kind, ref))
            except (OSError, ValueError, BudgetExceeded) as error:
                errors.append(f'{kind}: {error}')
                if previous.get('node_id') == ref.get('node_id'):
                    refs.extend(old for old in previous.get('refs', []) if old.get('source_kind') == kind)
        return {'full_name': ref['full_name'], 'node_id': ref.get('node_id', ''), 'refs': refs,
                'cache': cache, 'errors': errors, 'status': 'partial' if refs and errors else
                ('success' if refs else 'failed')}

    def evidenceRefs(self, payload: object, kind: str, ref: RepositoryRef) -> list[EvidenceRef]:
        if not isinstance(payload, dict):
            raise ValueError('Official evidence response must be an object.')
        if kind == 'repository':
            return self.repositoryEvidence(payload, ref)
        if kind == 'readme':
            if payload.get('encoding') != 'base64' or not isinstance(payload.get('content'), str):
                raise ValueError('README has no supported base64 content.')
            try:
                text = base64.b64decode(payload['content'], validate=False).decode('utf-8')
            except (ValueError, UnicodeDecodeError) as error:
                raise ValueError('Invalid README encoding.') from error
        else:
            text = json.dumps({'body': payload.get('body'), 'tag_name': payload.get('tag_name'),
                               'assets': payload.get('assets', [])}, ensure_ascii=False, sort_keys=True)
        whole = self.makeEvidenceRef(text, kind, kind, payload, ref)
        if kind != 'readme':
            return [whole]
        return [whole] + [self.makeEvidenceRef(body, kind, title, payload, ref)
                          for title, body in readmeSections(text)]

    def makeEvidenceRef(self, text: str, kind: str, section: str,
                        payload: dict[str, object], ref: RepositoryRef) -> EvidenceRef:
        digest = hashlib.sha256(text.encode()).hexdigest()
        url = payload.get('html_url')
        evidence: EvidenceRef = {'id': kind + ':' + section + ':' + digest,
            'url': url if isinstance(url, str) else 'https://github.com/' + ref['full_name'],
            'section': section, 'content_hash': digest, 'source_version': str(payload.get('sha') or
            payload.get('tag_name') or digest), 'checked_at': self.now(), 'status': 'verified',
            'source_kind': kind, 'text': text}
        published = payload.get('published_at')
        if isinstance(published, str):
            evidence['published_at'] = published
        return evidence

    def repositoryEvidence(self, payload: dict[str, object], ref: RepositoryRef) -> list[EvidenceRef]:
        raw = json.dumps(payload, ensure_ascii=False, sort_keys=True)
        refs = [self.makeEvidenceRef(raw, 'repository', 'metadata', payload, ref)]
        description = payload.get('description')
        if isinstance(description, str) and description:
            refs.append(self.makeEvidenceRef(description, 'repository', 'description', payload, ref))
        licenseInfo = payload.get('license')
        licenseId = licenseInfo.get('spdx_id') if isinstance(licenseInfo, dict) else None
        if isinstance(licenseId, str) and licenseId != 'NOASSERTION':
            licenseRef = self.makeEvidenceRef('SPDX-License-Identifier: ' + licenseId,
                                             'repository', 'license', payload, ref)
            licenseRef['license_spdx_id'] = licenseId
            refs.append(licenseRef)
        return refs


def readmeSections(text: str) -> list[tuple[str, str]]:
    sections: list[tuple[str, str]] = []
    title, lines = 'introduction', []
    fenced = False
    for line in text.splitlines():
        if line.lstrip().startswith(('```', '~~~')):
            fenced = not fenced
        heading = re.match(r'^#{1,6}\s+(.+?)\s*#*$', line) if not fenced else None
        if heading:
            if lines and '\n'.join(lines).strip():
                sections.append((title, '\n'.join(lines).strip()))
            title = 'introduction' if line.startswith('# ') else heading.group(1)
            lines = []
        else:
            lines.append(line)
    if lines and '\n'.join(lines).strip():
        sections.append((title, '\n'.join(lines).strip()))
    return sections
