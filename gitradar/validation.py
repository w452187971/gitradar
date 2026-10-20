"""发布前校验同批产物、身份和历史；不修改任何输入。"""
from __future__ import annotations

import datetime as dt
import hashlib
from pathlib import Path, PurePosixPath
from collections.abc import Mapping
from typing import cast

from gitradar.models import ValidationReport


def _mapping(value: object) -> dict[str, object]:
    return cast(dict[str, object], value) if isinstance(value, dict) else {}


def _projects(value: object) -> list[dict[str, object]]:
    return [_mapping(item) for item in value] if isinstance(value, list) else []


def _historyErrors(previous: dict[str, object], candidate: dict[str, object], today: str) -> list[str]:
    errors: list[str] = []
    original, updated = _mapping(previous.get('history')), _mapping(candidate.get('history'))
    fresh = {str(p.get('history_key', p.get('full_name'))) for p in _projects(candidate.get('projects'))
             if p.get('observation_status') == 'fresh' and not p.get('identity_conflict')}
    for name, oldSeries in original.items():
        for date, stars in _mapping(oldSeries).items():
            series = _mapping(updated.get(name))
            if date not in series or (series[date] != stars and (date != today or name not in fresh)):
                errors.append(f'history_changed:{name}:{date}')
    for name, series in updated.items():
        for date, stars in _mapping(series).items():
            if type(stars) is not int or stars < 0 or not _validDate(date):
                errors.append(f'invalid_history:{name}:{date}')
            if date not in _mapping(original.get(name)) and (date != today or name not in fresh):
                errors.append(f'unobserved_history:{name}:{date}')
    return errors


def _validDate(value: str) -> bool:
    try:
        return str(dt.date.fromisoformat(value)) == value
    except (TypeError, ValueError):
        return False


def _identityErrors(candidate: dict[str, object]) -> list[str]:
    nodes: dict[str, str] = {}
    names: set[str] = set()
    errors = []
    for project in _projects(candidate.get('projects')):
        name = str(project.get('full_name', '')).lower()
        node, key = project.get('node_id'), str(project.get('history_key', project.get('full_name')))
        if not name or name in names:
            errors.append('duplicate_or_empty_project:' + name)
        names.add(name)
        if isinstance(node, str):
            if node in nodes and nodes[node] != key:
                errors.append('identity_multiple_histories:' + node)
            nodes[node] = key
    return errors


def _budgetErrors(usage: dict[str, object]) -> list[str]:
    limits = {'rest_requests': 100, 'search_requests': 20, 'graphql_points': 600,
              'graphql_batches': 100, 'content_requests': 60, 'path_requests': 20,
              'identity_requests': 20}
    return ['budget_exceeded:' + key for key, maximum in limits.items()
            if type(usage.get(key, 0)) is not int or not 0 <= cast(int, usage.get(key, 0)) <= maximum]


def _validHistoryAlias(project: dict[str, object], alias: str,
                       previous: dict[str, object]) -> bool:
    node, createdAt = project.get('node_id'), project.get('created_at')
    key = project.get('history_key', project.get('full_name'))
    oldProjects = _projects(previous.get('projects'))
    originals = [old for old in oldProjects if old.get('history_key', old.get('full_name')) == key]
    if not isinstance(node, str) or not node or not isinstance(createdAt, str) or not createdAt:
        return False
    if len(originals) != 1 or alias not in _mapping(previous.get('history')):
        return False
    original = originals[0]
    if original.get('created_at') != createdAt or original.get('node_id') not in (None, node):
        return False
    for old in oldProjects:
        priorAliases = old.get('history_aliases', [])
        referenced = (old.get('history_key', old.get('full_name')) == alias
                      or isinstance(priorAliases, list) and alias in priorAliases)
        if referenced and old.get('node_id') == node and old.get('created_at') == createdAt:
            return True
    return False


def _candidateKeys(previous: dict[str, object], projects: list[dict[str, object]]) -> tuple[set[str], list[str]]:
    keys = {str(project.get('history_key', project.get('full_name'))) for project in projects}
    primaryKeys = set(keys)
    errors = []
    for project in projects:
        aliases = project.get('history_aliases', [])
        if not isinstance(aliases, list) or any(not isinstance(alias, str) for alias in aliases):
            errors.append('invalid_history_aliases:' + str(project.get('full_name')))
            continue
        for alias in aliases:
            if (alias in primaryKeys or aliases.count(alias) != 1
                    or not _validHistoryAlias(project, alias, previous)):
                errors.append('invalid_history_alias:' + alias)
            else:
                keys.add(alias)
    return keys, errors


def _observationErrors(previous: dict[str, object], candidate: dict[str, object], today: str) -> list[str]:
    projects, history = _projects(candidate.get('projects')), _mapping(candidate.get('history'))
    keys, errors = _candidateKeys(previous, projects)
    errors.extend('candidate_lost:' + str(p.get('full_name')) for p in _projects(previous.get('projects'))
                  if p.get('history_key', p.get('full_name')) not in keys)
    if not _validDate(today):
        return errors
    for project in projects:
        series = _mapping(history.get(str(project.get('history_key', project.get('full_name')))))
        fresh = project.get('observation_status') == 'fresh'
        if fresh and 'stargazers_count' in project and series.get(today) != project['stargazers_count']:
            errors.append('observation_star_mismatch:' + str(project.get('full_name')))
        for field, days in (('delta_1d', 1), ('delta_7d', 7)):
            old = series.get(str(dt.date.fromisoformat(today) - dt.timedelta(days=days)))
            now = series.get(today)
            expected = now - old if fresh and type(now) is int and type(old) is int else None
            if field in project and project[field] != expected:
                errors.append('delta_mismatch:' + str(project.get('full_name')) + ':' + field)
    return errors


def _artifactErrors(manifest: dict[str, object], outputDirectory: Path | None) -> list[str]:
    errors = []
    for name, digest in _mapping(manifest.get('artifacts')).items():
        path = PurePosixPath(name)
        if path.is_absolute() or '..' in path.parts or '.git' in path.parts:
            errors.append('unsafe_artifact:' + name)
        elif outputDirectory is not None:
            target = outputDirectory / name
            if not target.is_file() or hashlib.sha256(target.read_bytes()).hexdigest() != digest:
                errors.append('artifact_mismatch:' + name)
    return errors


def _feedErrors(candidate: dict[str, object]) -> list[str]:
    from gitradar.content import eligibleForRecommendation
    feed = _mapping(candidate.get('recommendations'))
    entries = _projects(feed.get('recommendations'))
    errors = []
    if len(entries) > 20:
        errors.append('too_many_recommendations')
    for project in entries:
        content = _mapping(project.get('content'))
        if not eligibleForRecommendation(content, project, str(candidate.get('generated_at')))['eligible']:
            errors.append('ineligible_recommendation:' + str(project.get('full_name')))
    return errors


def validateBatch(previousSnapshot: Mapping[str, object], candidateSnapshot: Mapping[str, object],
                  manifest: Mapping[str, object], outputDirectory: Path | None = None) -> ValidationReport:
    previous, candidate, build = dict(previousSnapshot), dict(candidateSnapshot), dict(manifest)
    today = str(candidate.get('generated_at', ''))[:10]
    errors = [] if _validDate(today) else ['invalid_generated_at']
    batch = candidate.get('batch_id')
    if not isinstance(batch, str) or not batch or build.get('batch_id') != batch:
        errors.append('manifest_batch_mismatch')
    for name in ('recommendations', 'evidence'):
        if _mapping(candidate.get(name)).get('batch_id') != batch:
            errors.append(name + '_batch_mismatch')
    if candidate.get('schema_version') != '4.0' or build.get('schema_version') != '4.0':
        errors.append('schema_mismatch')
    errors.extend(_historyErrors(previous, candidate, today))
    errors.extend(_observationErrors(previous, candidate, today))
    errors.extend(_identityErrors(candidate))
    errors.extend(_budgetErrors(_mapping(candidate.get('usage'))))
    errors.extend(_artifactErrors(build, outputDirectory))
    errors.extend(_feedErrors(candidate))
    return {'allowed': not errors, 'errors': errors, 'warnings': [],
            'checks': {'history': not any('history' in error for error in errors),
                       'batch': not any('batch' in error for error in errors), 'validated': not errors}}
