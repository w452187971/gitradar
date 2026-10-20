#!/usr/bin/env bash
# 仅由手动诊断入口运行，Python 会再次核对公开 Linux runner。
set -euo pipefail
cd "$(dirname "$0")/.."
exec python3 scripts/probe_local_model.py
