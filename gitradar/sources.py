"""将已经绑定的官方来源映射到可复核端点，不猜测替代文档。"""
from __future__ import annotations

from dataclasses import dataclass, field
from html.parser import HTMLParser
from urllib.parse import quote, unquote, urlencode, urlsplit

from .models import EvidenceBundle, EvidenceRef, RepositoryRef

MAX_SOURCE_BYTES = 1024 * 1024
SOURCE_TEXT_NORMALIZATION = 'seed_v1'


@dataclass
class SourceRequest:
    url: str
    endpoint: str
    kind: str
    web: bool = False
    old_refs: list[EvidenceRef] = field(default_factory=list)


def verifiedSourceUrl(url: str, ref: RepositoryRef, officialUrls: list[str]) -> bool:
    try:
        parsed = urlsplit(url)
        if parsed.scheme != 'https' or parsed.username or parsed.password or parsed.port not in (None, 443):
            return False
        repository = '/' + ref['full_name'].lower()
        if parsed.hostname in ('github.com', 'raw.githubusercontent.com'):
            return parsed.path.lower() == repository or parsed.path.lower().startswith(repository + '/')
        if parsed.hostname == 'api.github.com':
            path = '/repos' + repository
            return parsed.path.lower() == path or parsed.path.lower().startswith(path + '/')
        return any(urlsplit(origin).scheme == 'https' and parsed.netloc == urlsplit(origin).netloc
                   for origin in officialUrls)
    except ValueError:
        return False


def githubFileEndpoint(url: str, fullName: str) -> str:
    parsed = urlsplit(url)
    parts = unquote(parsed.path).strip('/').split('/')
    if parsed.hostname == 'raw.githubusercontent.com' and len(parts) >= 4:
        revision, path = parts[2], '/'.join(parts[3:])
    elif parsed.hostname == 'github.com' and len(parts) >= 5 and parts[2] == 'blob':
        revision, path = parts[3], '/'.join(parts[4:])
    else:
        raise ValueError('Source does not identify a GitHub file.')
    return '/repos/' + quote(fullName, safe='/') + '/contents/' + quote(path, safe='/') + '?' + urlencode({'ref': revision})


def isRepositoryMetadataUrl(url: object) -> bool:
    parsed = urlsplit(str(url or ''))
    parts = parsed.path.strip('/').split('/')
    return ((parsed.hostname == 'api.github.com' and len(parts) == 3 and parts[0] == 'repos')
            or (parsed.hostname == 'github.com' and len(parts) == 2 and all(parts)))


def sourceRequest(old: EvidenceRef, ref: RepositoryRef, officialUrls: list[str]) -> SourceRequest:
    url, kind = old.get('url', ''), old.get('source_kind', 'readme')
    if not verifiedSourceUrl(url, ref, officialUrls):
        raise ValueError('Source origin is not a verified official origin.')
    parsed = urlsplit(url)
    if kind == 'repository' and isRepositoryMetadataUrl(url):
        endpoint = '/repos/' + quote(ref['full_name'], safe='/')
    elif parsed.hostname == 'api.github.com':
        endpoint = url
    elif parsed.hostname == 'raw.githubusercontent.com' or (parsed.hostname == 'github.com' and '/blob/' in parsed.path):
        endpoint = githubFileEndpoint(url, ref['full_name'])
    else:
        return SourceRequest(url, url, kind, True, [old])
    return SourceRequest(url, endpoint, kind, False, [old])


def boundSourceRequests(previous: EvidenceBundle, ref: RepositoryRef) -> tuple[list[SourceRequest], list[str]]:
    bound = {identity for claim in previous.get('facts', {}).values()
             if isinstance(claim, dict) for identity in claim.get('ref_ids', [])}
    refs = sorted(previous.get('refs', []), key=lambda old: old.get('id') not in bound)
    requests: dict[str, SourceRequest] = {}
    errors: list[str] = []
    for old in refs:
        try:
            candidate = sourceRequest(old, ref, previous.get('official_urls', []))
            key = candidate.url.split('#', 1)[0]
            if key in requests:
                requests[key].old_refs.append(old)
            else:
                requests[key] = candidate
        except ValueError as error:
            errors.append(f'{old.get("url", "")}: {error}')
    return list(requests.values()), errors


class VisibleTextParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.skip = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in ('script', 'style'):
            self.skip += 1
        if tag in ('p', 'h1', 'h2', 'h3', 'li', 'tr', 'div'):
            self.parts.append('\n')

    def handle_endtag(self, tag: str) -> None:
        if tag in ('script', 'style'):
            self.skip -= 1

    def handle_data(self, data: str) -> None:
        if not self.skip:
            self.parts.append(data)


def visibleSourceText(body: object, contentType: str,
                      normalization: str = SOURCE_TEXT_NORMALIZATION) -> str:
    # 已审核片段和上下文哈希绑定 seed_v1，规则变更必须显式换版并重新审核。
    if normalization != 'seed_v1':
        raise ValueError('Unsupported official source text normalization.')
    if isinstance(body, bytes):
        body = body.decode('utf-8')
    if not isinstance(body, str):
        raise ValueError('Official webpage did not return text.')
    if len(body.encode('utf-8')) > MAX_SOURCE_BYTES:
        raise ValueError('Official source exceeds the 1 MiB reading limit.')
    if 'html' in contentType.lower() or body.lstrip().startswith('<'):
        parser = VisibleTextParser()
        parser.feed(body)
        parser.close()
        return '\n'.join(line.strip() for line in ''.join(parser.parts).splitlines() if line.strip())
    return body
