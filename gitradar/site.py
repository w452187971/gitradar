"""Render review-qualified content to portable, progressively enhanced static pages."""
from __future__ import annotations

import copy
import hashlib
import html
import json
from pathlib import Path
import re
from string import Template

from gitradar.content import Record, _record, _records, _strings, eligibleForRecommendation, isOfficialUrl
from gitradar.models import BuildManifest

ROOT = Path(__file__).resolve().parent.parent
FORM_LABELS = {'desktop_app': '桌面软件', 'mobile_app': '手机应用', 'web_app': '网页应用',
               'self_hosted': '自行部署', 'cli': '命令行工具', 'library': '开发库',
               'framework': '开发框架', 'skill': 'Skills', 'collection': '资料集合'}
REVIEW_LABELS = {'source_review': '资料已核对', 'automatic_template': '官方资料结构化整理',
                 'official_statement': '官方资料声明', 'tested': '有实际试用记录'}


def _text(value: object) -> str:
    return html.escape(str(value if value is not None else ''), quote=True)


def _template(filename: str, **values: object) -> str:
    return Template((ROOT / 'web' / 'templates' / filename).read_text()).substitute(values)


def _json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2) + '\n'


def _scriptJson(value: object) -> str:
    return _json(value).replace('<', '\\u003c').replace('\u2028', '\\u2028').replace('\u2029', '\\u2029')


def _content(project: Record) -> Record:
    return _record(project.get('content'))


def _date(value: object) -> str:
    return str(value)[:10] if value else '未记录'


def _checked(content: Record) -> str:
    dates = [str(ref['checked_at']) for ref in _records(content.get('evidence_refs')) if ref.get('checked_at')]
    return _date(min(dates)) if dates else _date(content.get('checked_at'))


def _detailPath(project: Record) -> str:
    identity = str(project.get('history_key') or project.get('full_name', ''))
    if not re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+', identity):
        raise ValueError('Invalid repository path: ' + identity)
    return 'projects/' + identity.lower().replace('/', '--') + '.html'


def _official(url: object, content: Record) -> str:
    if isinstance(url, str) and not any(ord(character) < 33 for character in url):
        if isOfficialUrl(url, str(content.get('full_name', '')), content.get('official_urls')):
            return _text(url)
    return ''


def _link(url: object, label: object, content: Record) -> str:
    safe = _official(url, content)
    return f'<a href="{safe}" target="_blank" rel="noopener noreferrer">{_text(label)} ↗</a>' if safe else _text(label)


def _reviewLabel(content: Record) -> str:
    # A reviewer type alone cannot stand in for a concrete device/version/task/result record.
    return REVIEW_LABELS.get(str(content.get('review_kind')), '官方资料声明') if content.get('review_kind') != 'tested' else '资料已核对'


def _tags(content: Record) -> str:
    tags = _strings(content.get('scenes'))
    form = FORM_LABELS.get(str(content.get('form')), '形态未知')
    return ''.join(f'<span class="tag">{_text(tag)}</span>' for tag in tags) + f'<span class="tag form-tag">{form}</span>'


def _identityStyle(project: Record) -> tuple[str, str]:
    name = str(project.get('display_name') or project.get('full_name', '').split('/')[-1])
    initials = ''.join(word[0].upper() for word in re.findall(r'[A-Za-z0-9]+', name)[:2]) or '◎'
    return initials[:2], str(int(hashlib.sha256(name.encode()).hexdigest()[:4], 16) % 5)


def _card(project: Record, initial: bool = True) -> str:
    content = _content(project)
    path = _records(content.get('usage_paths'))[0]
    initials, hue = _identityStyle(project)
    prerequisites = _strings(content.get('prerequisites')) or ['官方未列出额外前提；请先核对官方说明。']
    search = ' '.join([str(project.get('full_name', '')), str(content.get('purpose', '')),
                       str(content.get('audience', ''))] + _strings(content.get('search_aliases')))
    return _template('card.html', name=_text(project.get('full_name')), scenes=_text('|'.join(_strings(content.get('scenes')))),
                     platforms=_text('|'.join(_strings(content.get('platforms')))), form=_text(content.get('form')),
                     search=_text(search), initial=str(initial).lower(), initials=_text(initials), hue=hue,
                     displayName=_text(project.get('display_name') or str(project.get('full_name', '')).split('/')[-1]),
                     detail=_detailPath(project), tags=_tags(content), purpose=_text(content.get('purpose')),
                     audience=_text(content.get('audience')), devices=_text(' / '.join(_strings(content.get('platforms'))) or '设备未知'),
                     prerequisites=''.join('<span class="condition-line">' + _text(item) + '</span>' for item in prerequisites), reason=_text(project.get('recommendation_reason') or content.get('recommendation_reason')),
                     reviewLabel=_reviewLabel(content), checked=_checked(content), official=_official(path.get('url'), content),
                     pathLabel=_text(path.get('label') or '官方使用说明'))


def _options(values: list[str]) -> str:
    return ''.join(f'<option value="{_text(value)}">{_text(value)}</option>' for value in values)


def _filters(projects: list[Record]) -> str:
    scenes = sorted({scene for project in projects for scene in _strings(_content(project).get('scenes'))})
    devices = sorted({device for project in projects for device in _strings(_content(project).get('platforms'))})
    return ('<div class="filter-panel"><div class="search-wrap"><span aria-hidden="true">⌕</span>'
            '<label class="visually-hidden" for="purpose-search">搜索项目、具体用途或适合人群</label>'
            '<input id="purpose-search" type="search" placeholder="你想做什么？试试「文件」「笔记」" autocomplete="off"></div>'
            '<div class="filter-row"><label>使用场景 <select id="scene-filter"><option value="">全部场景</option>'
            + _options(scenes) + '</select></label><label>目标设备 <select id="device-filter"><option value="">全部设备</option>'
            + _options(devices) + '<option value="unknown">设备未知</option></select></label>'
            '<label>使用方式 <select id="form-filter"><option value="">全部方式</option>'
            + ''.join(f'<option value="{key}">{value}</option>' for key, value in FORM_LABELS.items())
            + '</select></label><button type="button" class="saved-filter" id="saved-filter" aria-pressed="false" hidden>☆ 只看收藏</button>'
            '<button type="button" class="reset-filter" id="reset-filters" hidden>清除条件</button></div></div>'
            '<noscript><p class="subtle">当前为静态目录，全部内容可直接阅读；启用 JavaScript 可使用搜索、筛选与本地收藏。</p></noscript>'
            '<p id="interaction-status" class="interaction-status" role="status"></p>')


def _discoveryCounts(feed: Record) -> str:
    counts = _record(feed.get('discovery_counts'))
    if not counts:
        return '<p>本批推荐来源尚未分类，不能视为自动新发现。</p>'
    labels = {'automatic_new': '自动新发现', 'seed': '首批审核种子', 'baseline_backfill': '旧池补齐',
              'manual_addition': '人工补充', 'rotation': '轮换'}
    parts = []
    for key, label in labels.items():
        value = counts.get(key)
        count = str(value) if isinstance(value, int) and not isinstance(value, bool) and value >= 0 else '未记录'
        parts.append(label + ' ' + count)
    return '<p>本批推荐来源：' + ' · '.join(parts) + '。审核种子与旧项目轮换不计为自动新发现。</p>'


def _transparency(snapshot: Record, count: int) -> str:
    feed = _record(snapshot.get('recommendations'))
    warnings = _strings(snapshot.get('warnings')) + _strings(feed.get('shortfall_reasons'))
    warning = ('<div class="data-notice" role="status">' + '；'.join(_text(item) for item in warnings) + '</div>') if warnings else ''
    stats = _json(snapshot.get('collection_stats', {}))
    return (warning + '<details class="transparency"><summary>这些推荐怎么选？查看数据与资料边界</summary>'
            f'<p>当前批次 {_text(snapshot.get("batch_id") or "旧版数据")} · {_text(_date(snapshot.get("generated_at")))} · {count} 项推荐。</p>'
            '<p>先满足中文用途、适合人群、设备、前置条件、官方路径和许可证的资料门槛，再按场景、新颖性和真实增长证据组合。'
            '首页最多 20 项，首 6 项优先普通用户软件；资料不足时展示实际数量。</p>'
            '<p>资料已核对与实际试用分别记录。开源许可证不代表全部服务免费；费用和依赖请看详情。'
            '本站有限候选池不等于 GitHub 全站覆盖，未观测到增长不等于增长为零。</p>'
            + _discoveryCounts(feed) + f'<pre>{_text(stats)}</pre><p id="batch-status" role="status">当前显示本批已生成的静态内容。</p></details>')


def _layout(body: str, page: str, snapshot: Record, base: str = '', detailName: str = '') -> str:
    title = {'home': '发现实用开源', 'scenes': '按生活场景找工具', 'detail': '项目使用指南'}[page]
    if detailName:
        title = _text(detailName) + ' 使用指南'
    state = {'batch_id': snapshot.get('batch_id'), 'schema_version': snapshot.get('schema_version'),
             'saved_aliases': snapshot.get('saved_aliases', {})}
    return _template('layout.html', body=body, title=title, page=page, base=base,
                     homeCurrent='aria-current="page"' if page == 'home' else '',
                     scenesCurrent='aria-current="page"' if page == 'scenes' else '', state=_scriptJson(state))


def _home(projects: list[Record], snapshot: Record) -> str:
    cards = ''.join(_card(project, index < 6) for index, project in enumerate(projects))
    if not cards:
        cards = '<p class="empty-state">暂无符合当前资料门槛的推荐。<a href="explore.html">去完整候选继续发现 →</a></p>'
    body = _template('home.html', count=len(projects), cards=cards, filters=_filters(projects),
                     date=_text(_date(snapshot.get('generated_at'))), transparency=_transparency(snapshot, len(projects)))
    return _layout(body, 'home', snapshot)


def _sceneId(scene: str) -> str:
    return 'scene-' + hashlib.sha256(scene.encode()).hexdigest()[:12]


def _scenes(projects: list[Record], snapshot: Record, recommendationCount: int) -> str:
    scenes = sorted({scene for project in projects for scene in _strings(_content(project).get('scenes'))})
    directory, groups = [], []
    for scene in scenes:
        members = [project for project in projects if scene in _strings(_content(project).get('scenes'))]
        anchor = _sceneId(scene)
        directory.append(f'<a class="scene-chip" href="#{anchor}">{_text(scene)} <span>{len(members)}</span></a>')
        groups.append(f'<section class="scene-group" id="{anchor}"><div class="section-heading"><h2>{_text(scene)}</h2>'
                      f'<span class="subtle">{len(members)} 个选择</span></div><div class="project-grid">'
                      + ''.join(_card(project) for project in members) + '</div></section>')
    body = _template('scenes.html', count=len(projects), directory=''.join(directory), groups=''.join(groups) or
                     '<p class="empty-state">暂无符合当前资料门槛的推荐。<a href="explore.html">探索完整候选 →</a></p>',
                     filters=_filters(projects), transparency=_transparency(snapshot, recommendationCount))
    return _layout(body, 'scenes', snapshot)


def _retirement(previous: Record, current: Record) -> str:
    content = _content(current)
    reasons = _strings(content.get('invalidation_reasons'))
    reason = '官方资料或使用入口已失效，等待重新核对。' if content.get('effective_status') == 'blocked' else (
        '资料需要重新核对，暂不推荐。' if reasons or content.get('effective_status') == 'review_required' else
        '本期轮换展示其他合格项目，不代表项目不可使用。')
    return ('<aside class="retirement-notice"><strong>已退出本期推荐</strong><p>' + reason
            + f' 以下内容保留原资料日期 {_text(_checked(_content(previous)))}，请核对最新官方说明。</p></aside>')


def _paths(content: Record, disabled: bool) -> str:
    if disabled:
        return '<p class="disabled-path" role="status">入口已停用：已确认失效或需要重新核对，请等待资料复核。</p>'
    return ''.join('<p class="detail-path">' + _link(path.get('url'), path.get('label') or '官方使用说明', content) + '</p>'
                   for path in _records(content.get('usage_paths')))


def _evidence(content: Record, disablePaths: bool = False) -> str:
    items = []
    paths = {str(path.get('url')) for path in _records(content.get('usage_paths'))} if disablePaths else set()
    for ref in _records(content.get('evidence_refs')):
        label = ref.get('section') or ref.get('source_kind') or '官方来源'
        source = _text(label) + '（入口已停用）' if str(ref.get('url')) in paths else _link(ref.get('url'), label, content)
        items.append('<li>' + source
                     + f'<span>核对日期 {_text(_date(ref.get("checked_at")))} · 资料版本 {_text(ref.get("source_version") or ref.get("content_hash") or "未记录")}</span></li>')
    return ''.join(items) or '<li>暂无可展示的官方证据。</li>'


def _disabled(current: Record) -> bool:
    content = _content(current)
    observation = _record(current.get('observation'))
    return (current.get('identity_conflict') is True or content.get('identity_conflict') is True
            or observation.get('identity_conflict') is True or observation.get('status') in ('not_found', 'blocked')
            or current.get('status') in ('not_found', 'blocked') or current.get('http_status') in (404, 410)
            or current.get('observation_status') in ('not_found', 'blocked', 'identity_conflict') or content.get('effective_status') in ('blocked', 'review_required') or any(
        ref.get('status') in (404, 410, 'deleted', 'not_found') or ref.get('path_status') in (404, 410, 'deleted', 'not_found')
        for ref in _records(content.get('evidence_refs'))))


def _detail(project: Record, snapshot: Record, retired: bool = False, current: Record | None = None) -> str:
    content = _content(project)
    initials, hue = _identityStyle(project)
    conditions = _strings(content.get('prerequisites')) or ['官方未列出额外前提；请先核对官方说明。']
    limits = _strings(content.get('limitations')) or ['未记录其他限制；这不代表没有限制，请以最新官方说明为准。']
    body = _template('detail.html', retirement=_retirement(project, current or {}) if retired else '',
        hue=hue, initials=initials, formLabel=FORM_LABELS.get(str(content.get('form')), '形态未知'), reviewLabel=_reviewLabel(content),
        displayName=_text(project.get('display_name') or str(project.get('full_name', '')).split('/')[-1]),
        name=_text(project.get('full_name')), purpose=_text(content.get('purpose')), tags=_tags(content),
        audience=_text(content.get('audience')), devices=_text(' / '.join(_strings(content.get('platforms'))) or '设备未知'),
        prerequisites=''.join('<li>' + _text(item) + '</li>' for item in conditions),
        limitations=''.join('<li>' + _text(item) + '</li>' for item in limits),
        paths=_paths(content, retired and _disabled(current or {})), license=_text(content.get('license') or '许可未知'),
        cost=_text(content.get('cost') or '官方未说明费用；不代表免费'), checked=_checked(content),
        reason=_text(project.get('recommendation_reason') or content.get('recommendation_reason')),
        firstRecommended=_text(_date(project.get('first_recommended_at'))),
        reviewBoundary='此页依据官方资料整理，未实际试用。用途、设备与获取路径分别核对；不构成安全背书。', evidence=_evidence(content, retired and _disabled(current or {})))
    return _layout(body, 'detail', snapshot, '../', str(project.get('full_name', '')))


def _qualified(snapshot: Record) -> tuple[list[Record], list[Record]]:
    feed = _record(snapshot.get('recommendations'))
    if feed.get('batch_id') and feed.get('batch_id') != snapshot.get('batch_id'):
        raise ValueError('Recommendation batch 与快照批次不一致')
    if snapshot.get('schema_version') != '4.0':
        return [], []
    asOf = str(snapshot.get('generated_at') or '')
    def eligible(project: Record) -> bool:
        observation = {**project, **_record(project.get('observation'))}
        return bool(eligibleForRecommendation(_content(project), observation, asOf)['eligible'])
    selected = [project for project in _records(feed.get('recommendations')) if eligible(project)][:20]
    directory = [project for project in _records(snapshot.get('projects')) if eligible(project)]
    for project in selected + directory:
        _detailPath(project)
    return selected, directory


def _previousDetails(snapshot: Record, output: Path) -> dict[str, Record]:
    provided = snapshot.get('previous_details')
    if isinstance(provided, dict):
        return {str(key): _record(value) for key, value in provided.items()}
    path = output / 'data' / 'detail-index.json'
    if not path.exists():
        return {}
    try:
        return {str(key): _record(value) for key, value in _record(json.loads(path.read_text())).items()}
    except (ValueError, OSError) as error:
        raise ValueError('无法安全保留旧详情索引: ' + str(error)) from error


def _detailFiles(selected: list[Record], directory: list[Record], snapshot: Record, output: Path) -> dict[str, str]:
    previous = _previousDetails(snapshot, output)
    current = {_detailPath(project): project for project in _records(snapshot.get('projects'))}
    active = {_detailPath(project): project for project in directory + selected}
    selectedPaths = {_detailPath(project) for project in selected}
    # Every reviewed directory item has a shareable address; retirement applies to former feed selections.
    files = {path: _detail(project, snapshot) for path, project in active.items()}
    index = {path: {'project': project, 'was_recommended': path in selectedPaths} for path, project in active.items()}
    for path, record in previous.items():
        if not re.fullmatch(r'projects/[a-z0-9_.-]+--[a-z0-9_.-]+\.html', path):
            raise ValueError('Invalid previous detail path: ' + path)
        oldProject = _record(record.get('project')) or record
        wasRecommended = record.get('was_recommended') is not False
        if path not in selectedPaths and (wasRecommended or path not in active):
            retirementCurrent = current.get(path) or _record(record.get('retirement_current'))
            files[path] = _detail(oldProject, snapshot, True, retirementCurrent)
            index[path] = {'project': oldProject, 'was_recommended': wasRecommended, 'retired': True,
                           'retirement_current': retirementCurrent}
    files['data/detail-index.json'] = _json(index)
    return files


def buildSite(snapshot: Record, outputDirectory: str | Path) -> BuildManifest:
    """Write only presentation artifacts; the caller validates and publishes its isolated batch."""
    selected, directory = _qualified(snapshot)
    output = Path(outputDirectory)
    state = {'batch_id': snapshot.get('batch_id'), 'schema_version': snapshot.get('schema_version'),
             'saved_aliases': snapshot.get('saved_aliases', {})}
    files = {'index.html': _home(selected, snapshot), 'scenes.html': _scenes(directory, snapshot, len(selected)),
             'explore.html': (ROOT / 'web' / 'templates' / 'explore.html').read_text(), 'data/site-state.json': _json(state)}
    files.update(_detailFiles(selected, directory, snapshot, output))
    files.update({'assets/' + path.name: path.read_text() for path in (ROOT / 'web' / 'assets').glob('*') if path.is_file()})
    artifacts: dict[str, str] = {}
    for name, content in files.items():
        target = output / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content)
        artifacts[name] = hashlib.sha256(target.read_bytes()).hexdigest()
    for target in (output / 'projects').glob('*.html'):
        artifacts[target.relative_to(output).as_posix()] = hashlib.sha256(target.read_bytes()).hexdigest()
    return {'schema_version': str(snapshot.get('schema_version') or '4.0'), 'batch_id': str(snapshot.get('batch_id') or ''),
            'generated_at': str(snapshot.get('generated_at') or ''), 'source_commit': str(snapshot.get('source_commit') or ''),
            'artifacts': artifacts}
