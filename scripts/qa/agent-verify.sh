#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)"
PYTHON_BIN="${PYTHON:-python3}"

cd "$ROOT"

printf 'Check agent-facing docs and feature packs\n'
./scripts/qa/check-agent-docs.sh

printf 'Compile loop scripts\n'
"$PYTHON_BIN" -m py_compile \
  scripts/feature_loop.py \
  scripts/feature_loop_core.py \
  scripts/feature_loop_adapter.py \
  scripts/start_run.py \
  scripts/validate_dataset.py

printf 'Baseline agent verification passed\n'
