const assert = require('node:assert/strict');
const test = require('node:test');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const file = path.join(__dirname, '..', 'web/assets/site.js');
const api = fs.existsSync(file) ? require(file) : {};
const project = {name: 'new/tool', search: 'LocalSend 局域网传输文件', scenes: ['文件传输', '隐私保护'],
  platforms: ['Windows', 'Android'], form: 'desktop_app'};
const aliases = {'old/tool': 'new/tool', 'older/tool': 'old/tool'};

test('multiple scene labels and explicit target device both constrain search', () => {
  assert.equal(typeof api.matchesFilters, 'function');
  assert.equal(api.matchesFilters(project, {query: '局域网', scene: '隐私保护', platform: 'Android'}), true);
  assert.equal(api.matchesFilters(project, {scene: '隐私保护', platform: 'iOS'}), false);
  assert.equal(api.matchesFilters({...project, platforms: []}, {platform: 'Android'}), false);
  assert.equal(api.matchesFilters({...project, platforms: []}, {platform: 'unknown'}), true);
  assert.equal(api.matchesFilters(project, {query: 'localSEND'}), true);
});

test('saved migration recognizes alias chains and retains unrelated historic favorites', () => {
  assert.equal(typeof api.toggleSaved, 'function');
  const saved = ['older/tool', 'retired/old'];
  assert.equal(api.isSaved('new/tool', saved, aliases), true);
  assert.deepEqual(api.toggleSaved('new/tool', saved, aliases), ['retired/old']);
  assert.deepEqual(api.toggleSaved('new/tool', ['retired/old'], aliases), ['retired/old', 'new/tool']);
  assert.deepEqual(saved, ['older/tool', 'retired/old']);
});

test('alias cycles cannot hang favorites', () => {
  assert.equal(typeof api.canonicalName, 'function');
  assert.equal(typeof api.canonicalName('old/tool', {'old/tool': 'new/tool', 'new/tool': 'old/tool'}), 'string');
});

test('filtering saved projects accepts original names after a rename', () => {
  assert.equal(typeof api.matchesFilters, 'function');
  assert.equal(api.matchesFilters(project, {savedOnly: true}, ['old/tool'], aliases), true);
  assert.equal(api.matchesFilters(project, {savedOnly: true}, ['another/tool'], aliases), false);
});

test('mismatched batch never overwrites static project cards or saved aliases', async () => {
  assert.equal(typeof api.checkBatch, 'function');
  let message = '';
  const status = {set textContent(value) { message = value; }};
  const data = {batch_id: 'new', projects: [{full_name: 'unsafe/replacement'}]};
  const state = {batch_id: 'old', saved_aliases: {'old/tool': 'new/tool'}};
  const before = JSON.stringify(state);
  await api.checkBatch(async () => ({ok: true, json: async () => data}), state, status, './');
  assert.match(message, /批次.*不同|批次.*不一致/);
  assert.equal(JSON.stringify(state), before);
});

test('offline or legacy dynamic data leaves readable static content', async () => {
  assert.equal(typeof api.checkBatch, 'function');
  for (const payload of [{}, {schema_version: '3.3'}]) {
    const status = {textContent: ''};
    await api.checkBatch(async () => ({ok: true, json: async () => payload}), {batch_id: 'current'}, status, '../');
    assert.match(status.textContent, /静态|批次/);
  }
  const status = {textContent: ''};
  await api.checkBatch(async () => { throw Error('offline'); }, {batch_id: 'current'}, status, './');
  assert.match(status.textContent, /静态/);
});

function browserFixture({denyRead = false, denyWrite = false, initialSaved = []} = {}) {
  const element = (dataset = {}, className = '') => ({dataset, hidden: false, value: '', textContent: '',
    listeners: {}, attributes: {}, classList: {contains: name => name === className},
    addEventListener(name, action) { this.listeners[name] = action; },
    setAttribute(name, value) { this.attributes[name] = value; }, focus() { this.focused = true; }});
  const cards = Array.from({length: 8}, (_, index) => element({project: 'demo/tool' + index,
    scenes: '文件传输|隐私保护', platforms: 'Windows|Android', search: '文件传输工具', form: 'desktop_app'}));
  const saves = cards.map(card => element({save: card.dataset.project}, 'save-button'));
  const ids = Object.fromEntries(['interaction-status', 'purpose-search', 'scene-filter', 'device-filter',
    'form-filter', 'result-count', 'filter-empty', 'show-more', 'reset-filters', 'saved-filter'].map(id => [id, element()]));
  ids['site-state'] = {textContent: JSON.stringify({batch_id: 'batch', saved_aliases: {'old/tool': 'demo/tool0'}})};
  const document = {body: {dataset: {page: 'home'}}, getElementById: id => ids[id] || null,
    querySelectorAll: selector => selector === '[data-project]' ? cards : selector === '[data-save]' ? saves : []};
  let stored = JSON.stringify(initialSaved);
  const storage = {getItem() { if (denyRead) throw Error('blocked'); return stored; },
    setItem(key, value) { assert.equal(key, 'radar_saved'); if (denyWrite) throw Error('quota'); stored = value; }};
  return {document, storage, ids, cards, saves, saved: () => JSON.parse(stored)};
}

test('actual homepage enhancement shows six first and expands in the same original order', () => {
  const fixture = browserFixture();
  api.init(fixture.document, fixture.storage);
  assert.equal(fixture.cards.filter(card => !card.hidden).length, 6);
  assert.equal(fixture.ids['show-more'].hidden, false);
  fixture.ids['show-more'].listeners.click();
  assert.equal(fixture.cards.filter(card => !card.hidden).length, 8);
  fixture.ids['device-filter'].value = 'iOS';
  fixture.ids['device-filter'].listeners.change();
  assert.equal(fixture.cards.filter(card => !card.hidden).length, 0);
  assert.equal(fixture.ids['filter-empty'].hidden, false);
  fixture.ids['reset-filters'].listeners.click();
  assert.equal(fixture.cards.filter(card => !card.hidden).length, 8);
  assert.equal(fixture.ids['purpose-search'].focused, true);
});

test('saving in the real event handler preserves unrelated old favorites and rolls back quota errors', () => {
  const fixture = browserFixture({initialSaved: ['old/tool', 'retired/keep']});
  api.init(fixture.document, fixture.storage);
  assert.equal(fixture.saves[0].attributes['aria-pressed'], 'true');
  fixture.saves[1].listeners.click();
  assert.deepEqual(fixture.saved(), ['old/tool', 'retired/keep', 'demo/tool1']);
  fixture.ids['saved-filter'].listeners.click();
  assert.equal(fixture.cards.filter(card => !card.hidden).length, 2);
  const denied = browserFixture({denyWrite: true, initialSaved: ['retired/keep']});
  api.init(denied.document, denied.storage);
  denied.saves[0].listeners.click();
  assert.deepEqual(denied.saved(), ['retired/keep']);
  assert.equal(denied.saves[0].attributes['aria-pressed'], 'false');
  assert.match(denied.ids['interaction-status'].textContent, /失败.*原有收藏已保留/);
});

test('denied local storage never blocks static cards or filters', () => {
  const fixture = browserFixture({denyRead: true});
  api.init(fixture.document, fixture.storage);
  assert.equal(fixture.cards.filter(card => !card.hidden).length, 6);
  assert.match(fixture.ids['interaction-status'].textContent, /读取失败/);
});
