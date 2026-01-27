#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

# Load platform defaults (VENV_BIN_DIR, etc). Keep it minimal (no prompts/services).
export CC1C_LIB_MINIMAL=1
# shellcheck source=/dev/null
source "$PROJECT_ROOT/scripts/lib/init.sh"

ORCHESTRATOR_DIR="$PROJECT_ROOT/orchestrator"
VENV_DIR="$ORCHESTRATOR_DIR/venv"
PYTHON="$VENV_DIR/$VENV_BIN_DIR/python"

if [[ "${1:-}" == "--bootstrap" ]]; then
  shift
  bash "$PROJECT_ROOT/scripts/dev/bootstrap.sh" --skip-docker --skip-build --skip-migrations --only-check
fi

if [[ ! -x "$PYTHON" ]]; then
  echo "ERROR: python venv not found: $PYTHON" >&2
  echo "Hint: run: ./scripts/dev/bootstrap.sh --skip-docker --skip-build --skip-migrations --only-check" >&2
  exit 1
fi

cd "$ORCHESTRATOR_DIR"
exec "$PYTHON" -m pytest "$@"

