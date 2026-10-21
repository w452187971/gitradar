"""从已保存的观测记录推导覆盖范围，不访问网络或修改调用方数据。"""
from __future__ import annotations

from collections.abc import Sequence
from typing import Optional, TypedDict


History = dict[str, dict[str, int]]


class SearchReport(TypedDict, total=False):
    query: str
    sort: str
    page: int
    returned: int
    total_count: Optional[int]
    incomplete: bool
    limited: bool
    succeeded: bool


class ObservationFields(TypedDict, total=False):
    first_seen_date: str
    last_observed_date: str
    observation_status: str


class StatsProject(ObservationFields, total=False):
    full_name: str
    history_key: str
    delta_1d: Optional[int]
    delta_7d: Optional[int]
    readme_checked: bool
    readme_stale: bool


class CollectionStats(TypedDict):
    observed_since: Optional[str]
    observed_through: Optional[str]
    observed_dates: int
    refreshed_count: int
    retained_count: int
    newly_discovered_count: int
    daily_coverage: int
    weekly_coverage: int
    readme_checked_count: int
    readme_stale_count: int
    search_attempted: int
    search_succeeded: int
    search_limited: int
    search_incomplete: int


def observationMetadata(name: str, history: History, refreshed: bool) -> ObservationFields:
    series = history.get(name, {})
    metadata: ObservationFields = {'observation_status': 'fresh' if refreshed else 'retained'}
    if series:
        metadata.update(first_seen_date=min(series), last_observed_date=max(series))
    return metadata


def collectionStats(items: Sequence[StatsProject], history: History,
                    previousNames: set[str], searches: Sequence[SearchReport]) -> CollectionStats:
    dates = {date for series in history.values() for date in series}
    knownKeys = {name.lower() for name in previousNames}
    currentKeys = {(item.get('history_key') or name).lower()
                   for item in items if (name := item.get('full_name'))}
    return {
        'observed_since': min(dates) if dates else None,
        'observed_through': max(dates) if dates else None,
        'observed_dates': len(dates),
        'refreshed_count': sum(item.get('observation_status') == 'fresh' for item in items),
        'retained_count': sum(item.get('observation_status') == 'retained' for item in items),
        'newly_discovered_count': len(currentKeys - knownKeys),
        'daily_coverage': sum(type(item.get('delta_1d')) is int for item in items),
        'weekly_coverage': sum(type(item.get('delta_7d')) is int for item in items),
        'readme_checked_count': sum(item.get('readme_checked') is True for item in items),
        'readme_stale_count': sum(item.get('readme_checked') is True and
                                  item.get('readme_stale') is True for item in items),
        'search_attempted': len(searches),
        'search_succeeded': sum(report.get('succeeded') is True for report in searches),
        'search_limited': sum(report.get('limited') is True for report in searches),
        'search_incomplete': sum(report.get('incomplete') is True for report in searches),
    }
