"""复核既有片段而不替编辑者改结论，路径与事实保持独立时钟。"""
from __future__ import annotations

import copy
import hashlib
import json

from gitradar.content import Record, _record, _records, _strings, isOfficialUrl
from gitradar.github_client import BudgetExceeded, GitHubClient
from gitradar.models import Budget


def _matchingSource(ref: Record, sources: list[Record]) -> Record:
    kind = ref.get('source_kind')
    matches = [source for source in sources if source.get('source_kind') == kind]
    if kind == 'readme':
        matches.sort(key=lambda item: len(str(item.get('text', ''))), reverse=True)
    return matches[0] if matches else {}


def _unchanged(ref: Record, source: Record) -> bool:
    old, new = str(ref.get('text', '')), str(source.get('text', ''))
    if not old:
        return False
    if ref.get('source_kind') == 'readme':
        return old in new
    try:
        before, after = json.loads(old), json.loads(new)
        return isinstance(before, dict) and isinstance(after, dict) and all(
            key in after and after[key] == value for key, value in before.items())
    except (ValueError, TypeError):
        return old == new


def _refreshRef(ref: Record, source: Record) -> Record:
    result = copy.deepcopy(ref)
    result.update(checked_at=source.get('checked_at'), status=source.get('status', 200),
                  source_hash=source.get('content_hash'))
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
    if previous.get('node_id') and fetched.get('node_id') not in (None, previous.get('node_id')):
        result['critical_unknowns'] = ['identity_conflict']
    return result


def _recordPathResult(bundle: Record, claims: list[str], status: int, asOf: str) -> None:
    refs = _records(bundle.get('refs'))
    for ref in refs:
        if ref.get('id') not in claims:
            continue
        ref['path_status'] = status
        if status == 200:
            ref['path_checked_at'] = asOf
    bundle['refs'] = refs


def refreshPaths(projects: list[Record], evidence: Record, client: GitHubClient,
                 budget: Budget, asOf: str) -> Record:
    result = copy.deepcopy(evidence)
    bundles = _record(result.get('projects'))
    for project in projects[:20]:
        name, content = str(project.get('full_name', '')), _record(project.get('content'))
        paths = _records(content.get('usage_paths'))
        if not paths or not isOfficialUrl(paths[0].get('url'), name, content.get('official_urls')):
            continue
        try:
            response = client.exchange('HEAD', str(paths[0]['url']), None, budget, 'path',
                                       {'User-Agent': 'GitRadar-V4-link-check'})
            if response.status in (200, 404, 410):
                bundle = _record(bundles.get(name))
                ids = _strings(_record(content.get('claims')).get('usage_paths'))
                _recordPathResult(bundle, ids, response.status, asOf)
                bundles[name] = bundle
        except BudgetExceeded:
            break
        except (OSError, ValueError):
            failures = _strings(result.get('path_failures'))
            result['path_failures'] = failures + [name]
    result['projects'] = bundles
    return result
