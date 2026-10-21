"""Conservative, offline content resolution from versioned official evidence."""
from __future__ import annotations

import copy
import datetime as dt
import re
from collections.abc import Mapping
from typing import Union
from urllib.parse import urlsplit

from gitradar.sources import isRepositoryMetadataUrl

Json = Union[None, bool, int, float, str, list['Json'], dict[str, 'Json']]
Record = dict[str, Json]
FACT_FIELDS = ('purpose', 'audience', 'platforms', 'form', 'prerequisites', 'license', 'cost', 'usage_paths')
REQUIRED_CLAIMS = ('purpose', 'audience', 'platforms', 'form', 'prerequisites', 'license', 'usage_paths')
# Fixed allowlist: unknown and custom licenses require review outside the default feed.
OSI_LICENSES = frozenset({'MIT', 'Apache-2.0', 'BSD-2-Clause', 'BSD-3-Clause', 'ISC',
                         'MPL-2.0', 'GPL-2.0-only', 'GPL-2.0-or-later', 'GPL-3.0-only',
                         'GPL-3.0-or-later', 'LGPL-2.1-only', 'LGPL-2.1-or-later',
                         'LGPL-3.0-only', 'LGPL-3.0-or-later', 'AGPL-3.0-only',
                         'AGPL-3.0-or-later', 'Unlicense', 'Zlib', 'BSL-1.0', 'Artistic-2.0', 'MS-PL'})
TEMPLATES = (
    (r'(?:offline )?file converter', '文件格式转换', '需要转换文件格式的人', '文件转换'),
    (r'local file search (?:tool|application)', '搜索本地文件', '需要在电脑里找文件的人', '文件查找'),
    (r'note-taking (?:application|app|tool)', '记录和整理笔记', '需要整理个人笔记的人', '笔记效率'),
    (r'media downloader', '下载媒体内容', '需要保存媒体内容的人', '下载媒体'),
    (r'password manager', '保存和管理密码', '需要管理账号密码的人', '隐私保护'),
    (r'desktop application launcher', '启动桌面应用', '需要快速打开桌面应用的人', '电视桌面'),
)
CHINESE_TEMPLATES = (
    (r'(?:用于)?(?:转换文件格式|文件格式转换)的?(?:工具|软件|应用)', '文件格式转换', '需要转换文件格式的人', '文件转换'),
    (r'(?:用于)?搜索本地文件的?(?:工具|软件|应用)', '搜索本地文件', '需要在电脑里找文件的人', '文件查找'),
    (r'(?:用于)?(?:记录和整理笔记|记笔记)的?(?:工具|软件|应用)', '记录和整理笔记', '需要整理个人笔记的人', '笔记效率'),
    (r'(?:用于)?下载媒体内容的?(?:工具|软件|应用)', '下载媒体内容', '需要保存媒体内容的人', '下载媒体'),
    (r'(?:密码管理器|管理密码的工具)', '保存和管理密码', '需要管理账号密码的人', '隐私保护'),
    (r'(?:用于)?启动桌面应用的?(?:工具|软件|应用)', '启动桌面应用', '需要快速打开桌面应用的人', '电视桌面'),
)


def _record(value: object) -> Record:
    return dict(value) if isinstance(value, Mapping) else {}


def _records(value: object) -> list[Record]:
    return [_record(item) for item in value if isinstance(item, Mapping)] if isinstance(value, list) else []


def _strings(value: object) -> list[str]:
    return [item for item in value if isinstance(item, str)] if isinstance(value, list) else []


def _time(value: object) -> dt.datetime | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = dt.datetime.fromisoformat(value.replace('Z', '+00:00'))
        return parsed.replace(tzinfo=dt.timezone.utc) if parsed.tzinfo is None else parsed
    except ValueError:
        return None


def _asOf(value: object) -> dt.datetime:
    return _time(value) or dt.datetime.now(dt.timezone.utc)


def isOfficialUrl(url: object, fullName: str, officialUrls: object = None) -> bool:
    if not isinstance(url, str):
        return False
    try:
        parsed = urlsplit(url)
        if parsed.scheme != 'https' or parsed.username or parsed.password or parsed.port not in (None, 443):
            return False
    except ValueError:
        return False
    path = parsed.path.rstrip('/').lower()
    repo = fullName.strip('/').lower()
    if parsed.hostname in ('github.com', 'raw.githubusercontent.com'):
        return bool(repo and (path == '/' + repo or path.startswith('/' + repo + '/')))
    if parsed.hostname == 'api.github.com':
        return bool(repo and (path == '/repos/' + repo or path.startswith('/repos/' + repo + '/')))
    return any(_sameOrigin(parsed, item) for item in _strings(officialUrls))


def _sameOrigin(parsed: object, officialUrl: str) -> bool:
    try:
        verified = urlsplit(officialUrl)
        return verified.scheme == 'https' and parsed.netloc == verified.netloc
    except (ValueError, AttributeError):
        return False


def _refAccepted(ref: Record, bundle: Record) -> bool:
    return isOfficialUrl(ref.get('url'), str(bundle.get('full_name', '')), bundle.get('official_urls'))


def _template(ref: Record, projectName: str = '') -> tuple[str, str, str] | None:
    section = str(ref.get('section', '')).lower()
    if ref.get('source_kind') not in ('readme', 'repository'):
        return None
    if not re.fullmatch(r'(?:introduction|overview|about|description|简介|介绍|概述|)', section):
        return None
    text = str(ref.get('text', ref.get('excerpt', ''))).strip()
    # Only anchored self-descriptions qualify; another tool, negation or examples cannot establish purpose.
    prefix = r'(?:an? |the )'
    if projectName:
        prefix = r'(?:' + re.escape(projectName) + r' is (?:an? |the )|an? |the )'
    firstSentence = re.split(r'[.!。\n]', text, maxsplit=1)[0].strip()
    for pattern, purpose, audience, scene in CHINESE_TEMPLATES:
        if re.fullmatch(r'(?:(?:这是|本项目是))?(?:一款|一个)' + pattern, firstSentence):
            return purpose, audience, scene
    for pattern, purpose, audience, scene in TEMPLATES:
        if re.fullmatch(prefix + pattern + r'(?: for [^.!。]+)?', firstSentence, re.I):
            return purpose, audience, scene
    return None


def deriveFacts(bundle: Record) -> Record:
    refs = [copy.deepcopy(ref) for ref in _records(bundle.get('refs')) if _refAccepted(ref, bundle)]
    facts: Record = {'full_name': bundle.get('full_name', ''), 'node_id': bundle.get('node_id'),
                     'evidence_refs': refs, 'official_urls': bundle.get('official_urls', []),
                     'claims': {}, 'critical_unknowns': bundle.get('critical_unknowns', []),
                     'platforms': [], 'form': 'unknown', 'prerequisites': [], 'usage_paths': []}
    _copyStructuredFacts(facts, _record(bundle.get('facts')), refs)
    if not facts.get('purpose'):
        _deriveTemplateFacts(facts, refs)
    if facts.get('generation_method') == 'supported_template':
        _deriveAutomaticEnvironment(facts, refs)
    return facts


def _copyStructuredFacts(facts: Record, structured: Record, refs: list[Record]) -> None:
    known = {str(ref.get('id')) for ref in refs}
    claims = _record(facts['claims'])
    for key in FACT_FIELDS:
        field = _record(structured.get(key))
        ids = _strings(field.get('ref_ids'))
        if ids and all(refId in known for refId in ids):
            facts[key] = copy.deepcopy(field.get('value'))
            claims[key] = ids
        if key == 'prerequisites' and field.get('complete') is False:
            facts['critical_unknowns'] = _strings(facts.get('critical_unknowns')) + ['prerequisites']
    facts['claims'] = claims
    facts['critical_unknowns'] = _strings(facts.get('critical_unknowns')) + _strings(structured.get('critical_unknowns'))


def _deriveTemplateFacts(facts: Record, refs: list[Record]) -> None:
    for ref in sorted(refs, key=lambda item: not bool(re.search(r'[\u4e00-\u9fff]', str(item.get('text', ''))))):
        result = _template(ref, str(facts.get('full_name', '')).rsplit('/', 1)[-1])
        if result:
            facts.update(purpose=result[0], audience=result[1], scenes=[result[2]], primary_scene=result[2])
            claims = _record(facts['claims'])
            claims.update(purpose=[str(ref['id'])], audience=[str(ref['id'])])
            facts.update(claims=claims, generation_method='supported_template')
            return


def resolveContent(facts: Record, curation: Record | None = None, asOf: str | None = None) -> Record:
    editorial = copy.deepcopy(curation or {})
    content = copy.deepcopy(facts)
    content.update(editorial)
    content['evidence_refs'] = copy.deepcopy(facts.get('evidence_refs', []))
    content['official_urls'] = copy.deepcopy(facts.get('official_urls', []))
    content['critical_unknowns'] = list(dict.fromkeys(_strings(facts.get('critical_unknowns'))
                                                    + _strings(editorial.get('critical_unknowns'))))
    automatic = not editorial and facts.get('generation_method') == 'supported_template'
    if automatic:
        content.update(status='published', review_kind='automatic_template',
                       recommendation_reason=str(facts.get('purpose', '')),
                       evidence_hashes={str(ref.get('id')): ref.get('content_hash')
                                        for ref in _records(facts.get('evidence_refs'))})
    content['status'] = editorial.get('status', content.get('status', 'evidence_ready' if facts.get('purpose') else 'queued'))
    reasons = _evidenceProblems(content, _asOf(asOf), bool(editorial) or automatic)
    blocked = any(reason.startswith(('missing_source:', 'identity_conflict', 'invalid_path:')) for reason in reasons)
    status = 'blocked' if blocked else 'review_required' if reasons else str(content['status'])
    content.update(effective_status=status, invalidation_reasons=reasons)
    content['eligibility'] = eligibleForRecommendation(content, asOf=asOf)
    return content


def _evidenceProblems(content: Record, asOf: dt.datetime, reviewed: bool) -> list[str]:
    refs = {str(ref.get('id')): ref for ref in _records(content.get('evidence_refs'))}
    claims, hashes = _record(content.get('claims')), _record(content.get('evidence_hashes'))
    reasons: list[str] = []
    for field in tuple(dict.fromkeys((*REQUIRED_CLAIMS, *claims.keys()))):
        ids = _strings(claims.get(field))
        if not ids:
            reasons.append('missing_claim:' + field)
        for refId in ids:
            ref = refs.get(refId, {})
            reasons.extend(_checkRef(refId, field, ref, hashes, reviewed, asOf))
    reasons.extend(_contextProblems(content, refs))
    reasons.extend(_pathEvidenceProblems(content, refs, asOf))
    if content.get('identity_conflict') or 'identity_conflict' in _strings(content.get('critical_unknowns')):
        reasons.append('identity_conflict')
    return list(dict.fromkeys(reasons))


def hasSourceContext(ref: Record) -> bool:
    kind = ref.get('source_kind')
    return (kind in ('readme', 'official_site', 'official_document', 'release') or
            (kind == 'repository' and bool(ref.get('url')) and not isRepositoryMetadataUrl(ref['url'])))


def _contextProblems(content: Record, refs: dict[str, Record]) -> list[str]:
    expected = _record(content.get('evidence_context_hashes'))
    bound = {refId for ids in _record(content.get('claims')).values() for refId in _strings(ids)}
    reasons: list[str] = []
    for refId in bound:
        ref = refs.get(refId, {})
        if not hasSourceContext(ref):
            continue
        current, reviewed = ref.get('source_hash'), expected.get(refId)
        if reviewed and not ref.get('context_changed') and reviewed == ref.get('navigation_equivalent_hash'):
            continue
        if (ref.get('context_changed') and (not reviewed or current != reviewed)) or (reviewed and current != reviewed):
            reasons.append('context_changed:' + refId)
    return reasons


def pathClaimRefs(content: Record, path: Record, refs: list[Record]) -> list[str]:
    claims = _strings(_record(content.get('claims')).get('usage_paths'))
    explicit = _strings(path.get('ref_ids'))
    if explicit:
        return [refId for refId in explicit if refId in claims]
    url = str(path.get('url', '')).split('#', 1)[0]
    matching = [str(ref.get('id')) for ref in refs if ref.get('id') in claims
                and str(ref.get('url', '')).split('#', 1)[0] == url]
    return matching or claims


def _pathEvidenceProblems(content: Record, refs: dict[str, Record], asOf: dt.datetime) -> list[str]:
    reasons: list[str] = []
    for path in _records(content.get('usage_paths')):
        url = str(path.get('url', ''))
        for refId in pathClaimRefs(content, path, list(refs.values())):
            ref = refs.get(refId, {})
            if not isinstance(ref.get('path_checks'), dict):
                continue
            check = _record(_record(ref['path_checks']).get(url))
            checked = _time(check.get('checked_at'))
            if check.get('status') in (404, 410):
                reasons.append('missing_path:' + url)
            elif (check.get('status') != 200 or checked is None or checked > asOf
                    or asOf - checked > dt.timedelta(days=7)):
                reasons.append('unverified_path:' + url)
    return reasons


def _checkRef(refId: str, field: str, ref: Record, hashes: Record,
              reviewed: bool, asOf: dt.datetime) -> list[str]:
    if (not ref or ref.get('status') in (404, 410, 'deleted', 'not_found')
            or (field == 'usage_paths' and ref.get('path_status') in (404, 410, 'deleted', 'not_found'))):
        return ['missing_source:' + refId]
    reasons: list[str] = []
    if reviewed and (not hashes.get(refId) or hashes.get(refId) != ref.get('content_hash')):
        reasons.append('changed_evidence:' + refId)
    checked = _time(ref.get('checked_at'))
    if checked is None or checked > asOf or asOf - checked > dt.timedelta(days=14):
        reasons.append('stale_evidence:' + refId)
    if field == 'usage_paths' or ref.get('asset_id'):
        pathChecked = _time(ref.get('path_checked_at', ref.get('checked_at')))
        if pathChecked is None or pathChecked > asOf or asOf - pathChecked > dt.timedelta(days=7):
            reasons.append('stale_path:' + refId)
    return reasons


def eligibleForRecommendation(content: Record, observation: Record | None = None,
                              asOf: str | None = None) -> Record:
    reasons = _strings(content.get('invalidation_reasons'))
    if content.get('effective_status') != 'published':
        reasons.append('not_published')
    reasons.extend(_evidenceProblems(content, _asOf(asOf), bool(content.get('review_kind'))))
    reasons.extend(_contentProblems(content))
    if observation and (observation.get('identity_conflict') or observation.get('status') in ('not_found', 'blocked')
                        or observation.get('observation_status') == 'identity_conflict'
                        or observation.get('http_status') in (404, 410) or observation.get('archived') is True
                        or observation.get('fork') is True):
        reasons.append('repository_unavailable')
    if content.get('critical_unknowns'):
        reasons.append('critical_unknowns')
    return {'eligible': not reasons, 'reasons': list(dict.fromkeys(reasons))}


def _contentProblems(content: Record) -> list[str]:
    reasons = []
    for field in ('purpose', 'audience', 'recommendation_reason', 'primary_scene'):
        if not isinstance(content.get(field), str) or not str(content.get(field, '')).strip():
            reasons.append('missing_' + field)
    if not _knownLicense(content.get('license')):
        reasons.append('unknown_license')
    if not _strings(content.get('platforms')) or content.get('form') in (None, '', 'unknown'):
        reasons.append('unknown_environment')
    paths = _records(content.get('usage_paths'))
    if not paths:
        reasons.append('missing_usage_path')
    for path in paths:
        if not isOfficialUrl(path.get('url'), str(content.get('full_name', '')), content.get('official_urls')):
            reasons.append('invalid_path:' + str(path.get('url', '')))
    return reasons


def _knownLicense(value: object) -> bool:
    if not isinstance(value, str):
        return False
    parts = re.split(r'\s+(?:OR|AND)\s+', value)
    return bool(parts) and all(part in OSI_LICENSES for part in parts)


def _bind(facts: Record, field: str, value: Json, refId: str) -> None:
    facts[field] = value
    claims = _record(facts.get('claims'))
    claims[field] = [refId]
    facts['claims'] = claims


def _positiveSentences(text: str) -> list[str]:
    sentences = [part.strip() for part in re.split(r'[.!。\n]', text) if part.strip()]
    return [part for part in sentences if not re.search(r'\b(?:not|never|unsupported|except)\b|不支持|不能', part, re.I)]


def _deriveAutomaticEnvironment(facts: Record, refs: list[Record]) -> None:
    for ref in refs:
        text = str(ref.get('text', ref.get('excerpt', '')))
        section = str(ref.get('section', '')).lower()
        if ref.get('source_kind') in ('repository', 'license'):
            _deriveLicense(facts, ref, text)
        if ref.get('source_kind') != 'readme':
            continue
        if re.fullmatch(r'introduction|overview|about|description|简介|介绍|概述|', section):
            _deriveFormAndPlatforms(facts, ref, text)
        if re.fullmatch(r'installation|install|getting started|download|requirements|安装|下载|使用|前置条件', section):
            _deriveFormAndPlatforms(facts, ref, text)
            _deriveInstallation(facts, ref, text)
    unknowns = _strings(facts.get('critical_unknowns'))
    if 'prerequisites' not in _record(facts.get('claims')):
        unknowns.append('prerequisites')
    facts['critical_unknowns'] = list(dict.fromkeys(unknowns))
    facts.setdefault('cost', '官方未说明费用；开源许可不代表服务免费')


def _deriveLicense(facts: Record, ref: Record, text: str) -> None:
    value = ref.get('license_spdx_id')
    if value is None:
        match = re.search(r'SPDX-License-Identifier:\s*([^\n]+)', text)
        value = match.group(1).strip() if match else None
    if _knownLicense(value):
        _bind(facts, 'license', str(value), str(ref['id']))


def _deriveFormAndPlatforms(facts: Record, ref: Record, text: str) -> None:
    forms = ((r'\bdesktop (?:application|app)\b', 'desktop_app'),
             (r'\bweb (?:application|app)\b', 'web_app'),
             (r'\bcommand-line (?:tool|application)\b', 'cli'),
             (r'\bself-hosted (?:service|application)\b', 'self_hosted'))
    for sentence in _positiveSentences(text):
        for pattern, form in forms:
            selfPrefix = r'(?:(?:This(?: project| application| app| tool)?|It|' + re.escape(
                str(facts.get('full_name', '')).rsplit('/', 1)[-1]) + r') is )?(?:an? )?'
            if re.fullmatch(selfPrefix + pattern + r'(?: for [^.!。]+)?', sentence, re.I):
                _bind(facts, 'form', form, str(ref['id']))
        if not re.match(r'(?:supports?|available for|runs on)\s', sentence, re.I):
            continue
        platforms = [name for name in ('Windows', 'macOS', 'Linux', 'Android TV', 'iOS')
                     if re.search(r'\b' + re.escape(name) + r'\b', sentence, re.I)]
        if platforms:
            _bind(facts, 'platforms', platforms, str(ref['id']))


def _deriveInstallation(facts: Record, ref: Record, text: str) -> None:
    prerequisites = []
    complete = False
    for sentence in _positiveSentences(text):
        if re.fullmatch(r'No account or additional software required', sentence, re.I):
            complete = True
        if re.match(r'Requires?\s+', sentence, re.I):
            prerequisites.append(sentence)
            complete = True
        if re.fullmatch(r'Free of charge|Free to use', sentence, re.I):
            _bind(facts, 'cost', '官方声明免费使用', str(ref['id']))
        elif re.search(r'\bpaid\b|\bpayment\b|\bsubscription\b', sentence, re.I):
            _bind(facts, 'cost', '官方说明：' + sentence, str(ref['id']))
    if complete:
        _bind(facts, 'prerequisites', prerequisites, str(ref['id']))
    paths = _automaticPaths(facts, text)
    if paths:
        _bind(facts, 'usage_paths', paths, str(ref['id']))


def _automaticPaths(facts: Record, text: str) -> list[Record]:
    paths = []
    positiveLines = '\n'.join(line for line in text.splitlines()
                              if not re.search(r'\b(?:not|never|unsupported)\b|不可|禁止', line, re.I))
    for label, url in re.findall(r'\[([^\]]+)\]\((https://[^\s)]+)\)', positiveLines):
        if not re.search(r'installer|download|installation|getting started|web app|安装|下载', label, re.I):
            continue
        if isOfficialUrl(url, str(facts.get('full_name', '')), facts.get('official_urls')):
            kind = 'web' if re.search(r'web app', label, re.I) else 'documentation'
            paths.append({'url': url, 'kind': kind, 'label': '官方使用入口：' + label})
    return paths
