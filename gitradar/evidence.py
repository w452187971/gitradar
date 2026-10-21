"""复核既有片段而不替编辑者改结论，路径与事实保持独立时钟。"""
from __future__ import annotations

import copy
import hashlib
import json
from urllib.parse import unquote, urlsplit
from typing import Callable

from gitradar.content import Record, _record, _records, _strings, isOfficialUrl, pathClaimRefs, hasSourceContext
from gitradar.github_client import BudgetExceeded, GitHubClient
from gitradar.models import Budget
from gitradar.sources import isRepositoryMetadataUrl


def sourceLocation(url: object, kind: object) -> str:
    parsed = urlsplit(str(url or ''))
    parts = unquote(parsed.path).strip('/').split('/')
    host = parsed.hostname or ''
    if host == 'raw.githubusercontent.com' and len(parts) >= 4:
        return 'github:' + '/'.join(parts[:2] + parts[3:])
    if host == 'github.com' and len(parts) >= 2:
        if kind == 'repository' and isRepositoryMetadataUrl(url):
            return 'github:' + '/'.join(parts[:2])
        if len(parts) >= 5 and parts[2] == 'blob':
            return 'github:' + '/'.join(parts[:2] + parts[4:])
    if host == 'api.github.com' and parts[:1] == ['repos'] and len(parts) >= 3:
        if kind == 'repository' and isRepositoryMetadataUrl(url):
            return 'github:' + '/'.join(parts[1:3])
        if len(parts) > 4 and parts[3] == 'contents':
            return 'github:' + '/'.join(parts[1:3] + parts[4:])
    return parsed._replace(fragment='').geturl()


def _matchingSource(ref: Record, sources: list[Record]) -> Record:
    kind = ref.get('source_kind')
    location = sourceLocation(ref.get('url'), kind)
    matches = [source for source in sources if source.get('source_kind') == kind
               and sourceLocation(source.get('url'), kind) == location]
    exact = next((source for source in matches if source.get('id') == ref.get('id')), None)
    if exact is not None:
        return exact
    if hasSourceContext(ref):
        matches.sort(key=lambda item: len(str(item.get('text', ''))), reverse=True)
    return matches[0] if matches else {}


def _unchanged(ref: Record, source: Record) -> bool:
    old, new = str(ref.get('text', '')), str(source.get('text', ''))
    if not old:
        return False
    if hasSourceContext(ref) and ref.get('source_kind') != 'release':
        return old in new
    try:
        before, after = json.loads(old), json.loads(new)
        return isinstance(before, dict) and isinstance(after, dict) and all(
            key in after and after[key] == value for key, value in before.items())
    except (ValueError, TypeError):
        return old == new


def _refreshRef(ref: Record, source: Record) -> Record:
    result = copy.deepcopy(ref)
    sourceHash = source.get('source_hash') or source.get('content_hash')
    result.update(checked_at=source.get('checked_at'), status=source.get('status', 200), source_hash=sourceHash)
    if hasSourceContext(ref) and ref.get('source_hash'):
        if ref.get('context_changed') or ref.get('source_hash') != sourceHash:
            result.update(context_changed=True, previous_source_hash=ref.get('previous_source_hash') or ref['source_hash'])
    if not _unchanged(ref, source):
        text = str(source.get('text', ''))[:16000]
        result.update(text=text, content_hash=hashlib.sha256(text.encode()).hexdigest(),
                      previous_hash=ref.get('content_hash'))
    return result


def mergeEvidence(previous: Record, fetched: Record) -> Record:
    result = copy.deepcopy(previous)
    latest = _records(fetched.get('refs'))
    bound = {refId for fact in _record(previous.get('facts')).values()
             for refId in _strings(_record(fact).get('ref_ids'))}
    old = [ref for ref in _records(previous.get('refs'))
           if not latest or ':' not in str(ref.get('id', '')) or ref.get('id') in bound]
    refs = [_refreshRef(ref, source) if (source := _matchingSource(ref, latest)) else copy.deepcopy(ref)
            for ref in old]
    ids = {ref.get('id') for ref in refs}
    refs.extend(copy.deepcopy(ref) for ref in latest if ref.get('id') not in ids)
    result.update(full_name=fetched.get('full_name', previous.get('full_name', '')),
                  node_id=fetched.get('node_id', previous.get('node_id')), refs=refs,
                  cache=copy.deepcopy(fetched.get('cache', previous.get('cache', {}))),
                  errors=fetched.get('errors', []), status=fetched.get('status', 'failed'))
    unknowns = _strings(previous.get('critical_unknowns')) + _strings(fetched.get('critical_unknowns'))
    fetchedId = fetched.get('node_id')
    if previous.get('node_id') and isinstance(fetchedId, str) and fetchedId and fetchedId != previous['node_id']:
        unknowns.append('identity_conflict')
    result['critical_unknowns'] = list(dict.fromkeys(unknowns))
    return result


def _initializePaths(bundle: Record, content: Record) -> None:
    refs = _records(bundle.get('refs'))
    required: dict[str, list[str]] = {}
    for path in _records(content.get('usage_paths')):
        url = str(path.get('url', ''))
        for refId in pathClaimRefs(content, path, refs):
            required.setdefault(refId, []).append(url)
    for ref in refs:
        urls = required.get(str(ref.get('id')), [])
        if not urls:
            continue
        checks = copy.deepcopy(_record(ref.get('path_checks')))
        for url in urls:
            checks.setdefault(url, {'status': 'unverified'})
        ref.update(path_checks=checks, path_required_urls=list(dict.fromkeys(urls)))
    bundle['refs'] = refs


def _recordPathResult(bundle: Record, claims: list[str], url: str, status: int, asOf: str) -> None:
    refs = _records(bundle.get('refs'))
    for ref in refs:
        if ref.get('id') not in claims:
            continue
        checks = _record(ref.get('path_checks'))
        check = _record(checks.get(url))
        check.update(status=status, last_attempt_at=asOf)
        if status == 200:
            check['checked_at'] = asOf
        checks[url] = check
        ref['path_checks'] = checks
        _aggregatePathChecks(ref, checks)
    bundle['refs'] = refs


def _aggregatePathChecks(ref: Record, checks: Record) -> None:
    required = [_record(checks.get(url)) for url in _strings(ref.get('path_required_urls'))]
    gone = next((check['status'] for check in required if check.get('status') in (404, 410)), None)
    if gone:
        ref['path_status'] = gone
    elif required and all(check.get('status') == 200 and check.get('checked_at') for check in required):
        ref.update(path_status=200, path_checked_at=min(str(check['checked_at']) for check in required))


def _checkProjectPaths(project: Record, bundle: Record, client: GitHubClient,
                       budget: Budget, asOf: str, result: Record, clock: Callable[[], str] | None = None) -> bool:
    name, content = str(project.get('full_name', '')), _record(project.get('content'))
    _initializePaths(bundle, content)
    checked: set[str] = set()
    for path in _records(content.get('usage_paths')):
        url = str(path.get('url', ''))
        if url in checked or not isOfficialUrl(url, name, content.get('official_urls')):
            continue
        checked.add(url)
        try:
            response = client.exchange('HEAD', url, None, budget, 'path', {'User-Agent': 'GitRadar-V4-link-check'})
            ids = pathClaimRefs(content, path, _records(bundle.get('refs')))
            checkedAt = clock() if clock is not None else asOf
            _recordPathResult(bundle, ids, url, response.status, checkedAt)
        except BudgetExceeded:
            return False
        except (OSError, ValueError):
            result['path_failures'] = _strings(result.get('path_failures')) + [name + ':' + url]
    return True


def refreshPaths(projects: list[Record], evidence: Record, client: GitHubClient,
                 budget: Budget, asOf: str, clock: Callable[[], str] | None = None) -> Record:
    result = copy.deepcopy(evidence)
    bundles = _record(result.get('projects'))
    for project in projects[:20]:
        name = str(project.get('full_name', ''))
        bundle = _record(bundles.get(name))
        complete = _checkProjectPaths(project, bundle, client, budget, asOf, result, clock)
        bundles[name] = bundle
        if not complete:
            break
    result['projects'] = bundles
    return result
