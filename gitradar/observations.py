"""仅将已核对身份和 UTC 日期的成功观测写入历史，保留所有旧系列。"""
from __future__ import annotations

import copy
import datetime as dt
from typing import Optional, Union, cast

from .models import History, Observation, ObservationBatch, ProjectRecord, Snapshot, SCHEMA_VERSION


def observationDate(value: str) -> str:
    instant = dt.datetime.fromisoformat(value.replace('Z', '+00:00'))
    if instant.tzinfo is None:
        raise ValueError('Observation timestamp must contain a timezone.')
    return instant.astimezone(dt.timezone.utc).date().isoformat()


def identityError(project: ProjectRecord, observation: Observation,
                  projects: list[ProjectRecord]) -> Optional[str]:
    nodeId, oldId = observation.get('node_id'), project.get('node_id')
    if not nodeId or (oldId and oldId != nodeId):
        return 'Repository stable identity changed or is missing.'
    if not oldId and (not project.get('created_at') or project['created_at'] != observation.get('created_at')):
        return 'Legacy repository creation time does not match.'
    if oldId and project.get('created_at') and project['created_at'] != observation.get('created_at'):
        return 'Stable repository identity has inconsistent creation time.'
    newName = observation.get('full_name', '').lower()
    if any(other is not project and other.get('full_name', '').lower() == newName for other in projects):
        return 'Repository display name belongs to another identity.'
    return None


def retainProject(project: ProjectRecord, status: str, error: str) -> None:
    project.update(observation_status=status, observation_error=error, delta_1d=None, delta_7d=None,
                   discovery_score=0)


def successfulObservation(observation: Observation, utcDate: str) -> Optional[str]:
    if observation.get('status') != 'success':
        return observation.get('error', 'Observation was deferred or failed.')
    stars = observation.get('stargazers_count')
    if type(stars) is not int or stars < 0:
        return 'Star count must be a non-negative integer.'
    try:
        if observationDate(observation.get('observed_at', '')) != utcDate:
            return 'Observation UTC date differs from the requested snapshot date.'
        dt.datetime.fromisoformat(observation.get('created_at', '').replace('Z', '+00:00'))
    except ValueError:
        return 'Observation has invalid or missing timestamps.'
    return None


def applySuccess(project: ProjectRecord, observation: Observation, history: History, utcDate: str) -> None:
    oldName = project['full_name']
    historyKey = project.get('history_key') or oldName
    project.update(observation)
    project['history_key'] = historyKey
    series = history.setdefault(historyKey, {})
    stars = observation['stargazers_count']
    series[utcDate] = stars
    date = dt.date.fromisoformat(utcDate)
    daily = series.get(str(date - dt.timedelta(days=1)))
    weekly = series.get(str(date - dt.timedelta(days=7)))
    project.update(delta_1d=None if daily is None else stars - daily,
                   delta_7d=None if weekly is None else stars - weekly,
                   first_seen_date=min(series), last_observed_date=max(series),
                   last_observed_at=observation['observed_at'], observation_status='fresh',
                   schema_version=SCHEMA_VERSION)
    project['discovery_score'] = candidateScore(project, date)
    project.pop('observation_error', None)


def candidateScore(project: ProjectRecord, date: dt.date) -> float:
    age = max(1, (date - dt.date.fromisoformat(project['created_at'][:10])).days)
    score = (project.get('delta_7d') or 0)*2 + (project.get('delta_1d') or 0)*3
    score += min(project['stargazers_count'], 2500)/(age+12)*3
    return round(score, 1)


def projectForObservation(projects: list[ProjectRecord], observation: Observation) -> Optional[ProjectRecord]:
    nodeId = observation.get('node_id')
    matches = [project for project in projects if nodeId and project.get('node_id') == nodeId]
    if matches:
        return matches[0]
    name = observation.get('full_name', '').lower()
    return next((project for project in projects if project.get('full_name', '').lower() == name), None)


def newProject(observation: Observation, projects: list[ProjectRecord], history: History) -> Optional[ProjectRecord]:
    name = observation.get('full_name', '')
    historyKey = observation.get('history_key') or name
    if not name or not observation.get('node_id') or historyKey in history:
        return None
    if any(project.get('history_key', project['full_name']) == historyKey for project in projects):
        return None
    project: ProjectRecord = {'full_name': name, 'history_key': historyKey,
                             'node_id': observation['node_id'], 'created_at': observation.get('created_at', '')}
    projects.append(project)
    return project


def applyOne(projects: list[ProjectRecord], history: History, aliases: dict[str, str],
             observation: Observation, utcDate: str) -> None:
    project = projectForObservation(projects, observation)
    failure = successfulObservation(observation, utcDate)
    if project is None:
        if failure:
            return
        project = newProject(observation, projects, history)
        if project is None:
            return
    if failure:
        status = 'deferred' if observation.get('status') == 'deferred' else 'retained'
        retainProject(project, status, failure)
        return
    conflict = identityError(project, observation, projects)
    if conflict:
        retainProject(project, 'identity_conflict', conflict)
        return
    oldName = project['full_name']
    applySuccess(project, observation, history, utcDate)
    if oldName != project['full_name']:
        for alias, current in list(aliases.items()):
            if current == oldName:
                aliases[alias] = project['full_name']
        aliases[oldName] = project['full_name']


def applyObservations(previousSnapshot: Snapshot, observations: Union[ObservationBatch, list[Observation]],
                      utcDate: Union[str, dt.date]) -> Snapshot:
    date = str(utcDate)
    if str(dt.date.fromisoformat(date)) != date:
        raise ValueError('Snapshot date must use YYYY-MM-DD.')
    snapshot = copy.deepcopy(previousSnapshot)
    projects, history = snapshot.setdefault('projects', []), snapshot.setdefault('history', {})
    aliases = snapshot.setdefault('saved_aliases', {})
    batch = observations['observations'] if isinstance(observations, dict) else observations
    for project in projects:
        retainProject(project, 'deferred', 'No successful observation in this batch.')
    for observation in batch:
        applyOne(projects, history, aliases, observation, date)
    snapshot['schema_version'] = SCHEMA_VERSION
    return snapshot


def legacyProjectView(record: ProjectRecord) -> ProjectRecord:
    """保留兼容字段和新身份键，避免旧展示层改变追踪身份。"""
    return copy.deepcopy(record)
