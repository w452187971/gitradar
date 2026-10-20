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
SUMMARY_MODE = 'free-v311'
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
    source_description: str


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
    ('影音去广告', r'ad.?block|adguard|android.?tv|smart.?tv|google.?tv|iptv|television|(?<![a-z0-9])tv(?![a-z0-9])|电视|去广告|广告拦截'),
    ('影音下载', r'download|video|media|music|player|stream|yt.dlp|youtube'),
    ('AI 应用', r'(?<![a-z0-9])(?:ai|agents?|llms?|chatbots?|openai|rag|diffusion|mcp)(?![a-z0-9])'),
    ('隐私安全', r'privacy|security|vpn|firewall|password|encrypt'),
    ('效率工具', r'productivity|automation|workflow|note|office|clipboard'),
    ('系统工具', r'desktop|windows|macos|linux|android|ios|browser|extension|launcher'),
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
    (r'\bfile\s+(?:format\s+)?convert(?:er|or)\b|\bconvert\s+(?:files|file formats)\b', '文件格式转换工具'),
    (r'\bgit\b[^.!?\n]{0,100}\b(?:ai\s+)?agents?\b', '面向 AI 智能体的 Git 工具'),
    (r'android.?tv|google.?tv|smart.?tv|television', '智能电视相关工具'),
    (r'\b(?:app(?:lication)?\s+|desktop\s+)?launcher\b', '应用启动器'),
    (r'ad.?block|adguard|remove ads|debl[o]?at', '广告处理或系统精简工具'),
    (r'video downloader|yt.dlp|download video', '视频下载工具'),
    (r'password manager|password vault', '密码管理工具'),
    (r'\b(?:screenshot|screen.capture)\s+(?:tool|app|utility)\b|\b(?:take|capture)\s+screenshots?\b', '截图工具'),
    (r'file manager|file explorer', '文件管理工具'),
    (r'notes app|note.taking', '笔记工具'),
    (r'\b(?:local|on[- ]device|offline)\s+(?:(?:large\s+)?language\s+models?|llms?)\b|\b(?:llms?|(?:large\s+)?language\s+models?)\b[^.!?\n]{0,60}\b(?:locally|on[- ]device|offline)\b', '本地大模型相关工具'),
    (r'\b(?:llms?|(?:large\s+)?language\s+models?)\b', '大模型相关项目'),
    (r'\b(?:coding|ai)\s+agents?\b', 'AI 智能体开发工具'),
    (r'\b(?:calendars?|meetings?|appointments?)\b', '日历或日程工具'),
]


INTRO_HEADING = re.compile(r'^(?:overview|introduction|about(?:\s+[^#]+)?|简介|介绍|概述|项目介绍)$', re.I)
SECONDARY_HEADING = re.compile(r'^(?:screenshots?|examples?|integrations?|demos?|截图|示例|集成)\b', re.I)


def cleanMarkdown(text: str) -> str:
    text = re.sub(r'!\[[^\]]*\]\([^)]*\)|<[^>]+>', ' ', text)
    text = re.sub(r'\[([^\]]*)\]\([^)]*\)', r'\1', text)
    text = re.sub(r'https?://\S+', ' ', text)
    return ' '.join(text.strip(' #*`_').split())


def readmeIntro(readme: str) -> str:
    lines = re.sub(r'<!--.*?-->', '', readme[:12000], flags=re.S).splitlines()
    paragraph: list[str] = []
    fenced = False
    titleSeen = False
    for line in lines:
        if re.match(r'^\s*(?:```|~~~)', line):
            fenced = not fenced
            continue
        if fenced:
            continue
        heading = re.match(r'^\s{0,3}(#{1,6})\s+(.+?)\s*#*$', line)
        title = cleanMarkdown(heading[2] if heading else line)
        if SECONDARY_HEADING.fullmatch(title) or (heading and SECONDARY_HEADING.match(title)):
            break
        if heading:
            if INTRO_HEADING.fullmatch(title):
                continue
            if len(heading[1]) != 1 or titleSeen or paragraph:
                break
            titleSeen = True
            continue
        if not title and paragraph:
            break
        if title and not re.fullmatch(r'[-=]+', title):
            paragraph.append(title)
    return ' '.join(paragraph)[:1200]


def purposeBrief(text: str) -> Optional[str]:
    if len(re.findall(r'[\u4e00-\u9fff]', text)) >= 4:
        return '【项目简介】' + text[:280]
    for pattern, label in LABELS:
        if re.search(pattern, text, re.I):
            return '【关键词提取】' + label + '；具体功能请以项目 README 为准。'
    return None


def makeBrief(project: Project, readme: str) -> str:
    for evidence in [cleanMarkdown(project.get('description') or ''), readmeIntro(readme)]:
        brief = purposeBrief(evidence)
        if brief:
            return brief
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


def cacheIsFresh(project: Project, cached: Summary, today: dt.date) -> bool:
    if cached.get('mode') != SUMMARY_MODE:
        return False
    if cached.get('source_description') != (project.get('description') or ''):
        return False
    checkedAt = cached.get('checked_at')
    if not isinstance(checkedAt, str):
        return False
    try:
        age = (today - dt.date.fromisoformat(checkedAt)).days
    except ValueError:
        return False
    lifetime = 14 if cached.get('readme_checked') is True else 1
    return 0 <= age < lifetime


def buildSummary(project: Project, readme: str, today: dt.date, checked: bool) -> Summary:
    return {'mode': SUMMARY_MODE, 'checked_at': str(today),
            'source_description': project.get('description') or '',
            'zh': makeBrief(project, readme),
            'difficulty': assess(readme) if checked else '⚪ 安装方式未确认',
            'readme_checked': checked}


def summaryQueueKey(cached: Summary, today: dt.date) -> tuple[int, dt.date]:
    checkedAt = cached.get('checked_at')
    checked = dt.date.min
    if isinstance(checkedAt, str):
        try:
            checked = dt.date.fromisoformat(checkedAt)
        except ValueError:
            checked = dt.date.min
    if checked > today:
        checked = dt.date.min
    return (0 if cached.get('mode') != SUMMARY_MODE else 1, checked)


def enrichProjects(items: list[Project], summaries: dict[str, Summary], today: dt.date,
                   token: Optional[str], warnings: list[str]) -> None:
    pending = [project for project in items
               if not cacheIsFresh(project, summaries.get(project['full_name'], {}), today)]
    pending.sort(key=lambda project: summaryQueueKey(summaries.get(project['full_name'], {}), today))
    for project in pending[:MAX_READMES]:
        name = project['full_name']
        try:
            payload = api('https://api.github.com/repos/' +
                          urllib.parse.quote(name, safe='/') + '/readme', token)
            content = payload['content']
            if not isinstance(content, str):
                raise ValueError('README response has no text content.')
            raw = base64.b64decode(content).decode('utf-8', 'replace')[:16000]
            summaries[name] = buildSummary(project, raw, today, True)
        except (OSError, ValueError, KeyError) as error:
            summaries[name] = buildSummary(project, '', today, False)
            warnings.append(f'README {name}: {error}')
        time.sleep(.13)


def attachSummaries(items: list[Project], summaries: dict[str, Summary],
                    today: Optional[dt.date] = None) -> None:
    today = today or dt.datetime.now(dt.timezone.utc).date()
    for project in items:
        cached = summaries.get(project['full_name'], {})
        summary = cached if cacheIsFresh(project, cached, today) else buildSummary(project, '', today, False)
        project['summary_zh'] = summary.get('zh')
        project['difficulty_zh'] = summary.get('difficulty', '⚪ 安装方式未确认')
        project['readme_checked'] = summary.get('readme_checked', False)


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
    items.extend(retained)
    attachSummaries(items, summaries, today)
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
