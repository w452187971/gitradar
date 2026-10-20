const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');

const html = fs.readFileSync(path.join(__dirname, '..', 'explore.html'), 'utf8');
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
  setAttribute(name, value) { this.attributes[name] = String(value); }
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
  const generatedAt = options.generatedAt === undefined ? '2020-01-03T08:00:00Z' : options.generatedAt;
  const rulesVersion = options.rulesVersion === undefined ? 'v3.3' : options.rulesVersion;
  const payload = {generated_at: generatedAt, projects, warnings: options.warnings || [],
    collection_stats: options.collectionStats, rules_version: rulesVersion};
  const fetch = async () => {
    requestCount += 1;
    return {ok: true, json: async () => payload};
  };
  const context = vm.createContext({document, localStorage, fetch, console, Date, Set, JSON, Error, URL});
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
  assert.ok(page.get('notice').className.split(' ').includes('warning'));
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

test('known backend categories control both the card label and the AI view', async () => {
  const categories = [
    ['影音去广告', '📺 影音 / 去广告'], ['影音下载', '🎬 影音下载'],
    ['AI 应用', '🤖 AI 工具'], ['隐私安全', '🔐 隐私安全'],
    ['效率工具', '⚡ 效率工具'], ['系统工具', '💻 系统工具'],
    ['自托管', '🏠 自托管'], ['游戏娱乐', '🎮 游戏娱乐'], ['其他开源', '📦 开源项目']
  ];
  const rows = categories.map(([category], index) => project(`sample/category-${index}`, {
    category_zh: category, description: 'An AI agent with a video player and app launcher'
  }));
  const page = await loadPage(rows);
  assert.deepEqual(page.cards().map(card => card.querySelector('.pill').textContent),
    categories.map(([, label]) => label));
  page.tab('ai');
  assert.deepEqual(page.cards().map(card => card.querySelector('.name').textContent), ['sample/category-2']);
});

for (const category of [undefined, '尚未支持的分类']) {
  test(`fallback does not infer AI from storage or drag when category is ${category}`, async () => {
    const page = await loadPage([
      project('cryptomator/cryptomator', {category_zh: category,
        description: 'Secure client-side encryption for your cloud storage, ensuring privacy.'}),
      project('homarr-labs/homarr', {category_zh: category,
        description: 'A dashboard with drag and drop configuration.'}),
      project('sample/chair-model', {category_zh: category,
        description: 'A model of a handmade chair.'})
    ]);
    assert.ok(page.cards().every(card => !card.querySelector('.pill').textContent.includes('AI')));
    page.tab('ai');
    assert.equal(page.cards().length, 0);
  });
}

test('fallback distinguishes an ordinary app launcher from a television launcher', async () => {
  const page = await loadPage([
    project('storytold/craft-launcher', {description: 'The Craft App Launcher'}),
    project('sample/tv-launcher', {description: 'An Android TV launcher with adblock support'})
  ]);
  assert.deepEqual(page.cards().map(card => card.querySelector('.pill').textContent),
    ['💻 系统工具', '📺 影音 / 去广告']);
});

test('fallback still recognizes explicit AI terms with separators', async () => {
  const page = await loadPage([
    project('sample/assistant', {description: 'Tools for AI-agents and language models.'}),
    project('sample/lookup', {description: 'A private RAG application.'})
  ]);
  page.tab('ai');
  assert.equal(page.cards().length, 2);
});

test('backend evidence summaries keep their complete source prefix and text', async () => {
  const summary = '【用途提取】文件格式转换工具；依据公开简介。';
  const page = await loadPage([project('KnifeLemon/Filee', {summary_zh: summary})]);
  assert.equal(page.cards()[0].querySelector('.desc').textContent, summary);
});

const searchableProjects = [
  project('sample/summary', {summary_zh: '【用途提取】智能电视去广告工具'}),
  project('sample/category', {category_zh: '自定义资料分类'}),
  project('sample/install', {difficulty_zh: '🟡 可能需要命令行安装'}),
  project('sample/platform', {platforms_zh: ['Android TV', 'macOS']})
];

for (const [query, name] of [['智能电视', 'sample/summary'], ['自定义资料', 'sample/category'],
  ['命令行', 'sample/install'], ['ANDROID TV', 'sample/platform']]) {
  test(`search includes published Chinese evidence and platform clues: ${query}`, async () => {
    const page = await loadPage(searchableProjects);
    page.get('search').value = query;
    page.get('search').oninput();
    assert.deepEqual(page.cards().map(card => card.querySelector('.name').textContent), [name]);
  });
}

function manyProjects() {
  return Array.from({length: 125}, (_, index) => project(`sample/project-${index}`, {
    category_zh: 'AI 应用', summary_zh: '【用途提取】笔记助手',
    difficulty_zh: '🟢 可能提供安装包（请核实）', stargazers_count: index + 1
  }));
}

test('load more reveals sixty additional matches per click and hides when exhausted', async () => {
  const page = await loadPage(manyProjects());
  assert.equal(page.cards().length, 60);
  assert.match(page.get('summary').textContent, /匹配 125 个/);
  assert.ok(page.get('loadMore'), 'the remaining matches need a browsing entry point');
  assert.equal(page.get('loadMore').hidden, false);
  page.get('loadMore').onclick();
  assert.equal(page.cards().length, 120);
  assert.equal(page.cards()[60].querySelector('.name').textContent, 'sample/project-60');
  assert.equal(page.get('loadMore').hidden, false);
  page.get('loadMore').onclick();
  assert.equal(page.cards().length, 125);
  assert.equal(page.cards()[124].querySelector('.name').textContent, 'sample/project-124');
  assert.equal(page.get('loadMore').hidden, true);
  assert.equal(page.requestCount(), 1);
});

const conditionChanges = {
  search: page => { page.get('search').value = '笔记'; page.get('search').oninput(); },
  installation: page => { page.get('installFilter').value = 'package'; page.get('installFilter').onchange(); },
  sort: page => { page.get('sort').value = 'stars'; page.get('sort').onchange(); },
  tab: page => page.tab('ai')
};

for (const [condition, change] of Object.entries(conditionChanges)) {
  test(`${condition} changes restart browsing from the first sixty matching projects`, async () => {
    const page = await loadPage(manyProjects());
    assert.ok(page.get('loadMore'), 'pagination must be available before changing conditions');
    page.get('loadMore').onclick();
    assert.equal(page.cards().length, 120);
    change(page);
    assert.equal(page.cards().length, 60);
    assert.match(page.get('summary').textContent, /匹配 125 个/);
    assert.equal(page.get('loadMore').hidden, false);
    if (condition === 'sort') {
      assert.equal(page.cards()[0].querySelector('.name').textContent, 'sample/project-124');
    }
  });
}

const installationProjects = [
  project('sample/package', {difficulty_zh: '🟢 可能提供安装包（请核实）'}),
  project('sample/command', {difficulty_zh: '🟡 可能需要命令行安装'}),
  project('sample/docker', {difficulty_zh: '🟡 可能需要 Docker 配置'}),
  project('sample/unknown', {difficulty_zh: '⚪ 安装方式未确认'}),
  project('sample/legacy')
];

for (const [filter, names] of [['package', ['sample/package']], ['command', ['sample/command']],
  ['docker', ['sample/docker']], ['unknown', ['sample/unknown', 'sample/legacy']]]) {
  test(`installation filter reuses existing evidence: ${filter}`, async () => {
    const page = await loadPage(installationProjects);
    assert.ok(page.get('installFilter'), 'installation evidence needs a filter');
    page.get('installFilter').value = filter;
    page.get('installFilter').onchange();
    assert.deepEqual(page.cards().map(card => card.querySelector('.name').textContent), names);
    assert.equal(page.get('loadMore').hidden, true);
  });
}

test('search, installation and the current category combine without losing any condition', async () => {
  const page = await loadPage([
    project('sample/target', {category_zh: 'AI 应用', platforms_zh: ['Android'],
      difficulty_zh: '🟢 可能提供安装包（请核实）'}),
    project('sample/wrong-category', {category_zh: '系统工具', platforms_zh: ['Android'],
      difficulty_zh: '🟢 可能提供安装包（请核实）'}),
    project('sample/wrong-install', {category_zh: 'AI 应用', platforms_zh: ['Android'],
      difficulty_zh: '🟡 可能需要命令行安装'}),
    project('sample/wrong-platform', {category_zh: 'AI 应用', platforms_zh: ['Windows'],
      difficulty_zh: '🟢 可能提供安装包（请核实）'})
  ]);
  assert.ok(page.get('installFilter'), 'the installation filter must participate in combined queries');
  page.get('search').value = 'android';
  page.get('search').oninput();
  page.get('installFilter').value = 'package';
  page.get('installFilter').onchange();
  page.tab('ai');
  assert.deepEqual(page.cards().map(card => card.querySelector('.name').textContent), ['sample/target']);
  assert.match(page.get('summary').textContent, /匹配 1 个/);
});

test('platform clues come only from the optional published field and support legacy data', async () => {
  const page = await loadPage([
    project('sample/known', {platforms_zh: ['Windows', 'macOS']}),
    project('sample/legacy', {description: 'A Windows and Android utility'}),
    project('sample/empty', {platforms_zh: []})
  ]);
  const clues = page.cards().map(card => card.querySelector('.platforms')?.textContent);
  assert.deepEqual(clues, ['平台线索：Windows / macOS', '平台线索：平台未确认', '平台线索：平台未确认']);
  assert.match(page.get('notice').textContent, /未实际验证/);
});

for (const [tab, field] of [['day', 'delta_1d'], ['week', 'delta_7d']]) {
  test(`${tab} selects its visible default sort and respects an explicit discovery-score sort`, async () => {
    const page = await loadPage([
      project('sample/fast', {[field]: 100, discovery_score: 5}),
      project('sample/negative', {[field]: -1, discovery_score: 10}),
      project('sample/zero', {[field]: 0, discovery_score: 1}), project('sample/unknown')
    ]);
    page.tab(tab);
    assert.equal(page.get('sort').value, tab);
    assert.deepEqual(page.cards().map(card => card.querySelector('.name').textContent),
      ['sample/fast', 'sample/zero', 'sample/negative']);
    assert.match(page.get('viewRule').textContent, /0.*负|零.*负/);
    page.get('sort').value = 'score'; page.get('sort').onchange();
    assert.deepEqual(page.cards().map(card => card.querySelector('.name').textContent),
      ['sample/negative', 'sample/fast', 'sample/zero']);
    assert.match(page.get('viewRule').textContent, /实际排序.*发现分/);
  });
}

test('switching to other views visibly restores discovery-score sorting', async () => {
  const page = await loadPage([project('sample/one', {category_zh: 'AI 应用'})]);
  page.get('sort').value = 'stars'; page.get('sort').onchange();
  page.tab('ai');
  assert.equal(page.get('sort').value, 'score');
  assert.match(page.get('viewRule').textContent, /AI/);
  assert.match(page.get('viewRule').textContent, /实际排序.*发现分/);
  page.tab('tools');
  assert.match(page.get('viewRule').textContent, /规则分类|规则.*识别/);
  assert.match(page.get('viewRule').textContent, /开发者工具/);
});

test('recent projects use a frozen thirty-day window ending at the collection timestamp', async () => {
  const page = await loadPage([
    project('sample/recent', {created_at: '2019-12-15T00:00:00Z'}),
    project('sample/old', {created_at: '2019-11-15T00:00:00Z'}),
    project('sample/future', {created_at: '2021-01-01T00:00:00Z'})
  ]);
  page.tab('new');
  assert.deepEqual(page.cards().map(card => card.querySelector('.name').textContent), ['sample/recent']);
  assert.match(page.get('viewRule').textContent, /采集.*30/);
});

test('an unknown collection timestamp cannot turn the machine clock into a recent-project window', async () => {
  const page = await loadPage([project('sample/recent', {created_at: new Date().toISOString()})],
    {generatedAt: null});
  page.tab('new');
  assert.equal(page.cards().length, 0);
  assert.match(page.get('cards').textContent, /采集时间.*未知|未知.*采集时间/);
});

test('coverage exposes retained, discovery and search limitations without claiming continuous dates', async () => {
  const stats = {observed_since: '2020-01-01', observed_through: '2020-01-03', observed_dates: 2,
    refreshed_count: 2, retained_count: 1, newly_discovered_count: 1, daily_coverage: 1,
    weekly_coverage: 0, readme_checked_count: 2, readme_stale_count: 1,
    search_attempted: 20, search_succeeded: 18, search_limited: 2, search_incomplete: 3};
  const page = await loadPage([project('sample/one'), project('sample/two'), project('sample/three')],
    {collectionStats: stats});
  const text = page.get('coverage')?.textContent;
  assert.ok(text, 'coverage needs a visible data boundary');
  assert.match(text, /最早快照日期.*2020-01-01/);
  assert.match(text, /记录过 2 个 UTC 日期/);
  assert.doesNotMatch(text, /连续\s*2\s*天/);
  assert.match(text, /1日可算 1\/3.*7日可算 0\/3/);
  assert.match(text, /本轮刷新 2.*保留旧值 1.*本轮新增候选 1/);
  assert.match(text, /README.*已检查 2\/3.*待复核 1/);
  assert.match(text, /受限 2.*不完整 3/);
});

test('legacy coverage derives available snapshots and README counts but leaves tracking metadata unknown', async () => {
  const page = await loadPage([
    project('sample/day', {delta_1d: 0, readme_checked: true}),
    project('sample/week', {delta_7d: -3}),
    project('sample/stale', {readme_checked: true, readme_stale: true})
  ]);
  const text = page.get('coverage')?.textContent;
  assert.ok(text, 'legacy datasets still need honest coverage');
  assert.match(text, /1日可算 1\/3.*7日可算 1\/3/);
  assert.match(text, /README.*已检查 2\/3.*待复核 1/);
  assert.match(text, /最早快照日期.*未知/);
  assert.match(text, /本轮刷新 未知.*保留旧值 未知/);
  assert.doesNotMatch(text, /2020-01-01/);
});

test('cold-start discovery clearly separates star-and-age scoring from growth rankings', async () => {
  const page = await loadPage([project('sample/one')]);
  const text = page.get('viewRule')?.textContent;
  assert.ok(text, 'the current view needs an explanation');
  assert.match(text, /仅依据.*Star.*年龄/);
  assert.match(text, /不是增长排名|非增长排名/);
});

test('a measured zero change remains valid evidence rather than a missing growth sample', async () => {
  const page = await loadPage([project('sample/zero', {delta_1d: 0})]);
  assert.ok(page.get('viewRule'));
  assert.doesNotMatch(page.get('viewRule').textContent, /仅依据.*Star.*年龄/);
});

test('recommendation evidence displays the recorded score and actual signed changes', async () => {
  const page = await loadPage([project('sample/declining', {
    discovery_score: -12.5, delta_1d: -60, delta_7d: 10
  })]);
  const text = page.cards()[0].querySelector('.reason')?.textContent;
  assert.ok(text, 'recommendations need inspectable evidence');
  assert.match(text, /发现分 -12.5/);
  assert.match(text, /1日净变化 -60/);
  assert.match(text, /7日净变化 \+10/);
});

test('recommendation evidence with no growth samples uses collection-relative age and recorded stars', async () => {
  const page = await loadPage([project('sample/recent', {created_at: '2019-12-25T23:00:00Z'})]);
  const text = page.cards()[0].querySelector('.reason')?.textContent;
  assert.ok(text);
  assert.match(text, /创建 9 天|年龄 9 天/);
  assert.match(text, /Star 100/);
  assert.doesNotMatch(text, /爆火|增长领先/);
});

test('missing snapshot endpoints distinguish a retained observation from a missing baseline', async () => {
  const page = await loadPage([
    project('sample/retained', {observation_status: 'retained'}), project('sample/no-baseline')
  ]);
  const texts = page.cards().map(card => card.querySelector('.delta').textContent);
  assert.match(texts[0], /1日快照 待积累.*本轮未更新/);
  assert.match(texts[0], /7日快照 待积累/);
  assert.match(texts[1], /1日快照 待积累.*缺1日基准/);
  assert.match(texts[1], /7日快照 待积累.*缺7日基准/);
});

test('README review dates preserve old checked evidence while marking a stale result', async () => {
  const page = await loadPage([
    project('sample/stale', {readme_checked: true, readme_checked_at: '2020-01-01', readme_stale: true}),
    project('sample/unknown-date', {readme_checked: true})
  ]);
  assert.match(page.cards()[0].querySelector('.original').textContent, /已检查 README.*2020-01-01.*待复核/);
  assert.match(page.cards()[1].querySelector('.original').textContent, /检查日期未知/);
});

test('repository creation and code-push dates cannot replace observation metadata', async () => {
  const page = await loadPage([
    project('sample/observed', {first_seen_date: '2020-01-02', last_observed_date: '2020-01-03',
      observation_status: 'fresh'}), project('sample/legacy')
  ]);
  const first = page.cards()[0].querySelector('.observed')?.textContent;
  assert.ok(first);
  assert.match(first, /首次观测.*2020-01-02.*最近观测.*2020-01-03/);
  const legacy = page.cards()[1].querySelector('.observed')?.textContent;
  assert.ok(legacy);
  assert.match(legacy, /未知/);
  assert.doesNotMatch(legacy, /2020-01-01|2020-01-02/);
});

test('missing or invalid code-push dates render as unknown without hiding the project list', async () => {
  const page = await loadPage([
    project('sample/null-date', {pushed_at: null}), project('sample/invalid-date', {pushed_at: 'not-a-date'})
  ]);
  assert.equal(page.cards().length, 2);
  assert.deepEqual(page.cards().map(card => card.querySelector('.foot').querySelector('.small').textContent),
    ['代码更新 未知', '代码更新 未知']);
});

test('retained observations never present old stars and age as a fresh recommendation', async () => {
  const page = await loadPage([project('sample/retained', {observation_status: 'retained',
    discovery_score: 0, created_at: '2020-01-02T00:00:00Z'})]);
  const text = page.cards()[0].querySelector('.reason').textContent;
  assert.match(text, /发现分 0/);
  assert.match(text, /本轮未更新，保留旧值/);
  assert.doesNotMatch(text, /近期创建|Star 100/);
});

test('coverage keeps its full-candidate-pool scope when search narrows the visible list', async () => {
  const page = await loadPage([project('sample/one', {delta_1d: 1}), project('sample/two')]);
  const before = page.get('coverage').textContent;
  assert.match(before, /全候选池/);
  page.get('search').value = 'sample/one'; page.get('search').oninput();
  assert.equal(page.cards().length, 1);
  assert.equal(page.get('coverage').textContent, before);
  assert.match(page.get('coverage').textContent, /1日可算 1\/2/);
});

for (const rulesVersion of [null, 'v3.2']) {
  test(`legacy score batches cannot be presented as the new formula: ${rulesVersion}`, async () => {
    const page = await loadPage([project('sample/legacy-score', {discovery_score: 95})], {rulesVersion});
    assert.match(page.get('notice').textContent, /旧评分规则.*新规则待采集发布后生效/);
    assert.match(page.get('viewRule').textContent, /旧评分规则/);
    assert.doesNotMatch(page.get('viewRule').textContent, /仅依据.*Star.*年龄/);
    assert.match(page.cards()[0].querySelector('.reason').textContent, /旧规则发现分 95/);
  });
}

test('unobserved Star values remain readable candidates instead of zero or a broken list', async () => {
  const page = await loadPage([project('seed/unobserved', {stargazers_count: null, observation_status: 'deferred'}),
    project('seed/observed', {stargazers_count: 123})]);
  assert.equal(page.cards().length, 2);
  const card = page.cards().find(item => item.querySelector('.name').textContent === 'seed/unobserved');
  assert.match(card.querySelector('.stars').textContent, /未观测/);
  assert.doesNotMatch(card.querySelector('.stars').textContent, /\b0\b/);
  assert.doesNotMatch(card.querySelector('.reason').textContent, /Star 0/);
  assert.doesNotMatch(page.get('notice').textContent, /列表加载失败/);
});

test('saved candidates without a Star observation can be viewed and unstarred', async () => {
  const page = await loadPage([project('seed/unobserved', {stargazers_count: null})],
    {stored: {radar_saved: '["seed/unobserved","retired/keep"]'}});
  page.tab('saved');
  assert.equal(page.cards().length, 1);
  assert.match(page.cards()[0].querySelector('.stars').textContent, /未观测/);
  page.cards()[0].querySelector('.save').onclick();
  assert.deepEqual(JSON.parse(page.stored.get('radar_saved')), ['retired/keep']);
  assert.equal(page.cards().length, 0);
});

test('Star sorting places unobserved candidates after observed zero and positive counts', async () => {
  const page = await loadPage([project('seed/null', {stargazers_count: null}),
    project('seed/zero', {stargazers_count: 0}), project('seed/positive', {stargazers_count: 7}),
    project('seed/missing', {stargazers_count: undefined})]);
  page.get('sort').value = 'stars';
  page.get('sort').onchange();
  assert.deepEqual(page.cards().map(card => card.querySelector('.name').textContent),
    ['seed/positive', 'seed/zero', 'seed/null', 'seed/missing']);
  assert.equal(page.cards()[1].querySelector('.stars').textContent, '⭐ 0');
});

test('missing or zero Star baselines never invent relative growth percentages', async () => {
  const page = await loadPage([project('seed/null', {stargazers_count: null, delta_1d: null}),
    project('seed/zero', {stargazers_count: 0, delta_1d: 0})]);
  assert.equal(page.cards().length, 2);
  for (const card of page.cards()) assert.doesNotMatch(card.textContent, /NaN|Infinity|\d+%/);
});

function reviewedVideoContent(overrides = {}) {
  return {full_name: 'sample/video', effective_status: 'published',
    eligibility: {eligible: true, reasons: []}, review_kind: 'source_review',
    purpose: '把已有影片转为 MP4 或 MKV，便于在其他设备播放。',
    audience: '想压缩家庭录像并保留自己的副本的人。', scenes: ['文件转换', '影音处理'],
    platforms: ['Windows', 'macOS'], prerequisites: ['需要自己准备本地视频文件。'],
    usage_paths: [{url: 'https://video.example/download', kind: 'download', label: '官方安装说明'}],
    official_urls: ['https://video.example'], recommendation_reason: '官方提供桌面安装路径',
    evidence_refs: [{id: 'intro', url: 'https://github.com/sample/video/blob/main/README.md',
      section: '核心介绍', checked_at: '2020-01-02T12:00:00Z', status: 200, content_hash: 'fixture-intro-v1'}],
    ...overrides};
}

test('qualified published content replaces contradictory legacy purpose and platform hints', async () => {
  const page = await loadPage([project('sample/video', {summary_zh: '【资料不足】旧版无法识别用途',
    platforms_zh: [], readme_checked: false, content: reviewedVideoContent()})]);
  const card = page.cards()[0];
  assert.match(card.querySelector('.desc').textContent, /把已有影片转为 MP4/);
  assert.match(card.querySelector('.platforms').textContent, /Windows.*macOS/);
  assert.doesNotMatch(card.textContent, /资料不足|平台未确认|安装方式未确认|已检查 README/);
  assert.match(card.querySelector('.content-audience').textContent, /压缩家庭录像/);
  assert.match(card.querySelector('.content-conditions').textContent, /自己准备本地视频/);
  assert.match(card.querySelector('.content-source').textContent, /资料已核对.*2020-01-02/);
  assert.equal(card.querySelector('.official-paths').querySelector('a').attributes.href, 'https://video.example/download');
  assert.equal(card.querySelector('.content-source').querySelector('a').attributes.href,
    'https://github.com/sample/video/blob/main/README.md');
});

test('unpublished ineligible and unknown new records keep legacy behavior instead of inheriting review', async () => {
  for (const content of [reviewedVideoContent({effective_status: 'review_required', invalidation_reasons: ['stale_path:download']}),
    reviewedVideoContent({effective_status: 'unknown'}), reviewedVideoContent({eligibility: {eligible: false}}),
    reviewedVideoContent({eligibility: undefined})]) {
    const page = await loadPage([project('sample/video', {summary_zh: '旧版用途保持可读', content})]);
    const card = page.cards()[0];
    assert.equal(card.querySelector('.desc').textContent, '旧版用途保持可读');
    assert.match(card.querySelector('.platforms').textContent, /平台未确认/);
    assert.doesNotMatch(card.textContent, /资料已核对|官方安装说明/);
    if (content.effective_status === 'review_required') assert.match(card.textContent, /待复核.*stale_path/);
  }
});

test('purpose audience and multiple reviewed scenes can find qualified candidates', async () => {
  const page = await loadPage([project('sample/video', {content: reviewedVideoContent()}), project('sample/other')]);
  for (const query of ['已有影片', '家庭录像', '影音处理']) {
    page.get('search').value = query;
    page.get('search').oninput();
    assert.equal(page.cards().length, 1);
    assert.equal(page.cards()[0].querySelector('.name').textContent, 'sample/video');
  }
});

test('reviewed content remains plain text and unsafe official links are visibly withheld', async () => {
  const content = reviewedVideoContent({purpose: '<img src=x onerror=alert(1)> 用途文本',
    usage_paths: [{url: 'javascript:alert(1)', label: '<script>evil</script>'}]});
  const page = await loadPage([project('sample/video', {content})]);
  const card = page.cards()[0];
  assert.match(card.querySelector('.desc').textContent, /<img src=x/);
  assert.equal(card.querySelectorAll('img').length, 0);
  assert.equal(card.querySelector('.official-paths').querySelectorAll('a').length, 0);
  assert.match(card.querySelector('.official-paths').textContent, /入口.*待复核/);
});

test('reviewed source does not hide retained observations or falsely refresh old Star values', async () => {
  const page = await loadPage([project('sample/video', {content: reviewedVideoContent(),
    observation_status: 'retained', first_seen_date: '2019-12-01', last_observed_date: '2020-01-01'})]);
  const card = page.cards()[0];
  assert.match(card.querySelector('.observed').textContent, /最近观测 2020-01-01.*本轮保留旧值/);
  assert.match(card.querySelector('.reason').textContent, /本轮未更新，保留旧值/);
  assert.match(card.querySelector('.delta').textContent, /本轮未更新/);
  assert.match(card.querySelector('.content-source').textContent, /2020-01-02/);
});

test('unknown review method and failed source checks remain explicit on qualified-looking records', async () => {
  const content = reviewedVideoContent({review_kind: 'unknown', evidence_refs: [{
    url: 'https://github.com/sample/video/blob/main/README.md', section: '安装资料', checked_at: 'bad-date', status: 404}]});
  const page = await loadPage([project('sample/video', {content, observation_status: 'retained'})]);
  const card = page.cards()[0];
  assert.match(card.querySelector('.content-source').textContent, /审核方式未记录/);
  assert.match(card.querySelector('.content-source').textContent, /未知.*来源状态 404/);
  assert.doesNotMatch(card.querySelector('.content-source').textContent, /资料已核对/);
  assert.match(card.querySelector('.observed').textContent, /本轮保留旧值/);
});
