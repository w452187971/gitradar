/* Progressive enhancement: the reviewed HTML remains the source of displayed facts. */
(function (root) {
  'use strict';

  function canonicalName(name, aliases = {}) {
    const visited = new Set();
    let current = name;
    while (typeof aliases[current] === 'string' && !visited.has(current)) {
      visited.add(current);
      current = aliases[current];
    }
    return visited.has(current) ? [...visited].sort()[0] : current;
  }

  function isSaved(name, saved = [], aliases = {}) {
    const canonical = canonicalName(name, aliases);
    return [...saved].some(value => canonicalName(value, aliases) === canonical);
  }

  function toggleSaved(name, saved = [], aliases = {}) {
    if (isSaved(name, saved, aliases)) {
      const canonical = canonicalName(name, aliases);
      return [...saved].filter(value => canonicalName(value, aliases) !== canonical);
    }
    return [...saved, name];
  }

  function matchesFilters(project, filters = {}, saved = [], aliases = {}) {
    const scenes = project.scenes || [];
    const platforms = project.platforms || [];
    const query = (filters.query || '').trim().toLocaleLowerCase();
    const searchable = [project.name, project.search, ...scenes, ...platforms].join(' ').toLocaleLowerCase();
    return (!query || searchable.includes(query)) &&
      (!filters.scene || scenes.includes(filters.scene)) &&
      (!filters.platform || (filters.platform === 'unknown' ? !platforms.length : platforms.includes(filters.platform))) &&
      (!filters.form || filters.form === project.form) &&
      (!filters.savedOnly || isSaved(project.name, saved, aliases));
  }

  async function checkBatch(fetcher, state, status, base) {
    try {
      const response = await fetcher(base + 'data/site-state.json', {cache: 'no-cache'});
      if (!response.ok) throw Error('HTTP ' + response.status);
      const data = await response.json();
      if (data.batch_id && state.batch_id && data.batch_id !== state.batch_id) {
        status.textContent = '页面与发布状态批次不一致，继续显示本批静态内容；请稍后重新载入。';
      } else if (!data.batch_id || !state.batch_id || data.schema_version !== '4.0') {
        status.textContent = '发布状态未提供可确认的 V4 批次；继续显示本批静态内容。';
      } else {
        status.textContent = '静态页面与发布状态批次一致。';
      }
    } catch (error) {
      status.textContent = '暂时无法核对发布状态，当前静态内容仍可阅读（' + error.message + '）。';
    }
  }

  function projectFromCard(card) {
    return {name: card.dataset.project, search: card.dataset.search,
      scenes: (card.dataset.scenes || '').split('|').filter(Boolean),
      platforms: (card.dataset.platforms || '').split('|').filter(Boolean), form: card.dataset.form};
  }

  function readSaved(storage, status) {
    try {
      const saved = JSON.parse(storage.getItem('radar_saved') || '[]');
      if (!Array.isArray(saved) || saved.some(name => typeof name !== 'string')) {
        throw Error('收藏数据格式无效');
      }
      return saved;
    } catch (error) {
      if (status) status.textContent = '本地收藏读取失败（' + error.message + '）；其他内容仍可浏览。';
      return [];
    }
  }

  function init(document, storage) {
    const stateElement = document.getElementById('site-state');
    if (!stateElement) return;
    const status = document.getElementById('interaction-status');
    let state;
    try {
      state = JSON.parse(stateElement.textContent);
    } catch (error) {
      if (status) status.textContent = '页面交互信息读取失败，静态目录仍可使用。';
      return;
    }
    let saved = readSaved(storage, status);
    const aliases = state.saved_aliases || {};
    const cards = [...document.querySelectorAll('[data-project]')];
    const controls = filterControls(document);
    const ui = {savedOnly: false, expanded: document.body.dataset.page !== 'home'};
    const update = () => updateResults(document, cards, controls, ui, saved, aliases);
    bindSaving(document, storage, () => saved, next => { saved = next; }, aliases, status, update);
    bindFilters(document, controls, ui, update);
    update();
    const batchStatus = document.getElementById('batch-status');
    if (batchStatus && typeof root.fetch === 'function') {
      checkBatch(root.fetch.bind(root), state, batchStatus, document.body.dataset.base || './');
    }
  }

  function filterControls(document) {
    return {query: document.getElementById('purpose-search'), scene: document.getElementById('scene-filter'),
      platform: document.getElementById('device-filter'), form: document.getElementById('form-filter')};
  }

  function valuesFromControls(controls, ui) {
    return {query: controls.query?.value || '', scene: controls.scene?.value || '',
      platform: controls.platform?.value || '', form: controls.form?.value || '', savedOnly: ui.savedOnly};
  }

  function updateSaveButtons(document, saved, aliases) {
    document.querySelectorAll('[data-save]').forEach(button => {
      const active = isSaved(button.dataset.save, saved, aliases);
      const detail = !button.classList.contains('save-button');
      button.textContent = active ? (detail ? '★ 已收藏' : '★') : (detail ? '☆ 收藏这个项目' : '☆');
      button.setAttribute('aria-pressed', String(active));
      button.setAttribute('aria-label', (active ? '取消收藏 ' : '收藏 ') + button.dataset.save);
      button.hidden = false;
    });
  }

  function updateResults(document, cards, controls, ui, saved, aliases) {
    const filters = valuesFromControls(controls, ui);
    const filtering = Object.values(filters).some(Boolean);
    const matches = cards.filter(card => matchesFilters(projectFromCard(card), filters, saved, aliases));
    const visible = ui.expanded || filtering ? matches : matches.slice(0, 6);
    cards.forEach(card => { card.hidden = !visible.includes(card); });
    const count = document.getElementById('result-count');
    const total = new Set(matches.map(card => card.dataset.project)).size;
    if (count) count.textContent = '显示 ' + new Set(visible.map(card => card.dataset.project)).size + ' 项 · 符合条件 ' + total + ' 项';
    const empty = document.getElementById('filter-empty');
    if (empty) empty.hidden = matches.length > 0 || cards.length === 0;
    const more = document.getElementById('show-more');
    if (more) more.hidden = ui.expanded || filtering || matches.length <= 6;
    const clear = document.getElementById('reset-filters');
    if (clear) clear.hidden = !filtering;
    document.querySelectorAll('.scene-group').forEach(group => {
      group.hidden = ![...group.querySelectorAll('[data-project]')].some(card => !card.hidden);
    });
    updateSaveButtons(document, saved, aliases);
  }

  function bindSaving(document, storage, getSaved, setSaved, aliases, status, update) {
    document.querySelectorAll('[data-save]').forEach(button => {
      button.addEventListener('click', () => {
        const next = toggleSaved(button.dataset.save, getSaved(), aliases);
        try {
          storage.setItem('radar_saved', JSON.stringify(next));
          setSaved(next);
          if (status) status.textContent = '收藏已保存在当前浏览器。完整候选页可查看原有全部收藏。';
          update();
        } catch (error) {
          if (status) status.textContent = '收藏保存失败（' + error.message + '）；原有收藏已保留。';
        }
      });
    });
  }

  function bindFilters(document, controls, ui, update) {
    Object.values(controls).filter(Boolean).forEach(control => {
      control.addEventListener(control === controls.query ? 'input' : 'change', update);
    });
    const savedFilter = document.getElementById('saved-filter');
    if (savedFilter) {
      savedFilter.hidden = false;
      savedFilter.addEventListener('click', () => {
        ui.savedOnly = !ui.savedOnly;
        savedFilter.setAttribute('aria-pressed', String(ui.savedOnly));
        update();
      });
    }
    document.getElementById('show-more')?.addEventListener('click', () => { ui.expanded = true; update(); });
    document.getElementById('reset-filters')?.addEventListener('click', () => {
      Object.values(controls).filter(Boolean).forEach(control => { control.value = ''; });
      ui.savedOnly = false;
      savedFilter?.setAttribute('aria-pressed', 'false');
      update();
      controls.query?.focus();
    });
  }

  const api = {canonicalName, isSaved, toggleSaved, matchesFilters, checkBatch, init};
  if (typeof module === 'object' && module.exports) module.exports = api;
  if (typeof document !== 'undefined') {
    const storage = {getItem: key => root.localStorage.getItem(key),
      setItem: (key, value) => root.localStorage.setItem(key, value)};
    init(document, storage);
  }
})(typeof globalThis !== 'undefined' ? globalThis : this);
