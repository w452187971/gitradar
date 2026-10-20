"""离线结算 V4 观察；不会访问网络、修改历史或自行生成独立参考集。"""
from __future__ import annotations

import argparse
import datetime as dt
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from gitradar.evaluation import evaluateObservation


def read(path: Path, default: object) -> object:
    return json.loads(path.read_text()) if path.exists() else default


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--published-at', required=True, help='实际 Pages 生效 UTC 时间')
    parser.add_argument('--references', type=Path, help='独立评审者保存的未来参考集 JSON')
    parser.add_argument('--as-of', default=dt.datetime.now(dt.timezone.utc).isoformat())
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    report = read(root / 'data/observation-reports.json', {})
    projects = read(root / 'data/projects.json', {}).get('projects', [])
    baseline = read(root / 'docs/evaluation/v4-baseline.json', {}).get('candidate_names', [])
    seeds = list(read(root / 'data/curation.json', {}).get('projects', {}))
    references = read(args.references, {}).get('items', []) if args.references else []
    result = evaluateObservation(report, projects, baseline, seeds, references, args.published_at, args.as_of)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
