"""Deterministic feed composition independent from the legacy discovery score."""
from __future__ import annotations

import copy
import datetime as dt
from collections import Counter

from gitradar.content import Record, _asOf, _record, _records, _strings, _time, eligibleForRecommendation

RECOMMENDATION_VERSION = 'v4.0'
DEVELOPER_FORMS = frozenset({'cli', 'library', 'framework', 'skill', 'collection'})
GUI_FORMS = frozenset({'desktop_app', 'mobile_app', 'web_app'})


def _content(project: Record) -> Record:
    return _record(project.get('content')) if isinstance(project.get('content'), dict) else project


def _identity(project: Record) -> str:
    nodeId = project.get('node_id') or _content(project).get('node_id')
    return str(nodeId) if nodeId else str(project.get('full_name', '')).casefold()


def _ordinary(project: Record) -> bool:
    content = _content(project)
    return content.get('form') in GUI_FORMS and any(
        path.get('kind') in ('download', 'web', 'documentation', 'installer')
        for path in _records(content.get('usage_paths')))


def _family(project: Record) -> str:
    return str(_content(project).get('family') or project.get('family') or '')


def _scene(project: Record) -> str:
    return str(_content(project).get('primary_scene', ''))


def _recent(value: object, asOf: dt.datetime) -> bool:
    parsed = _time(value)
    return parsed is not None and dt.timedelta(0) <= asOf - parsed <= dt.timedelta(days=14)


def _growth(project: Record, asOf: dt.datetime) -> Record:
    for evidence in _records(project.get('growth_evidence')):
        start, end = _time(evidence.get('start_date')), _time(evidence.get('end_date'))
        old, new = evidence.get('start_stars'), evidence.get('end_stars')
        if (start is not None and end is not None and start < end <= asOf
                and asOf - end <= dt.timedelta(days=2)
                and isinstance(old, int) and not isinstance(old, bool) and old >= 0
                and isinstance(new, int) and not isinstance(new, bool) and new > old):
            return {'start_date': evidence['start_date'], 'end_date': evidence['end_date'], 'net_change': new - old}
    return {}


def _momentum(project: Record, asOf: dt.datetime) -> bool:
    if _growth(project, asOf):
        return True
    for ref in _records(_content(project).get('evidence_refs')):
        if (ref.get('source_kind') == 'release' and ref.get('status') in (200, 'verified')
                and _recent(ref.get('published_at'), asOf)):
            return True
    return False


def _new(project: Record, dates: Record, asOf: dt.datetime) -> bool:
    return _recent(dates.get(_identity(project)), asOf)


def _allowed(project: Record, selected: list[Record]) -> bool:
    if len(selected) < 6 and not _ordinary(project):
        return False
    if _scene(project) and sum(_scene(item) == _scene(project) for item in selected) >= 10:
        return False
    if _content(project).get('form') in DEVELOPER_FORMS:
        if sum(_content(item).get('form') in DEVELOPER_FORMS for item in selected) >= 4:
            return False
    identity, family = _identity(project), _family(project)
    return not any(_identity(item) == identity or (family and _family(item) == family) for item in selected)


def _pick(pool: list[Record], selected: list[Record], limit: int, slot: str) -> None:
    for _ in range(limit):
        if len(selected) >= 20:
            return
        available = [item for item in pool if _allowed(item, selected)]
        if not available:
            return
        represented = {_scene(item) for item in selected}
        if len(represented) < 4:
            available.sort(key=lambda item: _scene(item) in represented)
        chosen = copy.deepcopy(available[0])
        chosen.update(slot=slot, primary_scene=_scene(chosen))
        selected.append(chosen)


def _discoveryKind(project: Record, previousDates: Record, asOf: dt.datetime) -> str:
    content = _content(project)
    if _identity(project) in previousDates:
        return 'rotation'
    if content.get('seed') or project.get('seed'):
        return 'seed'
    if project.get('in_frozen_baseline'):
        return 'baseline_backfill'
    discovered, started = _time(project.get('first_observed_at')), _time(project.get('observation_started_at'))
    automatic = (project.get('discovery_origin') == 'automatic' and project.get('automatically_qualified') is True
                 and content.get('review_kind') == 'automatic_template'
                 and discovered is not None and started is not None and started <= discovered <= asOf)
    return 'automatic_new' if automatic else 'manual_addition'


def _reason(project: Record, asOf: dt.datetime, first: bool) -> str:
    reason = str(_content(project).get('recommendation_reason', ''))
    growth = _growth(project, asOf)
    if growth:
        reason += '；' + str(growth['start_date'])[:10] + ' 至 ' + str(growth['end_date'])[:10]
        reason += ' Star 净增 ' + str(growth['net_change'])
    if first:
        reason += '；本站首次推荐'
    return reason


def _qualify(projects: list[Record], previous: Record, asOf: str) -> tuple[list[Record], Record, Record]:
    eligible, qualification, dates = [], {}, copy.deepcopy(_record(previous.get('first_qualified_at')))
    for project in projects:
        identity = _identity(project)
        observation = dict(project)
        observation.update(_record(project.get('observation')))
        result = eligibleForRecommendation(_content(project), observation, asOf)
        qualification[identity] = result
        if result['eligible'] and identity:
            eligible.append(project)
            dates.setdefault(identity, project.get('first_qualified_at') or asOf)
    # Content and environment outrank freshness and novelty. Legacy scores cannot override these gates.
    shown = _record(previous.get('last_recommended_at'))
    eligible.sort(key=lambda item: (not _ordinary(item), str(shown.get(_identity(item), '')),
                                    str(dates.get(_identity(item))), _identity(item)))
    return eligible, qualification, dates


def selectRecommendations(projects: list[Record], previousFeed: Record | None, asOf: str) -> Record:
    previous = previousFeed or {}
    eligible, qualification, qualifiedDates = _qualify(projects, previous, asOf)
    selected: list[Record] = []
    now = _asOf(asOf)
    _pick([item for item in eligible if _new(item, qualifiedDates, now)], selected, 8, 'new')
    _pick([item for item in eligible if _momentum(item, now)], selected, 6, 'momentum')
    _pick([item for item in eligible if not _new(item, qualifiedDates, now)
           and not _momentum(item, now)], selected, 6, 'rotation')
    _pick(eligible, selected, 20 - len(selected), 'refill')
    firstDates = copy.deepcopy(_record(previous.get('first_recommended_at')))
    counts: Counter[str] = Counter()
    _annotate(selected, firstDates, qualifiedDates, counts, now, asOf)
    lastDates = copy.deepcopy(_record(previous.get('last_recommended_at')))
    lastDates.update({_identity(project): asOf for project in selected})
    return {'recommendation_version': RECOMMENDATION_VERSION, 'generated_at': asOf,
            'recommendations': selected, 'first_recommended_at': firstDates,
            'first_qualified_at': qualifiedDates, 'eligibility': qualification,
            'last_recommended_at': lastDates,
            'discovery_counts': {key: counts[key] for key in ('automatic_new', 'seed', 'baseline_backfill', 'manual_addition', 'rotation')},
            'eligible_count': len(eligible), 'selected_count': len(selected),
            'shortfall_reasons': ['合格内容或场景、普通用户使用路径不足，展示实际数量'] if len(selected) < 20 else []}


def _annotate(selected: list[Record], firstDates: Record, qualifiedDates: Record,
              counts: Counter[str], now: dt.datetime, asOf: str) -> None:
    previousDates = copy.deepcopy(firstDates)
    for project in selected:
        identity = _identity(project)
        first = identity not in firstDates
        kind = _discoveryKind(project, previousDates, now)
        counts[kind] += 1
        firstDates.setdefault(identity, asOf)
        project.update(first_recommended_at=firstDates[identity], first_qualified_at=qualifiedDates[identity],
                       discovery_kind=kind, recommendation_reason=_reason(project, now, first))
