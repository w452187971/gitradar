"""有界采集、隔离生成与校验后发布；人工编辑资料从不由采集器覆盖。"""
from __future__ import annotations

import argparse
import copy
import datetime as dt
import hashlib
import json
import os
import shutil
import subprocess
import traceback
import uuid
from dataclasses import asdict
from pathlib import Path, PurePosixPath
from typing import Callable, cast
from urllib.parse import urlencode

from gitradar.content import deriveFacts, resolveContent, _strings
from gitradar.evidence import mergeEvidence, refreshPaths
from gitradar.github_client import BudgetExceeded, GitHubClient, utcNow
from gitradar.models import Budget, ObservationBatch, ProjectRecord, Snapshot
from gitradar.observations import applyObservations
from gitradar.recommendations import selectRecommendations
from gitradar.validation import validateBatch

Record = dict[str, object]
DATA_ARTIFACTS = ('projects.json', 'history.json', 'summaries.json', 'evidence.json',
                  'recommendations.json', 'observation-reports.json', 'pending-candidates.json')


def _record(value: object) -> Record:
    return cast(Record, value) if isinstance(value, dict) else {}


def _records(value: object) -> list[Record]:
    return [_record(item) for item in value if isinstance(item, dict)] if isinstance(value, list) else []


def readJson(path: Path, default: object) -> object:
    if not path.exists():
        return copy.deepcopy(default)
    with path.open(encoding='utf-8') as handle:
        return json.load(handle)


def writeJson(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, allow_nan=False, indent=2) + '\n', encoding='utf-8')


def loadSnapshot(root: Path) -> Record:
    import collect
    data = root / 'data'
    projects, history, summaries = collect.loadState(data)
    snapshot = _record(readJson(data / 'projects.json', {}))
    snapshot.update(projects=projects, history=history, summaries=summaries)
    machine = data / 'evidence.json'
    evidence = readJson(machine if machine.exists() else data / 'seed-evidence.json', {'projects': {}})
    snapshot.update(evidence=_record(evidence), curation=_record(readJson(data / 'curation.json', {})),
                    recommendations=_record(readJson(data / 'recommendations.json', {})),
                    observation_reports=_record(readJson(data / 'observation-reports.json', {})))
    baseline = _record(readJson(root / 'docs/evaluation/v4-baseline.json', {}))
    snapshot['pending_candidates'] = _record(readJson(data / 'pending-candidates.json', {'projects': []}))
    snapshot['previous_details'] = _record(readJson(data / 'detail-index.json', {}))
    snapshot['frozen_baseline_names'] = _strings(baseline.get('candidate_names'))
    return snapshot


def _searchPage(client: GitHubClient, query: str, sort: str, page: int,
                budget: Budget, repositories: Record) -> Record:
    import collect
    report: Record = {'query': query, 'sort': sort, 'page': page, 'returned': 0,
                       'total_count': None, 'incomplete': False, 'limited': False, 'succeeded': False}
    params = urlencode({'q': query, 'sort': sort, 'order': 'desc', 'per_page': 100, 'page': page})
    try:
        payload = _record(client.requestRest('/search/repositories?' + params, budget, 'search'))
        if not isinstance(payload.get('items'), list):
            raise ValueError('Search response has no repository list.')
        for item in _records(payload['items']):
            repository = collect.validateRepository(item)
            if not repository.get('archived') and not repository.get('fork'):
                repositories[repository['full_name'].lower()] = repository
        total = payload.get('total_count')
        report.update(returned=len(payload['items']), total_count=total if type(total) is int else None,
                      incomplete=payload.get('incomplete_results') is True, succeeded=True,
                      limited=payload.get('incomplete_results') is True or (type(total) is int and total > 100))
    except (OSError, ValueError, KeyError, BudgetExceeded) as error:
        report['error'] = str(error)
    return report


def discover(client: GitHubClient, budget: Budget, asOf: str) -> tuple[list[Record], list[Record]]:
    import collect
    today = dt.date.fromisoformat(asOf[:10])
    repositories: Record = {}
    reports = [_searchPage(client, query, 'stars' if (today.toordinal() + index) % 2 == 0 else 'updated',
                           1, budget, repositories)
               for index, query in enumerate(collect.discoveryQueries(today)[:18])]
    for query, sort, page in collect.extraSearchPages(today, reports):
        reports.append(_searchPage(client, query, sort, page, budget, repositories))
    return [_record(value) for value in repositories.values()], reports


def _seedMetadata(bundle: Record) -> Record:
    for ref in _records(bundle.get('refs')):
        if ref.get('source_kind') == 'repository':
            try:
                value = _record(json.loads(str(ref.get('text', ''))))
            except (ValueError, TypeError):
                continue
            if value.get('created_at') and value.get('html_url'):
                return value
    raise ValueError('Seed repository lacks official identity metadata: ' + str(bundle.get('full_name')))


def repositoryPool(previous: Record, discovered: list[Record], asOf: str) -> list[Record]:
    pool = copy.deepcopy(_records(previous.get('projects')))
    names = {str(project['full_name']).lower() for project in pool}
    for pending in _records(_record(previous.get('pending_candidates')).get('projects')):
        name = str(pending['full_name']).lower()
        if name not in names:
            pool.append(copy.deepcopy(pending))
            names.add(name)
    seedBundles = _record(_record(previous.get('evidence')).get('projects'))
    baseline = {name.lower() for name in _strings(previous.get('frozen_baseline_names'))}
    for repo in discovered:
        name = str(repo['full_name'])
        if name.lower() not in names:
            pool.append({**repo, 'discovery_origin': 'automatic', 'first_observed_at': asOf})
            names.add(name.lower())
    seedNames = {name for name, value in _record(_record(previous.get('curation')).get('projects')).items()
                 if _record(value).get('seed')}
    for name, value in seedBundles.items():
        if name not in seedNames:
            continue
        if name.lower() not in names:
            bundle = _record(value)
            metadata = _seedMetadata(bundle)
            pool.append({**metadata, 'full_name': name, 'node_id': bundle.get('node_id'), 'seed': True,
                         'schema_version': '4.0', 'stargazers_count': None,
                         'discovery_origin': 'seed', 'first_observed_at': asOf})
            names.add(name.lower())
    for project in pool:
        name = str(project['full_name'])
        project.setdefault('first_observed_at', project.get('last_observed_at') or previous.get('generated_at') or asOf)
        project.setdefault('discovery_origin', 'baseline' if name.lower() in baseline else 'manual')
        project.setdefault('observation_started_at', previous.get('observation_started_at') or asOf)
        project['in_frozen_baseline'] = name.lower() in baseline
        if name in seedNames or project.get('discovery_origin') == 'seed':
            project['seed'] = True
    return pool


def _refs(projects: list[Record]) -> list[Record]:
    return [{key: project[key] for key in ('full_name', 'node_id', 'created_at', 'history_key')
             if project.get(key)} for project in projects]


def _fallbackRefs(projects: list[Record], batch: ObservationBatch, previousFeed: Record) -> list[Record]:
    failed = {str(item.get('full_name')) for item in batch['observations'] if item.get('status') != 'success'}
    recommended = {str(item.get('full_name')) for item in _records(previousFeed.get('recommendations'))}
    pending = [project for project in projects if project['full_name'] in failed]
    pending.sort(key=lambda project: (str(project.get('full_name')) not in recommended,
                                     str(project.get('last_identity_attempt_at', '')),
                                     str(project.get('last_observed_at', '')), str(project['full_name'])))
    # 每轮至少一半补查用于最久未核对项目，失败尝试也推进轮换。
    priority = [project for project in pending if project['full_name'] in recommended][:10]
    remaining = [project for project in pending if project not in priority]
    remaining.sort(key=lambda project: (str(project.get('last_identity_attempt_at', '')), str(project['full_name'])))
    return _refs((priority + remaining)[:20])


def observe(previous: Record, pool: list[Record], client: GitHubClient,
            budget: Budget, asOf: str, offline: bool) -> Record:
    snapshot = copy.deepcopy(previous)
    snapshot['projects'] = pool
    if offline:
        batch: ObservationBatch = {'observations': [], 'errors': ['Offline preview; no fresh observations.'],
                                   'observed_at': asOf, 'usage': asdict(client.usage)}
    else:
        batch = client.fetchObservations(_refs(pool), budget)
        refs = _fallbackRefs(pool, batch, _record(previous.get('recommendations')))
        attempted = {str(ref['full_name']) for ref in refs}
        for project in pool:
            if project['full_name'] in attempted:
                project['last_identity_attempt_at'] = asOf
        if refs:
            fallback = client.fetchRestObservations(refs, budget)
            batch['observations'].extend(fallback['observations'])
            batch['errors'].extend(fallback['errors'])
    updated = applyObservations(cast(Snapshot, snapshot), batch, asOf[:10])
    result = cast(Record, updated)
    result['observation_errors'] = batch['errors']
    _partitionCandidates(previous, result, offline)
    return result


def _partitionCandidates(previous: Record, snapshot: Record, offline: bool) -> None:
    projects = _records(snapshot.get('projects'))
    history = _record(snapshot.get('history'))
    oldNames = {str(project['full_name']) for project in _records(previous.get('projects'))}
    pending = [project for project in projects
               if not _record(history.get(str(project.get('history_key', project['full_name']))))
               and str(project['full_name']) not in oldNames]
    snapshot['pending_candidates'] = {'projects': copy.deepcopy(pending)}
    if not offline:
        pendingNames = {str(project['full_name']) for project in pending}
        snapshot['projects'] = [project for project in projects if str(project['full_name']) not in pendingNames]


def _lastAttempt(project: Record, evidence: Record) -> str:
    bundle = _record(_record(evidence.get('projects')).get(str(project['full_name'])))
    return str(bundle.get('last_attempt_at', ''))


def _due(project: Record, evidence: Record, asOf: str) -> bool:
    bundle = _record(_record(evidence.get('projects')).get(str(project['full_name'])))
    dates = [str(ref.get('checked_at')) for ref in _records(bundle.get('refs')) if ref.get('checked_at')]
    if not dates:
        return False
    cutoff = (dt.datetime.fromisoformat(asOf.replace('Z', '+00:00')) - dt.timedelta(days=13)).isoformat()
    return min(dates) < cutoff


def scheduleContent(projects: list[Record], evidence: Record, previousFeed: Record,
                    asOf: str) -> tuple[list[Record], Record]:
    ordered = sorted(projects, key=lambda project: (_lastAttempt(project, evidence), str(project['full_name'])))
    recommended = {str(item.get('full_name')) for item in _records(previousFeed.get('recommendations'))}
    pools = [('due', [project for project in ordered if _due(project, evidence, asOf)], 20),
             ('recommended', [project for project in ordered if project['full_name'] in recommended], 8),
             ('new', [project for project in ordered if project.get('discovery_origin') == 'automatic'
                      and not _record(_record(evidence.get('projects')).get(str(project['full_name']))).get('refs')], 6),
             ('review', [project for project in ordered if _record(project.get('content')).get('effective_status')
                         in ('review_required', 'blocked')], 4), ('rotation', ordered, 2)]
    selected: list[Record] = []
    actual: Record = {}
    for kind, pool, quota in pools:
        chosen = [project for project in pool if project not in selected][:min(quota, 20 - len(selected))]
        selected.extend(chosen)
        actual[kind] = len(chosen)
    spare = [project for project in ordered if project not in selected][:20-len(selected)]
    selected.extend(spare)
    actual['refill'] = len(spare)
    return selected, {'planned': {'recommended': 8, 'new': 6, 'review': 4, 'rotation': 2},
                      'actual': actual, 'selected': [p['full_name'] for p in selected],
                      'waiting': max(0, len(projects) - len(selected))}


def refreshContent(snapshot: Record, client: GitHubClient, budget: Budget, asOf: str, offline: bool) -> None:
    evidence = _record(snapshot.get('evidence'))
    bundles = _record(evidence.get('projects'))
    projects = _records(snapshot.get('projects'))
    selected, allocation = scheduleContent(projects, evidence, _record(snapshot.get('recommendations')), asOf)
    attempted: list[str] = []
    initialRequests = client.usage.content_requests
    if not offline:
        for project in selected:
            if (client.usage.content_requests >= budget.content_requests
                    or client.usage.rest_requests >= budget.rest_requests or client.usage.rate_limited):
                break
            name = str(project['full_name'])
            previous = _record(bundles.get(name))
            fetched = client.readProjectEvidence(_refs([project])[0], previous, budget)
            bundles[name] = {**mergeEvidence(previous, fetched), 'last_attempt_at': asOf}
            attempted.append(name)
    statuses = [str(_record(bundles.get(name)).get('status', 'failed')) for name in attempted]
    allocation.update(attempted=attempted, attempted_count=len(attempted),
                      requests_used=client.usage.content_requests - initialRequests,
                      successful_count=statuses.count('success'), partial_count=statuses.count('partial'),
                      failed_count=sum(status not in ('success', 'partial') for status in statuses),
                      waiting=len(projects)-len(attempted))
    snapshot.update(evidence={**evidence, 'projects': bundles}, content_allocation=allocation)
    resolveProjects(snapshot, asOf)


def resolveProjects(snapshot: Record, asOf: str) -> None:
    bundles = _record(_record(snapshot.get('evidence')).get('projects'))
    curation = _record(_record(snapshot.get('curation')).get('projects'))
    for project in _records(snapshot.get('projects')):
        name = str(project['full_name'])
        facts = deriveFacts(_record(bundles.get(name)))
        facts['full_name'] = name
        if project.get('observation_status') == 'identity_conflict':
            facts['critical_unknowns'] = _strings(facts.get('critical_unknowns')) + ['identity_conflict']
        content = resolveContent(facts, _record(curation.get(name)), asOf)
        if project.get('observation_status') == 'identity_conflict':
            content['identity_conflict'] = True
        project['content'] = content
        project['automatically_qualified'] = (content.get('review_kind') == 'automatic_template'
                                               and not curation.get(name) and not project.get('seed'))


def attachGrowth(projects: list[Record], history: Record, asOf: str) -> None:
    today = dt.date.fromisoformat(asOf[:10])
    for project in projects:
        series = _record(history.get(str(project.get('history_key', project['full_name']))))
        growth = []
        for days in (1, 7):
            start = str(today - dt.timedelta(days=days))
            old, new = series.get(start), series.get(str(today))
            if project.get('observation_status') == 'fresh' and type(old) is int and type(new) is int:
                growth.append({'start_date': start, 'end_date': str(today), 'start_stars': old,
                               'end_stars': new, 'net_change': new-old})
        project['growth_evidence'] = growth


def _metadata(asOf: str, sourceCommit: str) -> Record:
    return {'schema_version': '4.0', 'rules_version': 'v3.3', 'recommendation_version': 'v4.0',
            'batch_id': uuid.uuid4().hex, 'generated_at': asOf, 'source_commit': sourceCommit}


def _recommend(snapshot: Record, asOf: str, client: GitHubClient, budget: Budget, offline: bool) -> None:
    projects = _records(snapshot.get('projects'))
    attachGrowth(projects, _record(snapshot.get('history')), asOf)
    previous = _record(snapshot.get('recommendations'))
    active = [p for p in projects if not p.get('archived') and not p.get('fork') and
              p.get('observation_status') != 'identity_conflict']
    feed = selectRecommendations(active, previous, asOf)
    if not offline:
        targets = _records(feed.get('recommendations'))
        selectedNames = {p['full_name'] for p in targets}
        recoverable = [p for p in active if p['full_name'] not in selectedNames
                       and _records(_record(p.get('content')).get('usage_paths'))]
        recoverable.sort(key=lambda p: str(p.get('last_path_attempt_at', '')))
        targets = (targets + recoverable)[:20]
        for project in targets:
            project['last_path_attempt_at'] = asOf
        snapshot['evidence'] = refreshPaths(targets,
                                           _record(snapshot.get('evidence')), client, budget, asOf)
        resolveProjects(snapshot, asOf)
        feed = selectRecommendations(active, previous, asOf)
    snapshot['recommendations'] = feed


def _observationReport(previous: Record, snapshot: Record, asOf: str, runKind: str) -> None:
    prior = _record(previous.get('observation_reports'))
    cohort = _strings(prior.get('fixed_cohort')) or [str(p.get('history_key', p['full_name']))
                                                    for p in _records(previous.get('projects'))]
    cohortSet = set(cohort)
    projects = _records(snapshot.get('projects'))
    fresh = [p for p in projects if p.get('observation_status') == 'fresh']
    feed = _record(snapshot.get('recommendations'))
    priorDates = _record(_record(previous.get('recommendations')).get('first_recommended_at'))
    new = [p for p in _records(feed.get('recommendations'))
           if str(p.get('node_id') or p['full_name']) not in priorDates]
    run = {'batch_id': snapshot['batch_id'], 'observed_at': asOf, 'utc_date': asOf[:10],
           'run_kind': runKind, 'planned_run': runKind == 'schedule', 'fresh_count': len(fresh),
           'cohort_size': len(cohort), 'cohort_fresh': sum(str(p.get('history_key', p['full_name']))
                                                        in cohortSet for p in fresh),
           'pool_size': len(projects),
           'pending_candidate_count': len(_records(_record(snapshot.get('pending_candidates')).get('projects'))),
           'usage': snapshot['usage'],
           'new_recommendations': new, 'discovery_counts': feed.get('discovery_counts', {}),
           'recommendation_count': len(_records(feed.get('recommendations'))),
           'recommendation_fresh_count': sum(p.get('observation_status') == 'fresh'
                                              for p in _records(feed.get('recommendations'))),
           'all_selected': [{key: p.get(key) for key in ('full_name', 'node_id', 'observation_status',
                                                       'first_recommended_at', 'discovery_kind')}
                            for p in _records(feed.get('recommendations'))],
           'automatic_new_recommendations': [{key: p.get(key) for key in
                                             ('full_name', 'node_id', 'first_recommended_at')}
                                            for p in new if p.get('discovery_kind') == 'automatic_new'],
           'content_allocation': snapshot.get('content_allocation'),
           'future_reference_set': {'status': 'awaiting_independent_human_reference', 'items': []}}
    snapshot['observation_reports'] = {'fixed_cohort': cohort, 'runs': _records(prior.get('runs')) + [run]}


def _prepare(previous: Record, client: GitHubClient, budget: Budget, asOf: str,
             offline: bool, metadata: Record, runKind: str) -> Record:
    import collect
    discovered, reports = ([], []) if offline else discover(client, budget, asOf)
    snapshot = observe(previous, repositoryPool(previous, discovered, asOf), client, budget, asOf, offline)
    refreshContent(snapshot, client, budget, asOf, offline)
    _recommend(snapshot, asOf, client, budget, offline)
    projects = _records(snapshot.get('projects'))
    collect.attachSummaries(projects, _record(snapshot.get('summaries')), dt.date.fromisoformat(asOf[:10]))
    stats = collect.collectionStats(projects, snapshot['history'],
                                    {str(p['full_name']).lower() for p in _records(previous.get('projects'))}, reports)
    snapshot.update(metadata)
    snapshot.update(collection_stats=stats, count=len(projects), search_reports=reports, usage=asdict(client.usage),
                    offline_preview=offline, observation_started_at=previous.get('observation_started_at') or asOf,
                    warnings=_strings(snapshot.get('observation_errors')))
    for key in ('evidence', 'recommendations', 'pending_candidates'):
        _record(snapshot.get(key)).update(metadata)
    _observationReport(previous, snapshot, asOf, 'offline_preview' if offline else runKind)
    _record(snapshot.get('observation_reports')).update(metadata)
    return snapshot


def _writeData(snapshot: Record, output: Path) -> None:
    hidden = {'history', 'summaries', 'evidence', 'curation', 'recommendations', 'observation_reports',
              'frozen_baseline_names', 'previous_details', 'pending_candidates'}
    documents = {'projects.json': {k: value for k, value in snapshot.items() if k not in hidden},
                 'history.json': snapshot['history'], 'summaries.json': snapshot['summaries'],
                 'evidence.json': snapshot['evidence'], 'recommendations.json': snapshot['recommendations'],
                 'observation-reports.json': snapshot['observation_reports'],
                 'pending-candidates.json': snapshot['pending_candidates']}
    for name, document in documents.items():
        writeJson(output / 'data' / name, document)


def run(root: Path, outputDirectory: Path, client: GitHubClient | None = None,
        offline: bool = False, asOf: str | None = None, sourceCommit: str | None = None,
        runKind: str = 'manual', validator: Callable[..., Record] = validateBatch) -> Record:
    from gitradar.site import buildSite
    root, output = root.resolve(), outputDirectory.resolve()
    if root == output or output == root / 'data' or root / 'data' in output.parents:
        raise ValueError('Collection must use a separate staging directory.')
    output.mkdir(parents=True, exist_ok=True)
    try:
        previous = loadSnapshot(root)
        instant = asOf or utcNow()
        source = sourceCommit or subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=root, text=True).strip()
        metadata = _metadata(instant, source)
        snapshot = _prepare(previous, client or GitHubClient(), Budget(), instant, offline, metadata, runKind)
        if asOf is None and utcNow()[:10] != instant[:10]:
            raise RuntimeError('Collection crossed UTC midnight; publication blocked.')
        _writeData(snapshot, output)
        manifest = cast(Record, buildSite(snapshot, output))
        artifacts = _record(manifest.get('artifacts'))
        for name in DATA_ARTIFACTS:
            relative = 'data/' + name
            artifacts[relative] = hashlib.sha256((output / relative).read_bytes()).hexdigest()
        manifest.update(metadata, artifacts=artifacts, offline_preview=offline)
        writeJson(output / 'build-manifest.json', manifest)
        report = validator(previous, snapshot, manifest, output)
        writeJson(output / 'validation-report.json', report)
        return report
    except Exception as error:
        writeJson(output / 'validation-report.json', {'allowed': False, 'errors': [str(error)],
                                                     'traceback': traceback.format_exc()})
        raise


def _publicationPaths(manifest: Record, output: Path) -> list[Path]:
    paths = []
    for relative, expected in _record(manifest.get('artifacts')).items():
        path = PurePosixPath(relative)
        allowed = relative in ('index.html', 'explore.html', 'scenes.html') or path.parts[0] in ('data', 'projects', 'scenes', 'assets')
        if not allowed or path.is_absolute() or '..' in path.parts or relative in ('data/curation.json', 'data/seed-evidence.json'):
            raise ValueError('Unsafe publication artifact: ' + relative)
        source = output / relative
        if not source.is_file() or source.is_symlink() or hashlib.sha256(source.read_bytes()).hexdigest() != expected:
            raise ValueError('Publication artifact changed: ' + relative)
        paths.append(Path(relative))
    return paths


def promote(outputDirectory: Path, root: Path) -> None:
    output = outputDirectory.resolve()
    report = _record(readJson(output / 'validation-report.json', {}))
    manifest = _record(readJson(output / 'build-manifest.json', {}))
    if report.get('allowed') is not True or manifest.get('offline_preview'):
        raise ValueError('Only validated live batches can be published.')
    paths = _publicationPaths(manifest, output)
    if not all('data/' + name in _record(manifest.get('artifacts')) for name in DATA_ARTIFACTS):
        raise ValueError('Publication manifest lacks complete data artifacts.')
    candidate = _record(readJson(output / 'data/projects.json', {}))
    for key in ('history', 'evidence', 'recommendations'):
        candidate[key] = readJson(output / 'data' / (key + '.json'), {})
    current = loadSnapshot(root)
    validation = validateBatch(current, candidate, manifest, output)
    if validation.get('allowed') is not True:
        writeJson(output / 'promotion-validation-report.json', validation)
        raise ValueError('Formal state changed or staged batch is invalid; publication blocked.')
    # 在首次正式写入前检查全部哈希；失败生成永不进入此步骤。
    for relative in paths + [Path('build-manifest.json')]:
        target = root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = target.with_name('.' + target.name + '.v4-staged')
        shutil.copyfile(output / relative, temporary)
        os.replace(temporary, target)


def main() -> None:
    parser = argparse.ArgumentParser(description='GitRadar V4 isolated collection and validation')
    parser.add_argument('--output-dir', type=Path, default=Path('.v4-output'))
    parser.add_argument('--publish-to', type=Path)
    parser.add_argument('--offline', action='store_true')
    parser.add_argument('--promote-only', action='store_true')
    options = parser.parse_args()
    root = Path(__file__).resolve().parent.parent
    if not options.promote_only:
        report = run(root, options.output_dir, GitHubClient(os.getenv('GH_API_TOKEN')),
                     options.offline, runKind=os.getenv('GITHUB_EVENT_NAME', 'manual'))
        if report.get('allowed') is not True:
            raise SystemExit('Batch validation failed; inspect ' + str(options.output_dir / 'validation-report.json'))
    if options.publish_to:
        promote(options.output_dir, options.publish_to)
    elif options.promote_only:
        raise SystemExit('--promote-only requires --publish-to')
    print('V4 batch ready:', options.output_dir)
