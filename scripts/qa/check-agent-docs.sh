#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)"
PYTHON_BIN="${PYTHON:-python3}"
status=0

require_path() {
  local rel="$1"
  if [ ! -e "$ROOT/$rel" ]; then
    printf 'missing required path: %s\n' "$rel" >&2
    status=1
  fi
}

require_executable() {
  local rel="$1"
  if [ ! -x "$ROOT/$rel" ]; then
    printf 'missing executable bit: %s\n' "$rel" >&2
    status=1
  fi
}

require_path AGENTS.md
require_path Makefile
require_path docs/agent/INDEX.md
require_path docs/agent/ARCHITECTURE_MAP.md
require_path docs/agent/VERIFY.md
require_path docs/agent/TASK_ROUTING.md
require_path docs/agent/code_review.md
require_path scripts/dev/check-agent-doc-freshness.sh
require_path scripts/feature_loop.py
require_path scripts/feature_loop_core.py
require_path scripts/feature_loop_adapter.py
require_path scripts/start_run.py
require_path scripts/validate_dataset.py
require_path scripts/qa/codex-onboard.sh
require_path scripts/qa/agent-verify.sh
require_path scripts/qa/check-agent-docs.sh
require_path ai/features/README.md

require_executable scripts/dev/check-agent-doc-freshness.sh
require_executable scripts/qa/codex-onboard.sh
require_executable scripts/qa/agent-verify.sh
require_executable scripts/qa/check-agent-docs.sh

./scripts/dev/check-agent-doc-freshness.sh || status=1

while IFS= read -r feature_dir; do
  [ -n "$feature_dir" ] || continue
  rel="${feature_dir#"$ROOT/"}"
  require_path "$rel/feature.md"
  require_path "$rel/change-constraints.md"
  require_path "$rel/checklist.md"
  require_path "$rel/dev.jsonl"
  require_path "$rel/holdout.jsonl"
  "$PYTHON_BIN" "$ROOT/scripts/validate_dataset.py" \
    --dev "$rel/dev.jsonl" \
    --holdout "$rel/holdout.jsonl" >/dev/null || status=1
done < <(find "$ROOT/ai/features" -mindepth 1 -maxdepth 1 -type d 2>/dev/null | LC_ALL=C sort)

if [ "$status" -ne 0 ]; then
  exit "$status"
fi

printf 'Agent-facing docs check passed\n'
