import copy
import unittest

from gitradar.observations import applyObservations, legacyProjectView


CREATED = '2025-01-01T00:00:00Z'
DATE = '2026-10-20'


def snapshot(identity='R1'):
    return {'projects': [{'full_name': 'a/old', 'node_id': identity, 'history_key': 'a/old',
            'created_at': CREATED, 'stargazers_count': 100, 'summary_zh': '旧内容'}],
            'history': {'a/old': {'2026-10-19': 100, '2026-10-13': 105}}}


def observation(**changes):
    value = {'full_name': 'a/old', 'node_id': 'R1', 'created_at': CREATED,
             'observed_at': DATE+'T12:00:00Z', 'stargazers_count': 95, 'status': 'success'}
    value.update(changes)
    return value


class ObservationTests(unittest.TestCase):
    def test_rename_retains_history_and_saved_aliases(self):
        original = snapshot()
        before = copy.deepcopy(original)
        result = applyObservations(original, [observation(full_name='b/new')], DATE)
        project = result['projects'][0]
        self.assertEqual(project['full_name'], 'b/new')
        self.assertEqual(project['history_key'], 'a/old')
        self.assertEqual(result['history']['a/old'][DATE], 95)
        self.assertEqual(result['saved_aliases']['a/old'], 'b/new')
        self.assertEqual(original, before)
        self.assertEqual(project['delta_1d'], -5)
        self.assertEqual(project['delta_7d'], -10)
        self.assertEqual(legacyProjectView(project)['summary_zh'], '旧内容')

    def test_legacy_created_at_is_verified_before_binding_node(self):
        old = snapshot()
        old['projects'][0].pop('node_id')
        result = applyObservations(old, [observation(created_at='2026-01-01T00:00:00Z')], DATE)
        self.assertNotIn(DATE, result['history']['a/old'])
        self.assertEqual(result['projects'][0]['observation_status'], 'identity_conflict')
        valid = applyObservations(old, [observation()], DATE)
        self.assertEqual(valid['projects'][0]['node_id'], 'R1')

    def test_same_name_recreated_is_isolated(self):
        result = applyObservations(snapshot(), [observation(node_id='R2')], DATE)
        self.assertNotIn(DATE, result['history']['a/old'])
        self.assertEqual(result['projects'][0]['node_id'], 'R1')
        self.assertEqual(result['projects'][0]['observation_status'], 'identity_conflict')
        self.assertIsNone(result['projects'][0]['delta_1d'])

    def test_partial_failure_keeps_old_values_and_missing_dates(self):
        original = snapshot()
        result = applyObservations(original, [observation(status='failed', error='timeout')], DATE)
        self.assertEqual(result['history'], original['history'])
        self.assertEqual(result['projects'][0]['stargazers_count'], 100)
        self.assertEqual(result['projects'][0]['observation_status'], 'retained')
        empty = snapshot()
        empty['history']['a/old'].pop('2026-10-19')
        fresh = applyObservations(empty, [observation()], DATE)
        self.assertIsNone(fresh['projects'][0]['delta_1d'])
        self.assertNotIn('2026-10-19', fresh['history']['a/old'])

    def test_cross_utc_date_and_invalid_star_never_write(self):
        for item in [observation(observed_at='2026-10-21T00:00:00Z'), observation(stargazers_count=-1),
                     observation(observed_at='2026-10-20T00:30:00+08:00')]:
            with self.subTest(item=item):
                result = applyObservations(snapshot(), [item], DATE)
                self.assertNotIn(DATE, result['history']['a/old'])

    def test_same_day_rerun_changes_only_today_and_archived_is_observed(self):
        first = applyObservations(snapshot(), [observation()], DATE)
        result = applyObservations(first, [observation(stargazers_count=90, archived=True)], DATE)
        self.assertEqual(result['history']['a/old'], {'2026-10-19': 100, '2026-10-13': 105, DATE: 90})
        self.assertTrue(result['projects'][0]['archived'])
        self.assertEqual(result['projects'][0]['observation_status'], 'fresh')

    def test_history_owner_collision_does_not_merge_series(self):
        old = snapshot()
        old['projects'].append({'full_name': 'b/new', 'node_id': 'R2', 'created_at': CREATED,
                                'history_key': 'b/new', 'stargazers_count': 10})
        old['history']['b/new'] = {'2026-10-19': 10}
        result = applyObservations(old, [observation(full_name='b/new')], DATE)
        self.assertEqual(result['history'], old['history'])
        self.assertEqual(result['projects'][0]['observation_status'], 'identity_conflict')

    def test_candidate_score_is_recomputed_using_unchanged_v33_formula(self):
        result = applyObservations(snapshot(), [observation()], DATE)
        age = 657
        expected = round((-10)*2 + (-5)*3 + 95/(age+12)*3, 1)
        self.assertEqual(result['projects'][0]['discovery_score'], expected)

    def test_missing_observation_preserves_real_last_observed_time(self):
        old = snapshot()
        old['projects'][0]['last_observed_at'] = '2026-10-19T22:00:00Z'
        result = applyObservations(old, [], DATE)
        self.assertEqual(result['projects'][0]['last_observed_at'], '2026-10-19T22:00:00Z')
        self.assertEqual(result['projects'][0]['observation_status'], 'deferred')

    def test_confirmed_unavailable_state_survives_timeouts_and_is_cleared_by_success(self):
        for httpStatus in [404, 410]:
            original = snapshot()
            unavailable = observation(status='not_found', http_status=httpStatus, error='Confirmed unavailable')
            result = applyObservations(original, [unavailable], DATE)
            project = result['projects'][0]
            self.assertEqual(project['http_status'], httpStatus)
            self.assertEqual(project['status'], 'not_found')
            self.assertEqual(project['observation_status'], 'not_found')
            self.assertEqual(result['history'], original['history'])
            self.assertIsNone(project['delta_1d'])
            self.assertIsNone(project['delta_7d'])
            retained = applyObservations(result, [observation(status='failed', error='timeout')], DATE)
            self.assertEqual(retained['projects'][0]['http_status'], httpStatus)
            self.assertEqual(retained['projects'][0]['status'], 'not_found')
            deferred = applyObservations(retained, [], DATE)
            self.assertEqual(deferred['projects'][0]['observation_status'], 'not_found')
            recovered = applyObservations(retained, [observation()], DATE)
            self.assertNotIn('http_status', recovered['projects'][0])
            self.assertEqual(recovered['projects'][0]['status'], 'success')
            self.assertEqual(recovered['projects'][0]['observation_status'], 'fresh')
            self.assertEqual(recovered['history']['a/old'][DATE], 95)

    def test_generic_failure_does_not_invent_unavailability(self):
        result = applyObservations(snapshot(), [observation(status='failed', error='unknown GraphQL null')], DATE)
        self.assertNotIn('http_status', result['projects'][0])
        self.assertNotEqual(result['projects'][0].get('status'), 'not_found')
        self.assertEqual(result['projects'][0]['observation_status'], 'retained')


class InitialRenameIntegrationTests(unittest.TestCase):
    oldName = 'JeroenCorthout/TheMachine'
    newName = 'Salesflare/TheMachine'
    createdAt = '2026-10-15T20:40:05Z'
    nodeId = 'R_kgDOVLdUZA'
    asOf = '2026-10-21T12:00:00Z'

    def fetchRename(self, createdAt=None, historyKey=None):
        import json
        from gitradar.github_client import GitHubClient, HttpResponse
        from gitradar.models import Budget
        self.requests = []
        def transport(method, url, headers, body):
            self.requests.append(json.loads(body)['query'])
            return HttpResponse(200, {}, {'data': {'r0': {
                'id': self.nodeId, 'nameWithOwner': self.newName, 'stargazerCount': 10,
                'createdAt': createdAt or self.createdAt, 'isArchived': False, 'isFork': False,
                'url': 'https://github.com/' + self.newName, 'description': 'The same description.'},
                'rateLimit': {'cost': 1, 'remaining': 999}}})
        client = GitHubClient(transport=transport, now=lambda: self.asOf)
        ref = {'full_name': self.oldName, 'created_at': self.createdAt}
        if historyKey:
            ref['history_key'] = historyKey
        batch = client.fetchObservations([ref], Budget())
        self.assertEqual(batch['errors'], [])
        self.assertEqual(batch['usage']['identity_requests'], 0)
        self.assertEqual(batch['usage']['graphql_batches'], 1)
        self.assertIn('owner: "JeroenCorthout"', self.requests[0])
        self.assertIn('name: "TheMachine"', self.requests[0])
        return batch

    def previous(self, historyKey=None):
        key = historyKey or self.oldName
        return {'projects': [{'full_name': self.oldName, 'created_at': self.createdAt,
                'description': 'The same description.', 'stargazers_count': 10, 'history_key': key}],
                'history': {key: {'2026-10-19': 9, '2026-10-20': 10}}}

    def test_first_identity_binding_rename_keeps_original_history_and_favorites(self):
        old = self.previous()
        before = copy.deepcopy(old)
        result = applyObservations(old, self.fetchRename(), '2026-10-21')
        self.assertEqual(len(result['projects']), 1)
        project = result['projects'][0]
        self.assertEqual(project['full_name'], self.newName)
        self.assertEqual(project['node_id'], self.nodeId)
        self.assertEqual(project['history_key'], self.oldName)
        self.assertEqual(project['observation_status'], 'fresh')
        self.assertEqual(project['delta_1d'], 0)
        self.assertEqual(result['history'], {self.oldName: {'2026-10-19': 9, '2026-10-20': 10, '2026-10-21': 10}})
        self.assertEqual(result['saved_aliases'][self.oldName], self.newName)
        self.assertEqual(old, before)

    def test_mismatched_creation_time_does_not_merge_even_with_identical_description(self):
        old = self.previous()
        result = applyObservations(old, self.fetchRename('2026-10-16T20:40:05Z'), '2026-10-21')
        self.assertEqual(len(result['projects']), 1)
        self.assertEqual(result['history'], old['history'])
        self.assertEqual(result['projects'][0]['full_name'], self.oldName)
        self.assertNotIn('node_id', result['projects'][0])
        self.assertEqual(result['projects'][0]['observation_status'], 'identity_conflict')
        self.assertIsNone(result['projects'][0]['delta_1d'])
        self.assertEqual(result['saved_aliases'], {})

    def test_explicit_original_history_key_also_associates_the_requested_repository(self):
        key = 'OriginalOwner/OriginalMachine'
        old = self.previous(key)
        result = applyObservations(old, self.fetchRename(historyKey=key), '2026-10-21')
        self.assertEqual(len(result['projects']), 1)
        self.assertEqual(result['projects'][0]['full_name'], self.newName)
        self.assertEqual(result['projects'][0]['history_key'], key)
        self.assertEqual(set(result['history']), {key})
        self.assertEqual(result['history'][key]['2026-10-21'], 10)

    def duplicateBatch(self, reverse=False, createdAt=None, targetAvailable=True):
        from gitradar.github_client import GitHubClient, HttpResponse
        from gitradar.models import Budget
        refs = [{'full_name': self.oldName, 'created_at': self.createdAt},
                {'full_name': self.newName, 'node_id': self.nodeId, 'created_at': self.createdAt,
                 'history_key': self.newName}]
        if reverse:
            refs.reverse()
        data = {'rateLimit': {'cost': 1, 'remaining': 999}}
        for index, ref in enumerate(refs):
            data['r'+str(index)] = None if not targetAvailable and ref['full_name'] == self.newName else {
                'id': self.nodeId, 'nameWithOwner': self.newName, 'stargazerCount': 10,
                'createdAt': createdAt if ref['full_name'] == self.oldName and createdAt else self.createdAt,
                'isArchived': False, 'isFork': False, 'url': 'https://github.com/' + self.newName}
        client = GitHubClient(transport=lambda *args: HttpResponse(200, {}, {'data': data}), now=lambda: self.asOf)
        return client.fetchObservations(refs, Budget())

    def doublePrevious(self, reverse=False):
        old = self.previous()
        old['projects'].append({'full_name': self.newName, 'node_id': self.nodeId,
                                'history_key': self.newName, 'created_at': self.createdAt,
                                'stargazers_count': 12})
        old['history'][self.newName] = {'2026-10-20': 12}
        if reverse:
            old['projects'].reverse()
        return old

    def test_current_duplicate_records_reconcile_only_with_both_requested_identity_proofs(self):
        for reverseRecords in [False, True]:
            for reverseRequests in [False, True]:
                with self.subTest(records=reverseRecords, requests=reverseRequests):
                    old = self.doublePrevious(reverseRecords)
                    before = copy.deepcopy(old)
                    result = applyObservations(old, self.duplicateBatch(reverseRequests), '2026-10-21')
                    self.assertEqual(len(result['projects']), 1)
                    project = result['projects'][0]
                    self.assertEqual(project['full_name'], self.newName)
                    self.assertEqual(project['history_key'], self.oldName)
                    self.assertEqual(project['node_id'], self.nodeId)
                    self.assertEqual(project['history_aliases'], [self.newName])
                    self.assertEqual(project['observation_status'], 'fresh')
                    self.assertEqual(result['saved_aliases'][self.oldName], self.newName)
                    for key, series in old['history'].items():
                        for date, stars in series.items():
                            self.assertEqual(result['history'][key][date], stars)
                    self.assertEqual(result['history'][self.newName], old['history'][self.newName])
                    self.assertNotIn('2026-10-21', result['history'][self.newName])
                    self.assertEqual(old, before)

    def test_duplicate_records_are_not_coalesced_without_matching_creation_and_target_observation(self):
        for batch in [self.duplicateBatch(createdAt='2026-10-16T20:40:05Z'),
                      self.duplicateBatch(targetAvailable=False)]:
            old = self.doublePrevious()
            result = applyObservations(old, batch, '2026-10-21')
            self.assertEqual(len(result['projects']), 2)
            project = next(p for p in result['projects'] if p['full_name'] == self.oldName)
            self.assertEqual(project['observation_status'], 'identity_conflict')
            self.assertNotIn('history_aliases', project)
            self.assertEqual(result['history'][self.oldName], old['history'][self.oldName])
            self.assertNotIn(self.oldName, result['saved_aliases'])
