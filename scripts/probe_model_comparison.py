"""固定 v3 方法、仅替换14B权重的隔离容量对照。"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import types

ROOT = Path(__file__).resolve().parents[1]
BASELINE = '980b7657415796f9d9c67181dac69365a22e2838'
SOURCE = 'scripts/probe_local_model.py'
FIXTURE = 'tests/fixtures/model_probe/cases.json'
PINS = 'scripts/model_probe_pins.json'
MODEL = 'scripts/model_comparison_14b.json'
SOURCE_SHA256 = '0871654d0a1f0731daa75133c46ab632332bcd9fabde8719f0e44be49e1b74ae'
FIXTURE_SHA256 = '96978ccade1edc8841ad23d7aef2676734157c6b2826a6707d5dbcabe64917bf'
MODEL_SHA256 = 'd1ff6d33271fa0e8e8f7ba32302845fe04ec6ea8b6ff57aa915e5ca168b68ef4'


def gitBytes(relative: str) -> bytes:
    return subprocess.run(['git', 'show', BASELINE + ':' + relative], cwd=ROOT,
                          capture_output=True, check=True, timeout=20).stdout


def verifiedInputs(provenance: dict) -> tuple[bytes, bytes, bytes]:
    source, fixture = gitBytes(SOURCE), gitBytes(FIXTURE)
    provenance.update(source_sha256=hashlib.sha256(source).hexdigest(),
                      baseline_fixture_sha256=hashlib.sha256(fixture).hexdigest())
    if provenance['source_sha256'] != SOURCE_SHA256:
        raise ValueError('Immutable baseline source SHA256 mismatch')
    if provenance['baseline_fixture_sha256'] != FIXTURE_SHA256 or (ROOT / FIXTURE).read_bytes() != fixture:
        raise ValueError('Baseline/current fixture bytes mismatch')
    model = (ROOT / MODEL).read_bytes()
    if hashlib.sha256(model).hexdigest() != MODEL_SHA256:
        raise ValueError('Comparison model pins SHA256 mismatch')
    pins = json.loads(gitBytes(PINS))
    pins['model'] = json.loads(model)
    return source, fixture, (json.dumps(pins, ensure_ascii=False, indent=2) + '\n').encode()


def loadBaseline(source: bytes) -> types.ModuleType:
    if hashlib.sha256(source).hexdigest() != SOURCE_SHA256:
        raise ValueError('Immutable baseline source SHA256 mismatch before exec')
    module = types.ModuleType('gitradar_immutable_v3_comparison')
    module.__file__ = str(ROOT / SOURCE)
    exec(compile(source, 'git:' + BASELINE + ':' + SOURCE, 'exec'), module.__dict__)
    return module


def requireSpace(pins: dict) -> None:
    required = pins['model']['size'] + pins['runtime']['size'] + 2 * 1024 ** 3
    available = shutil.disk_usage(tempfile.gettempdir()).free
    if available < required:
        raise RuntimeError(f'Insufficient temporary disk space: free={available}, required={required} including 2 GiB margin')


def writeJson(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def invokeBaseline(module: types.ModuleType, fixture: bytes, pins: bytes, output: Path) -> int:
    with tempfile.TemporaryDirectory(prefix='gitradar-model-comparison-') as directory:
        module.ROOT = Path(directory)
        for relative, body in [(FIXTURE, fixture), (PINS, pins)]:
            path = module.ROOT / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(body)
        previous = sys.argv
        try:
            sys.argv = [SOURCE, '--output-dir', str(output)]
            return module.main()
        finally:
            sys.argv = previous


def runComparison(output: Path) -> int:
    output.mkdir(parents=True, exist_ok=True)
    provenance = {'baseline_commit': BASELINE, 'expected_source_sha256': SOURCE_SHA256,
                  'event_github_sha': os.environ.get('GITHUB_SHA'),
                  'status': 'failed_unverified', 'scope': 'model-capacity comparison; not production or blind'}
    try:
        provenance['checkout_head'] = subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=ROOT,
            capture_output=True, check=True, timeout=20).stdout.decode().strip()
        source, fixture, pins = verifiedInputs(provenance)
        module = loadBaseline(source)
        module.requirePublicRunner()
        requireSpace(json.loads(pins))
        provenance.update(harness_fixture_sha256=hashlib.sha256(fixture).hexdigest(),
                          harness_pins_sha256=hashlib.sha256(pins).hexdigest(), status='running_unverified')
        writeJson(output / 'comparison-provenance.json', provenance)
        code = invokeBaseline(module, fixture, pins, output)
        provenance.update(status='completed_semantics_unverified' if code == 0 else 'failed_unverified', exit_code=code)
        return code
    except Exception as error:
        provenance['error'] = f'{type(error).__name__}: {error}'
        if not (output / 'report.json').exists():
            writeJson(output / 'report.json', {'status': 'failed_unverified', 'scope': 'comparison_preflight',
                                             'cases': [], 'error': provenance['error']})
        return 1
    finally:
        writeJson(output / 'comparison-provenance.json', provenance)


if __name__ == '__main__':
    raise SystemExit(runComparison(ROOT / '.model-probe'))
