#!/usr/bin/env python3
"""GitRadar V3.1: free discovery with validated, persistent daily snapshots."""
from __future__ import annotations

import base64
import datetime as dt
import json
import os
import pathlib
import re
import tempfile
import time
import urllib.parse
import urllib.request
from typing import Optional, TypedDict, cast

DATA_DIR = pathlib.Path(__file__).parent / 'data'
MAX_READMES = 40
History = dict[str, dict[str, int]]


class Project(TypedDict, total=False):
    full_name: str
    html_url: str
    description: str
    stargazers_count: int
    delta_1d: Optional[int]
    delta_7d: Optional[int]
    language: Optional[str]
    topics: list[str]
    created_at: str
    pushed_at: Optional[str]
    category_zh: str
    discovery_score: float
    summary_zh: Optional[str]
    difficulty_zh: str
    readme_checked: bool


class Repository(Project, total=False):
    fork: bool
    archived: bool


class Summary(TypedDict, total=False):
    mode: str
    checked_at: str
    zh: str
    difficulty: str
    readme_checked: bool


def readJson(path: pathlib.Path, default: object) -> object:
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except FileNotFoundError:
        return default
    except (OSError, ValueError) as error:
        raise ValueError(f'Cannot safely read {path.name}; existing data preserved.') from error


def validateHistory(value: object) -> History:
    if not isinstance(value, dict):
        raise ValueError('History must map repositories to daily Star snapshots.')
    for name, series in value.items():
        if not isinstance(name, str) or not isinstance(series, dict):
            raise ValueError('Invalid history repository or series.')
        for date, stars in series.items():
            if not isinstance(date, str) or str(dt.date.fromisoformat(date)) != date:
                raise ValueError('Invalid history snapshot date.')
            if type(stars) is not int or stars < 0:
                raise ValueError('History Star counts must be non-negative integers.')
    return cast(History, value)


def validateRepository(value: object) -> Repository:
    if not isinstance(value, dict):
        raise ValueError('Repository must be an object.')
    name, stars = value.get('full_name'), value.get('stargazers_count')
    if not isinstance(name, str) or len(name.split('/')) != 2:
        raise ValueError('Repository name must contain owner/name.')
    if type(stars) is not int or stars < 0:
        raise ValueError(f'Invalid Star count for {name}.')
    if not isinstance(value.get('html_url'), str):
        raise ValueError(f'Missing repository URL for {name}.')
    created = value.get('created_at')
    if not isinstance(created, str):
        raise ValueError(f'Missing creation date for {name}.')
    dt.date.fromisoformat(created[:10])
    return cast(Repository, value)


def loadState(dataDir: pathlib.Path) -> tuple[list[Project], History, dict[str, Summary]]:
    document = readJson(dataDir / 'projects.json', {'projects': []})
    if not isinstance(document, dict) or not isinstance(document.get('projects'), list):
        raise ValueError('Invalid projects document; refusing to replace snapshots.')
    projects = [cast(Project, validateRepository(p)) for p in document['projects']]
    history = validateHistory(readJson(dataDir / 'history.json', {}))
    if any(not history.get(p['full_name']) for p in projects):
        raise ValueError('Tracked repositories are missing history; restore it before collecting.')
    summaries = readJson(dataDir / 'summaries.json', {})
    if not isinstance(summaries, dict) or any(not isinstance(v, dict) for v in summaries.values()):
        raise ValueError('Invalid summary cache; existing data preserved.')
    return projects, history, cast(dict[str, Summary], summaries)


def api(url: str, token: Optional[str] = None) -> dict[str, object]:
    headers = {'Accept': 'application/vnd.github+json', 'User-Agent': 'GitRadar-V3.1'}
    if token:
        headers['Authorization'] = 'Bearer ' + token
    request = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(request, timeout=35) as response:
        payload = json.load(response)
    if not isinstance(payload, dict):
        raise ValueError('GitHub API returned an invalid response.')
    return payload


def discoveryQueries(today: dt.date) -> list[str]:
    return [
        f'created:>={today-dt.timedelta(days=7)} stars:20..2000',
        f'created:>={today-dt.timedelta(days=30)} stars:50..5000',
        f'created:>={today-dt.timedelta(days=90)} stars:100..10000',
        f'pushed:>={today-dt.timedelta(days=7)} stars:100..3000',
        'topic:android-tv stars:>15', 'topic:adblock stars:>20',
        'topic:download-manager stars:>20', 'topic:open-source-apps stars:>20',
        'topic:privacy stars:>50', 'topic:self-hosted stars:>50',
        'topic:ai-agent stars:>50', 'topic:productivity stars:>30',
        'android tv remove ads in:description stars:>10', 'ad blocker in:description stars:>30',
    ]


def discover(today: dt.date, token: Optional[str], warnings: list[str]) -> dict[str, Repository]:
    repos: dict[str, Repository] = {}
    for query in discoveryQueries(today):
        try:
            params = urllib.parse.urlencode({'q': query, 'sort': 'stars', 'order': 'desc', 'per_page': 100})
            payload = api('https://api.github.com/search/repositories?' + params, token)
            results = payload.get('items')
            if not isinstance(results, list):
                raise ValueError('Search response has no repository list.')
            for result in results:
                repo = validateRepository(result)
                if not repo.get('fork') and not repo.get('archived'):
                    repos[repo['full_name'].lower()] = repo
        except (OSError, ValueError, KeyError) as error:
            warnings.append(f'Search {query}: {error}')
        time.sleep(2.1)
    return repos


def refreshTracked(projects: list[Project], repos: dict[str, Repository],
                   token: Optional[str], warnings: list[str]) -> list[Project]:
    retained = []
    for project in projects:
        name = project['full_name']
        if name.lower() in repos:
            repos[name.lower()]['full_name'] = name
            continue
        try:
            repo = validateRepository(api('https://api.github.com/repos/' +
                                         urllib.parse.quote(name, safe='/'), token))
            if repo['full_name'].lower() != name.lower():
                raise ValueError('Repository identity changed; retaining existing tracking name.')
            repo['full_name'] = name
            repos[name.lower()] = repo
        except (OSError, ValueError, KeyError) as error:
            fallback = project.copy()
            fallback.update(delta_1d=None, delta_7d=None, discovery_score=0)
            retained.append(fallback)
            warnings.append(f'Refresh {name}: {error}; retained previous data without a new snapshot.')
        time.sleep(.12)
    return retained


RULES = [
    ('影音去广告', r'ad.?block|adguard|android.?tv|smart.?tv|launcher|iptv|youtube|television'),
    ('影音下载', r'download|video|media|music|player|stream|yt.dlp'),
    ('AI 应用', r'agent|llm|chatbot|openai|rag|diffusion|mcp|ai.?tool'),
    ('隐私安全', r'privacy|security|vpn|firewall|password|encrypt'),
    ('效率工具', r'productivity|automation|workflow|note|office|clipboard'),
    ('系统工具', r'desktop|windows|macos|linux|android|ios|browser|extension'),
    ('自托管', r'self.host|homelab|docker|nas|server'),
    ('游戏娱乐', r'game|gaming|emulator'),
]


def classify(repo: Repository) -> str:
    text = ' '.join([repo['full_name'], repo.get('description') or '',
                     ' '.join(repo.get('topics') or [])]).lower()
    for name, pattern in RULES:
        if re.search(pattern, text):
            return name
    return '其他开源'


def change(series: dict[str, int], stars: int, days: int, today: dt.date) -> Optional[int]:
    baseline = series.get(str(today - dt.timedelta(days=days)))
    return stars - baseline if baseline is not None else None


def buildProject(repo: Repository, history: History, today: dt.date) -> Project:
    name, stars = repo['full_name'], repo['stargazers_count']
    series = history.setdefault(name, {})
    series[str(today)] = stars
    daily, weekly = change(series, stars, 1, today), change(series, stars, 7, today)
    created = repo['created_at']
    age = max(1, (today - dt.date.fromisoformat(created[:10])).days)
    category = classify(repo)
    score = (weekly or 0)*2 + (daily or 0)*3 + min(stars, 2500)/(age+12)*3
    score += 90 if category != '其他开源' else 0
    return {
        'full_name': name, 'html_url': repo['html_url'],
        'description': repo.get('description') or '', 'stargazers_count': stars,
        'delta_1d': daily, 'delta_7d': weekly, 'language': repo.get('language'),
        'topics': repo.get('topics') or [], 'created_at': created,
        'pushed_at': repo.get('pushed_at'), 'category_zh': category,
        'discovery_score': round(score, 1),
    }


LABELS = [
    (r'android.?tv|google.?tv|smart.?tv|television', '智能电视相关工具'),
    (r'ad.?block|adguard|remove ads|debl[o]?at', '广告处理或系统精简工具'),
    (r'video downloader|yt.dlp|download video', '视频下载工具'),
    (r'password manager|password vault', '密码管理工具'),
    (r'screenshot|screen capture', '截图工具'),
    (r'file manager|file explorer', '文件管理工具'),
    (r'notes app|note.taking', '笔记工具'),
    (r'local llm|run llm|language model', '本地大模型相关工具'),
    (r'git.*agent|coding agent|ai agent', 'AI 智能体开发工具'),
    (r'calendar|schedule', '日历或日程工具'),
]


def makeBrief(project: Project, readme: str) -> str:
    text = (project.get('description') or '') + ' ' + readme[:5000]
    for pattern, label in LABELS:
        if re.search(pattern, text, re.I):
            return '【关键词提取】' + label + '；具体功能请以项目 README 为准。'
    return '【资料不足】暂无法从公开简介中可靠提取具体用途，请查看项目 README。'


def assess(readme: str) -> str:
    # Explicit installation markers are clues, not evidence of a successful install.
    text = readme.lower()
    if re.search(r'\bdocker compose\b|\bdocker-compose\b|\bdocker run\b', text):
        return '🟡 可能需要 Docker 配置'
    if re.search(r'\bpip install\b|\bnpm install\b|\bgo install\b|\bcargo install\b', text):
        return '🟡 可能需要命令行安装'
    if re.search(r'\b(apk|dmg|msi|appimage)\b|download.*release|install.*release', text):
        return '🟢 可能提供安装包（请核实）'
    return '⚪ 安装方式未确认'


def enrichProjects(items: list[Project], summaries: dict[str, Summary], today: dt.date,
                   token: Optional[str], warnings: list[str]) -> None:
    for project in items[:MAX_READMES]:
        name = project['full_name']
        cached = summaries.get(name, {})
        if cached.get('mode') == 'free-v31':
            checked = dt.date.fromisoformat(cached['checked_at'])
            if (today - checked).days < 14:
                continue
        try:
            payload = api('https://api.github.com/repos/' +
                          urllib.parse.quote(name, safe='/') + '/readme', token)
            content = payload['content']
            if not isinstance(content, str):
                raise ValueError('README response has no text content.')
            raw = base64.b64decode(content).decode('utf-8', 'replace')[:16000]
            summaries[name] = {'mode': 'free-v31', 'checked_at': str(today),
                               'zh': makeBrief(project, raw), 'difficulty': assess(raw),
                               'readme_checked': True}
        except (OSError, ValueError, KeyError) as error:
            summaries[name] = {'mode': 'free-v31', 'checked_at': str(today),
                               'zh': makeBrief(project, ''), 'difficulty': '⚪ 安装方式未确认',
                               'readme_checked': False}
            warnings.append(f'README {name}: {error}')
        time.sleep(.13)


def attachSummaries(items: list[Project], summaries: dict[str, Summary]) -> None:
    for project in items:
        cached = summaries.get(project['full_name'], {})
        free = cached.get('mode') == 'free-v31'
        project['summary_zh'] = cached.get('zh') if free else None
        project['difficulty_zh'] = cached.get('difficulty', '⚪ 安装方式未确认') if free else '⚪ 安装方式未确认'
        project['readme_checked'] = cached.get('readme_checked', False) if free else False


def validatePreservation(original: History, updated: History, today: dt.date) -> None:
    validateHistory(updated)
    for name, series in original.items():
        for date, stars in series.items():
            if date != str(today) and updated.get(name, {}).get(date) != stars:
                raise ValueError(f'Refusing to remove or rewrite historical snapshot: {name} {date}')


def saveSnapshots(dataDir: pathlib.Path, history: History, summaries: dict[str, Summary],
                  document: dict[str, object]) -> None:
    dataDir.mkdir(exist_ok=True)
    staged: list[tuple[pathlib.Path, pathlib.Path]] = []
    try:
        for name, value in [('history.json', history), ('summaries.json', summaries),
                            ('projects.json', document)]:
            with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=dataDir,
                                             prefix='.' + name + '.', delete=False) as handle:
                staged.append((pathlib.Path(handle.name), dataDir / name))
                json.dump(value, handle, ensure_ascii=False, allow_nan=False)
                handle.flush()
                os.fsync(handle.fileno())
        for temporary, target in staged:
            os.replace(temporary, target)
    finally:
        for temporary, target in staged:
            temporary.unlink(missing_ok=True)


def main() -> None:
    today = dt.datetime.now(dt.timezone.utc).date()
    previous, history, summaries = loadState(DATA_DIR)
    original = {name: series.copy() for name, series in history.items()}
    warnings: list[str] = []
    token = os.getenv('GH_API_TOKEN')
    repos = discover(today, token, warnings)
    retained = refreshTracked(previous, repos, token, warnings)
    if not repos:
        raise RuntimeError('No repositories retrieved; keeping existing data.')
    canonicalNames = {name.lower(): name for name in history}
    for repo in repos.values():
        repo['full_name'] = canonicalNames.get(repo['full_name'].lower(), repo['full_name'])
    items = [buildProject(repo, history, today) for repo in repos.values()]
    items.sort(key=lambda project: project['discovery_score'], reverse=True)
    enrichProjects(items, summaries, today, token, warnings)
    attachSummaries(items, summaries)
    items.extend(retained)
    items.sort(key=lambda project: project['discovery_score'], reverse=True)
    validatePreservation(original, history, today)
    generatedAt = dt.datetime.now(dt.timezone.utc)
    if generatedAt.date() != today:
        raise RuntimeError('Collection crossed UTC midnight; keeping existing data. Run again.')
    document = {'generated_at': generatedAt.isoformat(),
                'count': len(items), 'projects': items, 'warnings': warnings}
    saveSnapshots(DATA_DIR, history, summaries, document)
    print('Collected', len(items), 'repos; free README cache', len(summaries),
          'warnings', len(warnings))


if __name__ == '__main__':
    main()
