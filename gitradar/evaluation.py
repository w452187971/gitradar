"""从真实运行报告结算有限观察窗口，缺少时间或独立样本不算通过。"""
from __future__ import annotations

import datetime as dt
from gitradar.content import Record, _record, _records, _strings, _time


def _instant(value: str) -> dt.datetime:
    parsed = _time(value)
    if parsed is None:
        raise ValueError('Evaluation requires a valid timestamp.')
    return parsed.astimezone(dt.timezone.utc)


def _status(passed: bool, complete: bool) -> str:
    return ('passed' if passed else 'failed') if complete else 'unverified'


def _scheduled(runs: list[Record], cohortSize: int, complete: bool) -> Record:
    dates = set()
    for run in runs:
        size, fresh = run.get('cohort_size'), run.get('cohort_fresh')
        count, current = run.get('recommendation_count'), run.get('recommendation_fresh_count')
        if (run.get('run_kind') == 'schedule' and type(size) is int and size == cohortSize and size > 0
                and type(fresh) is int and fresh / size >= .95 and type(count) is int and count > 0
                and type(current) is int and current / count >= .95):
            dates.add(str(run.get('utc_date')))
    return {'status': _status(len(dates) >= 13, complete), 'successful_days': len(dates),
            'required_days': 13, 'dates': sorted(dates)}


def _automatic(runs: list[Record], excluded: set[str], complete: bool) -> Record:
    identities, scenes = set(), set()
    for run in runs:
        for project in _records(run.get('new_recommendations')):
            content = _record(project.get('content'))
            name = str(project.get('full_name', '')).casefold()
            if (project.get('discovery_kind') != 'automatic_new' or name in excluded
                    or content.get('seed') or content.get('review_kind') != 'automatic_template'):
                continue
            identities.add(str(project.get('node_id') or name))
            scenes.add(str(project.get('primary_scene') or content.get('primary_scene') or ''))
    scenes.discard('')
    return {'status': _status(len(identities) >= 10 and len(scenes) >= 3, complete),
            'count': len(identities), 'scene_count': len(scenes), 'scenes': sorted(scenes)}


def _references(references: list[Record], projects: list[Record], start: dt.datetime,
                end: dt.datetime, now: dt.datetime) -> Record:
    unique = {}
    for reference in references:
        first = _time(reference.get('first_public_seen_at'))
        if reference.get('independently_eligible') is True and first and start <= first < end:
            unique.setdefault(str(reference.get('full_name', '')).casefold(), reference)
    observed = {str(p.get('full_name', '')).casefold(): _time(p.get('first_observed_at')) for p in projects}
    detected = 0
    for name, reference in unique.items():
        first = _instant(str(reference['first_public_seen_at']))
        seen = observed.get(name)
        detected += int(seen is not None and seen <= first + dt.timedelta(hours=48))
    complete = now >= end + dt.timedelta(hours=48) and len(unique) >= 20
    return {'status': _status(bool(unique) and detected / len(unique) >= .8, complete),
            'sample_count': len(unique), 'detected_within_48h': detected,
            'sampling_days': (end - start).days, 'missing_samples_are_unverified': True}


def evaluateObservation(report: Record, projects: list[Record], baselineNames: list[str],
                        seedNames: list[str], references: list[Record], publishedAt: str,
                        asOf: str) -> Record:
    published, now = _instant(publishedAt), _instant(asOf)
    start = dt.datetime.combine(published.date() + dt.timedelta(days=1), dt.time(), dt.timezone.utc)
    end = start + dt.timedelta(days=14)
    complete = now >= end + dt.timedelta(hours=48)
    runs = [run for run in _records(report.get('runs'))
            if str(start.date()) <= str(run.get('utc_date', '')) < str(end.date())]
    excluded = {name.casefold() for name in baselineNames + seedNames}
    referenceEnd = end
    initialReferences = _references(references, projects, start, end, now)
    if complete and initialReferences['sample_count'] < 20:
        referenceEnd = start + dt.timedelta(days=28)
    return {'window_start': str(start.date()), 'sampling_end_exclusive': str(end.date()),
            'settlement_at': (end + dt.timedelta(hours=48)).isoformat(),
            'scheduled_coverage': _scheduled(runs, len(set(_strings(report.get('fixed_cohort')))), complete),
            'automatic_new': _automatic(runs, excluded, complete),
            'reference_discovery': _references(references, projects, start, referenceEnd, now)}
