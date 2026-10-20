"""只测内置令牌批量能力，不写生产快照。"""
from __future__ import annotations

import datetime as dt
import json
import os
from pathlib import Path
import urllib.request


def main() -> None:
    projects = json.loads(Path('data/projects.json').read_text())['projects']
    fields = []
    for index, project in enumerate(projects[:50]):
        owner, name = project['full_name'].split('/')
        fields.append(f'r{index}: repository(owner:{json.dumps(owner)}, name:{json.dumps(name)})'
                      '{id nameWithOwner createdAt stargazerCount isArchived isFork}')
    query = '{rateLimit {cost remaining resetAt} ' + ' '.join(fields) + '}'
    request = urllib.request.Request('https://api.github.com/graphql',
        data=json.dumps({'query': query}).encode(),
        headers={'Authorization': 'Bearer ' + os.environ['GH_API_TOKEN'],
                 'Content-Type': 'application/json', 'User-Agent': 'GitRadar-V4-probe'})
    with urllib.request.urlopen(request, timeout=45) as response:
        payload = json.load(response)
        headers = {key: response.headers.get(key) for key in
                   ('X-RateLimit-Limit', 'X-RateLimit-Remaining', 'X-RateLimit-Used')}
    data = payload.get('data') or {}
    report = {'checked_at': dt.datetime.now(dt.timezone.utc).isoformat(),
              'token_kind': 'Actions GITHUB_TOKEN', 'requested': len(fields),
              'returned': sum(isinstance(data.get(f'r{i}'), dict) for i in range(len(fields))),
              'rate_limit': data.get('rateLimit'), 'headers': headers,
              'errors': payload.get('errors', []),
              'estimated_batches_for_baseline': (len(projects) + 49) // 50}
    Path('probe-report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps(report, ensure_ascii=False))
    if report['errors'] or report['returned'] < len(fields):
        raise RuntimeError('Batch probe incomplete; inspect report before migration.')


if __name__ == '__main__':
    main()
