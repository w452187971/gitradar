import base64
import copy
import datetime as dt
import json
import tempfile
import unittest
from dataclasses import asdict
from pathlib import Path
from unittest.mock import patch

import collect
from gitradar import pipeline
from gitradar.models import Usage
from gitradar.github_client import GitHubClient, HttpResponse

AS_OF = '2026-10-20T15:00:00Z'


class PipelineTests(unittest.TestCase):
    def test_due_evidence_preempts_slots_and_last_attempt_prevents_starvation(self):
        projects = [{'full_name': f'o/p{i}'} for i in range(25)]
        evidence = {'projects': {p['full_name']: {'last_attempt_at': '2026-10-19T00:00:00Z',
                                                           'refs': [{'checked_at': '2026-09-01T00:00:00Z'}]}
                                 for p in projects}}
        evidence['projects']['o/p24']['last_attempt_at'] = '2026-09-01T00:00:00Z'
        selected, report = pipeline.scheduleContent(projects, evidence, {}, AS_OF)
        self.assertEqual(len(selected), 20)
        self.assertEqual(selected[0]['full_name'], 'o/p24')
        self.assertEqual(report['waiting'], 5)
        self.assertEqual(report['actual']['due'], 20)

    def test_history_key_loader_handles_repository_rename(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            data = root / 'data'
            data.mkdir()
            project = {'full_name': 'o/new', 'history_key': 'o/old', 'node_id': 'N',
                       'created_at': '2020-01-01T00:00:00Z', 'html_url': 'https://github.com/o/new',
                       'stargazers_count': 10}
            (data / 'projects.json').write_text(json.dumps({'projects': [project]}))
            (data / 'history.json').write_text(json.dumps({'o/old': {'2026-10-19': 10}}))
            self.assertEqual(collect.loadState(data)[0][0]['history_key'], 'o/old')

    def test_growth_evidence_only_uses_real_history_endpoints(self):
        project = {'full_name': 'o/new', 'history_key': 'o/old', 'observation_status': 'fresh'}
        pipeline.attachGrowth([project], {'o/old': {'2026-10-13': 10, '2026-10-20': 22}}, AS_OF)
        self.assertEqual(project['growth_evidence'][0]['net_change'], 12)
        self.assertEqual(project['growth_evidence'][0]['start_date'], '2026-10-13')
        self.assertEqual(len(project['growth_evidence']), 1)

    def test_offline_run_keeps_history_and_publishes_no_fresh_observations(self):
        with tempfile.TemporaryDirectory() as source, tempfile.TemporaryDirectory() as output:
            root = self.makeState(Path(source))
            before = (root / 'data/history.json').read_bytes()
            result = pipeline.run(root, Path(output), offline=True, asOf=AS_OF, sourceCommit='abc')
            self.assertTrue(result['allowed'], result)
            document = json.loads((Path(output) / 'data/projects.json').read_text())
            self.assertEqual(document['projects'][0]['observation_status'], 'deferred')
            self.assertTrue(document['offline_preview'])
            self.assertEqual((root / 'data/history.json').read_bytes(), before)
            self.assertEqual(json.loads((Path(output) / 'data/history.json').read_text()),
                             {'o/p': {'2026-10-19': 10}})
            report = json.loads((Path(output) / 'data/observation-reports.json').read_text())
            self.assertEqual(report['runs'][0]['fresh_count'], 0)
            self.assertEqual(report['runs'][0]['run_kind'], 'offline_preview')

    def test_explicit_offset_uses_the_actual_utc_day_for_replay(self):
        instants = [('2026-10-21T01:00:00+08:00', '2026-10-20T17:00:00Z'),
                    ('2026-10-19T23:00:00-02:00', '2026-10-20T01:00:00Z')]
        for supplied, utc in instants:
            with self.subTest(asOf=supplied), tempfile.TemporaryDirectory() as source, tempfile.TemporaryDirectory() as output:
                root = self.makeState(Path(source))
                result = pipeline.run(root, Path(output), offline=True, asOf=supplied, sourceCommit='utc-fixture')
                self.assertTrue(result['allowed'], result)
                document = json.loads((Path(output) / 'data/projects.json').read_text())
                report = json.loads((Path(output) / 'data/observation-reports.json').read_text())
                self.assertEqual(document['generated_at'], utc)
                self.assertEqual(report['runs'][0]['utc_date'], '2026-10-20')
                self.assertEqual(report['runs'][0]['observed_at'], utc)

    def test_failed_validation_never_changes_formal_artifacts(self):
        with tempfile.TemporaryDirectory() as source, tempfile.TemporaryDirectory() as output:
            root = self.makeState(Path(source))
            result = pipeline.run(root, Path(output), offline=True, asOf=AS_OF,
                                  sourceCommit='abc', validator=lambda *args: {'allowed': False, 'errors': ['blocked']})
            self.assertFalse(result['allowed'])
            self.assertFalse((root / 'index.html').exists())
            self.assertTrue((Path(output) / 'validation-report.json').exists())
            with self.assertRaises(ValueError):
                pipeline.promote(Path(output), root)

    def test_freshness_and_budget_are_not_inferred_from_search(self):
        with tempfile.TemporaryDirectory() as source, tempfile.TemporaryDirectory() as output:
            root = self.makeState(Path(source))
            client = FailedClient()
            result = pipeline.run(root, Path(output), client=client, asOf=AS_OF, sourceCommit='abc')
            self.assertTrue(result['allowed'], result)
            document = json.loads((Path(output) / 'data/projects.json').read_text())
            self.assertNotEqual(document['projects'][0]['observation_status'], 'fresh')
            self.assertEqual(client.refs[0]['full_name'], 'o/p')
            self.assertEqual(document['usage']['rest_requests'], 0)
            self.assertIn('2026-10-19', json.loads((Path(output) / 'data/history.json').read_text())['o/p'])

    def test_main_uses_v4_cli_entry(self):
        with patch.object(pipeline, 'main') as runV4:
            collect.main()
        runV4.assert_called_once_with()

    def test_seed_metadata_never_becomes_a_star_observation(self):
        with tempfile.TemporaryDirectory() as source, tempfile.TemporaryDirectory() as output:
            root = self.makeState(Path(source))
            bundle = {'full_name': 'o/seed', 'node_id': 'S', 'refs': [
                {'source_kind': 'repository', 'text': json.dumps({
                    'created_at': '2020-01-01T00:00:00Z', 'html_url': 'https://github.com/o/seed'})}]}
            (root / 'data/seed-evidence.json').write_text(json.dumps({'projects': {'o/seed': bundle}}))
            (root / 'data/curation.json').write_text(json.dumps({'projects': {'o/seed': {'seed': True}}}))
            result = pipeline.run(root, Path(output), offline=True, asOf=AS_OF, sourceCommit='abc')
            self.assertTrue(result['allowed'], result)
            document = json.loads((Path(output) / 'data/projects.json').read_text())
            seed = next(p for p in document['projects'] if p['full_name'] == 'o/seed')
            self.assertIsNone(seed['stargazers_count'])
            self.assertNotEqual(seed['observation_status'], 'fresh')
            self.assertTrue(seed['seed'])
            projects, history, summaries = collect.loadState(Path(output) / 'data')
            self.assertNotIn('o/seed', history)
            self.assertEqual(len(projects), 2)

    def test_machine_evidence_takes_priority_over_seed_file(self):
        with tempfile.TemporaryDirectory() as source:
            root = self.makeState(Path(source))
            (root / 'data/seed-evidence.json').write_text(json.dumps({'projects': {'seed': {}}}))
            (root / 'data/evidence.json').write_text(json.dumps({'projects': {'machine': {}}}))
            self.assertEqual(set(pipeline.loadSnapshot(root)['evidence']['projects']), {'machine'})

    def test_promote_rejects_history_changed_after_isolated_collection(self):
        with tempfile.TemporaryDirectory() as source, tempfile.TemporaryDirectory() as output:
            root = self.makeState(Path(source))
            pipeline.run(root, Path(output), client=FailedClient(), asOf=AS_OF, sourceCommit='abc')
            formal = root / 'data/history.json'
            formal.write_text(json.dumps({'o/p': {'2026-10-18': 8, '2026-10-19': 10}}))
            with self.assertRaises(ValueError):
                pipeline.promote(Path(output), root)
            self.assertIn('2026-10-18', json.loads(formal.read_text())['o/p'])

    def test_expired_path_is_rechecked_even_when_it_blocks_current_feed(self):
        project = {'full_name': 'o/expired', 'content': {'usage_paths': [
            {'url': 'https://github.com/o/expired/releases'}]}}
        snapshot = {'projects': [project], 'history': {}, 'evidence': {'projects': {}},
                    'recommendations': {}}
        with patch.object(pipeline, 'refreshPaths', return_value={'projects': {}}) as refresh:
            pipeline._recommend(snapshot, AS_OF, FailedClient(), pipeline.Budget(), False)
        self.assertEqual(refresh.call_args.args[0][0]['full_name'], 'o/expired')

    def test_real_client_transport_runs_observation_content_validation_and_promotion(self):
        repository = {'full_name': 'o/p', 'node_id': 'N', 'created_at': '2020-01-01T00:00:00Z',
                      'html_url': 'https://github.com/o/p', 'stargazers_count': 11, 'description': '',
                      'archived': False, 'fork': False, 'language': 'Python', 'topics': []}

        def transport(method, url, headers, body):
            if '/search/' in url:
                return HttpResponse(200, {}, {'items': [repository], 'total_count': 1})
            if url.endswith('/graphql'):
                node = {'id': 'N', 'nameWithOwner': 'o/p', 'createdAt': repository['created_at'],
                        'stargazerCount': 11, 'url': repository['html_url']}
                return HttpResponse(200, {}, {'data': {'r0': node, 'rateLimit': {'cost': 1, 'remaining': 900}}})
            if url.endswith('/readme'):
                return HttpResponse(200, {}, {'encoding': 'base64',
                                             'content': base64.b64encode(b'A document tool.').decode()})
            if url.endswith('/releases/latest'):
                return HttpResponse(404, {}, {})
            return HttpResponse(200, {}, repository)

        with tempfile.TemporaryDirectory() as source, tempfile.TemporaryDirectory() as output:
            root = self.makeState(Path(source))
            client = GitHubClient(transport=transport, now=lambda: AS_OF, sleep=lambda _: None)
            report = pipeline.run(root, Path(output), client=client, asOf=AS_OF, sourceCommit='abc')
            self.assertTrue(report['allowed'], report)
            document = json.loads((Path(output) / 'data/projects.json').read_text())
            self.assertEqual(document['projects'][0]['observation_status'], 'fresh')
            self.assertEqual(document['projects'][0]['delta_1d'], 1)
            self.assertEqual(document['usage']['search_requests'], 18)
            self.assertEqual(document['usage']['content_requests'], 3)
            self.assertEqual(document['usage']['graphql_points'], 1)
            pipeline.promote(Path(output), root)
            self.assertEqual(json.loads((root / 'data/history.json').read_text())['o/p']['2026-10-20'], 11)
            self.assertTrue((root / 'index.html').is_file())
            self.assertFalse((root / 'data/curation.json').exists())

    def test_unobserved_search_candidates_persist_outside_formal_projects_and_retry(self):
        with tempfile.TemporaryDirectory() as source, tempfile.TemporaryDirectory() as output:
            root = self.makeState(Path(source))
            new = {'full_name': 'o/new', 'node_id': 'NEW', 'stargazers_count': 99,
                   'created_at': '2026-10-19T00:00:00Z', 'html_url': 'https://github.com/o/new'}
            with patch.object(pipeline, 'discover', return_value=([new], [])):
                report = pipeline.run(root, Path(output), client=FailedClient(), asOf=AS_OF, sourceCommit='abc')
            self.assertTrue(report['allowed'], report)
            pipeline.promote(Path(output), root)
            projects, history, _ = collect.loadState(root / 'data')
            self.assertEqual([p['full_name'] for p in projects], ['o/p'])
            self.assertNotIn('o/new', history)
            queued = json.loads((root / 'data/pending-candidates.json').read_text())
            self.assertEqual(queued['projects'][0]['first_observed_at'], AS_OF)
            self.assertEqual(queued['projects'][0]['discovery_origin'], 'automatic')
            client = FailedClient()
            with patch.object(pipeline, 'discover', return_value=([], [])):
                pipeline.run(root, Path(output), client=client, asOf=AS_OF, sourceCommit='def')
            self.assertIn('o/new', [ref['full_name'] for ref in client.refs])
            run = json.loads((Path(output) / 'data/observation-reports.json').read_text())['runs'][-1]
            self.assertEqual(run['cohort_size'], 1)

    def test_live_unobserved_seed_is_queued_without_null_stars_in_formal_projects(self):
        with tempfile.TemporaryDirectory() as source, tempfile.TemporaryDirectory() as output:
            root = self.makeState(Path(source))
            bundle = {'full_name': 'o/seed', 'node_id': 'S', 'refs': [
                {'source_kind': 'repository', 'text': json.dumps({
                    'created_at': '2020-01-01T00:00:00Z', 'html_url': 'https://github.com/o/seed'})}]}
            (root / 'data/seed-evidence.json').write_text(json.dumps({'projects': {'o/seed': bundle}}))
            (root / 'data/curation.json').write_text(json.dumps({'projects': {'o/seed': {'seed': True}}}))
            pipeline.run(root, Path(output), client=FailedClient(), asOf=AS_OF, sourceCommit='abc')
            document = json.loads((Path(output) / 'data/projects.json').read_text())
            self.assertEqual([p['full_name'] for p in document['projects']], ['o/p'])
            self.assertTrue(all(type(p['stargazers_count']) is int for p in document['projects']))
            queue = json.loads((Path(output) / 'data/pending-candidates.json').read_text())
            self.assertIsNone(queue['projects'][0]['stargazers_count'])
            self.assertTrue(queue['projects'][0]['seed'])

    def test_content_single_remaining_request_is_used_instead_of_assuming_three(self):
        class SingleRequestClient(FailedClient):
            def readProjectEvidence(self, ref, previous, budget):
                self.usage.content_requests += 1
                self.usage.rest_requests += 1
                return super().readProjectEvidence(ref, previous, budget)
        client = SingleRequestClient()
        client.usage.content_requests = 59
        snapshot = {'projects': [{'full_name': 'o/p', 'node_id': 'N'}], 'evidence': {'projects': {}}}
        pipeline.refreshContent(snapshot, client, pipeline.Budget(), AS_OF, False)
        self.assertEqual(client.usage.content_requests, 60)
        self.assertEqual(snapshot['content_allocation']['attempted'], ['o/p'])
        self.assertEqual(snapshot['content_allocation']['requests_used'], 1)
        self.assertEqual(snapshot['content_allocation']['successful_count'], 0)
        self.assertEqual(snapshot['content_allocation']['failed_count'], 1)

    def test_formal_v4_loader_rejects_unobserved_records_without_history(self):
        with tempfile.TemporaryDirectory() as source:
            root = self.makeState(Path(source))
            path = root / 'data/projects.json'
            document = json.loads(path.read_text())
            document.update(schema_version='4.0', offline_preview=False)
            document['projects'].append({'full_name': 'o/orphan', 'node_id': 'ORPHAN',
                                          'created_at': '2026-10-19T00:00:00Z',
                                          'html_url': 'https://github.com/o/orphan',
                                          'stargazers_count': 99, 'observation_status': 'retained'})
            path.write_text(json.dumps(document))
            with self.assertRaises(ValueError):
                collect.loadState(root / 'data')

    def test_queued_candidate_enters_formal_projects_only_after_successful_observation(self):
        class SuccessClient(FailedClient):
            def fetchObservations(self, refs, budget):
                self.refs = copy.deepcopy(refs)
                observations = [{**ref, 'node_id': ref.get('node_id') or 'OLD',
                                 'stargazers_count': 101, 'observed_at': AS_OF,
                                 'html_url': 'https://github.com/' + ref['full_name'],
                                 'status': 'success', 'archived': False, 'fork': False} for ref in refs]
                return {'observations': observations, 'errors': [], 'usage': asdict(self.usage)}
        with tempfile.TemporaryDirectory() as source, tempfile.TemporaryDirectory() as output:
            root = self.makeState(Path(source))
            pending = {'full_name': 'o/new', 'node_id': 'NEW', 'stargazers_count': 99,
                       'created_at': '2026-10-19T00:00:00Z', 'html_url': 'https://github.com/o/new',
                       'first_observed_at': '2026-10-19T12:00:00Z', 'discovery_origin': 'automatic'}
            (root / 'data/pending-candidates.json').write_text(json.dumps({'projects': [pending]}))
            with patch.object(pipeline, 'discover', return_value=([], [])):
                report = pipeline.run(root, Path(output), client=SuccessClient(), asOf=AS_OF, sourceCommit='abc')
            self.assertTrue(report['allowed'], report)
            pipeline.promote(Path(output), root)
            projects, history, _ = collect.loadState(root / 'data')
            candidate = next(project for project in projects if project['full_name'] == 'o/new')
            self.assertEqual(candidate['first_observed_at'], pending['first_observed_at'])
            self.assertEqual(candidate['observation_status'], 'fresh')
            self.assertEqual(history['o/new']['2026-10-20'], 101)
            queue = json.loads((root / 'data/pending-candidates.json').read_text())
            self.assertEqual(queue['projects'], [])
            self.assertEqual(queue['batch_id'], json.loads((root / 'data/projects.json').read_text())['batch_id'])

    def advancingSourceRun(self, sourceTime='2026-10-20T15:05:00Z', explicit=False,
                           start='2026-10-20T15:00:00Z', finish='2026-10-20T15:06:00Z'):
        from test_v4_content import sampleContent
        facts, editorial = sampleContent()
        state = {'now': start}
        class AdvancingClient(FailedClient):
            def readProjectEvidence(self, ref, previous, budget):
                state['now'] = sourceTime if sourceTime[:4] != '2050' else '2026-10-20T15:05:00Z'
                fetched = copy.deepcopy(previous)
                for evidence in fetched['refs']:
                    evidence.update(checked_at=sourceTime, status=200)
                fetched.update(status='success', errors=[])
                return fetched
            def exchange(self, *args):
                state['now'] = finish
                return HttpResponse(200, {}, None)
        with tempfile.TemporaryDirectory() as source, tempfile.TemporaryDirectory() as output:
            root = Path(source)
            (root/'data').mkdir()
            project = {'full_name': 'demo/search', 'node_id': 'N', 'created_at': '2020-01-01T00:00:00Z',
                       'html_url': 'https://github.com/demo/search', 'stargazers_count': 10}
            bundle = {'full_name': 'demo/search', 'node_id': 'N', 'refs': facts['evidence_refs'],
                      'facts': {key: {'value': editorial[key], 'ref_ids': [key], 'complete': True}
                                for key in facts['claims']}}
            pipeline.writeJson(root/'data/projects.json', {'projects': [project]})
            pipeline.writeJson(root/'data/history.json', {'demo/search': {'2026-10-19': 10}})
            pipeline.writeJson(root/'data/evidence.json', {'projects': {'demo/search': bundle}})
            pipeline.writeJson(root/'data/curation.json', {'projects': {'demo/search': editorial}})
            with patch.object(pipeline, 'utcNow', side_effect=lambda: state['now']):
                report = pipeline.run(root, Path(output), client=AdvancingClient(),
                                      asOf=start if explicit else None, sourceCommit='clock-fixture')
            self.assertTrue(report['allowed'], report)
            document = json.loads((Path(output)/'data/projects.json').read_text())
            evidence = json.loads((Path(output)/'data/evidence.json').read_text())
            feed = json.loads((Path(output)/'data/recommendations.json').read_text())
            return document, evidence, feed

    def test_live_generation_cutoff_includes_successful_checks_completed_during_collection(self):
        document, evidence, feed = self.advancingSourceRun()
        self.assertEqual(document['generated_at'], '2026-10-20T15:06:00Z')
        self.assertEqual(feed['selected_count'], 1)
        self.assertEqual(document['projects'][0]['content']['effective_status'], 'published')
        refs = evidence['projects']['demo/search']['refs']
        self.assertTrue(all(ref['checked_at'] == '2026-10-20T15:05:00Z' for ref in refs))
        checked = next(ref for ref in refs if ref['id'] == 'usage_paths')
        self.assertEqual(checked['path_checked_at'], '2026-10-20T15:06:00Z')

    def test_explicit_replay_cutoff_remains_fixed_and_future_checks_do_not_pass(self):
        document, _, feed = self.advancingSourceRun(explicit=True)
        self.assertEqual(document['generated_at'], '2026-10-20T15:00:00Z')
        self.assertEqual(feed['selected_count'], 0)

    def test_live_cutoff_does_not_accept_arbitrary_future_source_timestamp(self):
        document, _, feed = self.advancingSourceRun(sourceTime='2050-01-01T00:00:00Z')
        self.assertEqual(document['generated_at'], '2026-10-20T15:06:00Z')
        self.assertEqual(feed['selected_count'], 0)
        self.assertIn('stale_evidence:purpose', document['projects'][0]['content']['invalidation_reasons'])

    def test_advancing_live_collection_cannot_publish_across_utc_midnight(self):
        with self.assertRaisesRegex(RuntimeError, 'UTC midnight'):
            self.advancingSourceRun(start='2026-10-20T23:59:00Z', sourceTime='2026-10-21T00:00:30Z',
                                    finish='2026-10-21T00:01:00Z')

    def test_refresh_content_resolves_against_its_real_completion_cutoff(self):
        from test_v4_content import sampleContent
        facts, editorial = sampleContent()
        complete = '2026-10-20T15:05:00Z'
        class CompleteClient(FailedClient):
            def readProjectEvidence(self, ref, previous, budget):
                fetched = copy.deepcopy(previous)
                for item in fetched['refs']:
                    item['checked_at'] = complete
                return fetched
        snapshot = {'projects': [{'full_name': 'demo/search', 'node_id': 'N'}],
                    'evidence': {'projects': {'demo/search': {'full_name': 'demo/search', 'node_id': 'N',
                                'refs': facts['evidence_refs'], 'facts': {field: {'value': editorial[field],
                                'ref_ids': [field]} for field in facts['claims']}}}},
                    'curation': {'projects': {'demo/search': editorial}}}
        pipeline.refreshContent(snapshot, CompleteClient(), pipeline.Budget(), AS_OF, False, clock=lambda: complete)
        self.assertEqual(snapshot['projects'][0]['content']['effective_status'], 'published')

    def test_offline_default_cutoff_is_frozen_after_its_initial_clock_read(self):
        with tempfile.TemporaryDirectory() as source, tempfile.TemporaryDirectory() as output:
            root = self.makeState(Path(source))
            with patch.object(pipeline, 'utcNow', side_effect=[AS_OF, AssertionError('Offline clock advanced')]):
                report = pipeline.run(root, Path(output), offline=True, sourceCommit='offline-clock')
            self.assertTrue(report['allowed'], report)
            self.assertEqual(json.loads((Path(output)/'data/projects.json').read_text())['generated_at'], AS_OF)

    def makeState(self, root):
        (root / 'data').mkdir()
        project = {'full_name': 'o/p', 'created_at': '2020-01-01T00:00:00Z',
                   'html_url': 'https://github.com/o/p', 'stargazers_count': 10}
        (root / 'data/projects.json').write_text(json.dumps({'projects': [project]}))
        (root / 'data/history.json').write_text(json.dumps({'o/p': {'2026-10-19': 10}}))
        return root


class FailedClient:
    def __init__(self):
        self.usage = Usage()
        self.refs = []

    def requestRest(self, *args):
        raise ValueError('search unavailable')

    def fetchObservations(self, refs, budget):
        self.refs = copy.deepcopy(refs)
        return {'observations': [{'full_name': ref['full_name'], 'status': 'failed',
                                  'error': 'unavailable'} for ref in refs],
                'errors': ['GraphQL unavailable'], 'usage': asdict(self.usage)}

    def fetchRestObservations(self, refs, budget):
        return {'observations': [], 'errors': ['REST unavailable'], 'usage': asdict(self.usage)}

    def readProjectEvidence(self, ref, previous, budget):
        return {'full_name': ref['full_name'], 'refs': [], 'status': 'failed', 'errors': ['unavailable']}


if __name__ == '__main__':
    unittest.main()
