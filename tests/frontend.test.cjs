const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');

const html = fs.readFileSync(path.join(__dirname, '..', 'index.html'), 'utf8');
const source = html.match(/<script>([\s\S]*?)<\/script>/)[1];
const voidTags = new Set(['meta', 'input', 'br', 'link']);

class Element {
  constructor(tagName, attributes = {}) {
    this.tagName = tagName;
    this.attributes = attributes;
    this.children = [];
    this.dataset = Object.fromEntries(Object.entries(attributes)
      .filter(([name]) => name.startsWith('data-')).map(([name, value]) => [name.slice(5), value]));
    this.classList = {toggle: (name, active) => {
      const names = new Set(this.className.split(/\s+/).filter(Boolean));
      active ? names.add(name) : names.delete(name);
      this.className = [...names].join(' ');
    }};
  }
  get className() { return this.attributes.class || ''; }
  set className(value) { this.attributes.class = value; }
  get value() { return this.currentValue ?? this.attributes.value ?? this.querySelector('option')?.value ?? ''; }
  set value(value) { this.currentValue = value; }
  get textContent() { return this.children.map(child => typeof child === 'string' ? child : child.textContent).join(''); }
  set textContent(value) { this.children = [String(value)]; }
  set innerHTML(value) { this.children = parseMarkup(value).children; }
  replaceChildren(...children) { this.children = children; }
  querySelector(selector) { return this.querySelectorAll(selector)[0] || null; }
  querySelectorAll(selector) {
    return this.children.filter(child => child instanceof Element).flatMap(child =>
      [...(matches(child, selector) ? [child] : []), ...child.querySelectorAll(selector)]);
  }
}

function matches(element, selector) {
  if (selector.startsWith('#')) return element.attributes.id === selector.slice(1);
  if (selector.startsWith('.')) return element.className.split(/\s+/).includes(selector.slice(1));
  if (selector.startsWith('[')) {
    const [, name, value] = selector.match(/^\[([^=\]]+)(?:="([^"]*)")?\]$/);
    return name in element.attributes && (value === undefined || element.attributes[name] === value);
  }
  return element.tagName === selector;
}

function parseMarkup(markup) {
  const root = new Element('root');
  const stack = [root];
  for (const token of markup.match(/<[^>]*>|[^<]+/g) || []) {
    if (token.startsWith('</')) { stack.pop(); continue; }
    if (token.startsWith('<!')) continue;
    if (!token.startsWith('<')) { stack.at(-1).children.push(token); continue; }
    const tagName = token.match(/^<([\w-]+)/)[1];
    const attributes = Object.fromEntries([...token.matchAll(/([\w-]+)="([^"]*)"/g)]
      .map(([, name, value]) => [name, value]));
    const node = new Element(tagName, attributes);
    stack.at(-1).children.push(node);
    if (!voidTags.has(tagName)) stack.push(node);
  }
  return root;
}

function project(fullName, overrides = {}) {
  return {full_name: fullName, html_url: `https://github.com/${fullName}`, description: 'A useful tool',
    stargazers_count: 100, delta_1d: null, delta_7d: null, language: 'JavaScript', topics: [],
    created_at: '2020-01-01T00:00:00Z', pushed_at: '2020-01-02T00:00:00Z',
    discovery_score: 10, summary_zh: null, ...overrides};
}

async function loadPage(projects, options = {}) {
  const document = parseMarkup(html.replace(/<script>[\s\S]*?<\/script>/, ''));
  document.getElementById = id => document.querySelector(`#${id}`);
  document.createElement = tagName => new Element(tagName);
  const stored = new Map(Object.entries(options.stored || {}));
  let requestCount = 0;
  const localStorage = {
    getItem(key) { if (options.denyRead) throw Error('storage blocked'); return stored.get(key) ?? null; },
    setItem(key, value) { if (options.denyWrite) throw Error('quota exceeded'); stored.set(key, value); }
  };
  const payload = {generated_at: '2020-01-03T08:00:00Z', projects, warnings: options.warnings || []};
  const fetch = async () => {
    requestCount += 1;
    return {ok: true, json: async () => payload};
  };
  const context = vm.createContext({document, localStorage, fetch, console, Date, Set, JSON, Error});
  vm.runInContext(source, context);
  await new Promise(resolve => setImmediate(resolve));
  return {document, stored, requestCount: () => requestCount,
    get: id => document.getElementById(id),
    tab: name => document.querySelector(`[data-tab="${name}"]`).onclick(),
    cards: () => document.querySelectorAll('.card')};
}

test('negative snapshot changes keep their sign and identify the one-day snapshot', async () => {
  const page = await loadPage([project('sample/decline', {delta_1d: -60, delta_7d: -300})]);
  const text = page.cards()[0].querySelector('.delta').textContent;
  assert.match(text, /1日快照 -60/);
  assert.match(text, /7日快照 -300/);
  assert.doesNotMatch(text, /\+-/);
});

for (const [sort, field] of [['day', 'delta_1d'], ['week', 'delta_7d']]) {
  test(`${sort} sorting puts missing history behind negative, zero and positive changes`, async () => {
    const page = await loadPage([
      project('sample/unknown'), project('sample/negative', {[field]: -60}),
      project('sample/zero', {[field]: 0}), project('sample/positive', {[field]: 5})
    ]);
    page.get('sort').value = sort;
    page.get('sort').onchange();
    assert.deepEqual(page.cards().map(card => card.querySelector('.name').textContent),
      ['sample/positive', 'sample/zero', 'sample/negative', 'sample/unknown']);
  });
}

test('filtering keeps the data collection timestamp rather than the render time', async () => {
  const page = await loadPage([project('sample/one')]);
  assert.match(page.get('summary').textContent, /采集时间 2020/);
  const summary = page.get('summary').textContent;
  page.get('search').value = 'sample';
  page.get('search').oninput();
  assert.equal(page.get('summary').textContent, summary);
});

test('refresh reads the static list again without changing its collection timestamp', async () => {
  const page = await loadPage([project('sample/one')]);
  const summary = page.get('summary').textContent;
  await page.get('refresh').onclick();
  assert.equal(page.requestCount(), 2);
  assert.equal(page.get('refresh').textContent, '↻ 刷新列表');
  assert.equal(page.get('summary').textContent, summary);
  assert.match(page.get('notice').textContent, /静态/);
});

test('collection warnings remain visible when the list loads successfully', async () => {
  const page = await loadPage([project('sample/one')], {warnings: ['refresh sample/stale: HTTP 503']});
  assert.equal(page.cards().length, 1);
  assert.match(page.get('notice').textContent, /sample\/stale.*HTTP 503/);
});

for (const tab of ['day', 'week']) {
  test(`${tab} view explains missing history instead of claiming no matching projects`, async () => {
    const page = await loadPage([project('sample/one')]);
    page.tab(tab);
    assert.equal(page.cards().length, 0);
    assert.match(page.get('cards').textContent, /快照|历史/);
    assert.match(page.get('cards').textContent, /不足|积累/);
  });
}

for (const options of [{stored: {radar_saved: '{broken'}},
  {stored: {radar_saved: '{}'}}, {denyRead: true},
  {stored: {radar_snapshots: '{obsolete'}}]) {
  test(`unavailable or malformed saved state does not block the list: ${JSON.stringify(options)}`, async () => {
    const page = await loadPage([project('sample/one')], options);
    assert.equal(page.cards().length, 1);
    assert.equal(page.requestCount(), 1);
  });
}

test('a failed save reports the failure and leaves the visible favorite unchanged', async () => {
  const page = await loadPage([project('sample/one')], {denyWrite: true});
  page.cards()[0].querySelector('.save').onclick();
  assert.equal(page.cards()[0].querySelector('.save').textContent, '☆ 收藏');
  assert.match(page.get('notice').textContent, /收藏.*失败|无法.*收藏/);
  page.tab('saved');
  assert.equal(page.cards().length, 0);
});

test('a failed unsave preserves the existing favorite and its persisted state', async () => {
  const saved = '["sample/one"]';
  const page = await loadPage([project('sample/one')], {stored: {radar_saved: saved}, denyWrite: true});
  page.cards()[0].querySelector('.save').onclick();
  page.tab('saved');
  assert.equal(page.cards().length, 1);
  assert.equal(page.cards()[0].querySelector('.save').textContent, '★ 已收藏');
  assert.equal(page.stored.get('radar_saved'), saved);
});

test('a successful favorite is persisted and can be removed from the saved view', async () => {
  const page = await loadPage([project('sample/one')]);
  page.cards()[0].querySelector('.save').onclick();
  assert.deepEqual(JSON.parse(page.stored.get('radar_saved')), ['sample/one']);
  page.tab('saved');
  assert.equal(page.cards().length, 1);
  page.cards()[0].querySelector('.save').onclick();
  assert.equal(page.cards().length, 0);
  assert.deepEqual(JSON.parse(page.stored.get('radar_saved')), []);
});
