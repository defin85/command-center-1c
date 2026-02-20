#!/usr/bin/env bash

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ORCH_DIR="$PROJECT_ROOT/orchestrator"

if [[ $# -lt 1 ]]; then
  cat <<'USAGE' >&2
Usage:
  ./debug/eval-django.sh "<python statements>"

Examples:
  ./debug/eval-django.sh "print('ok')"
  ./debug/eval-django.sh "from apps.databases.models import Database; print(Database.objects.count())"
USAGE
  exit 1
fi

if [[ -f "$PROJECT_ROOT/.env.local" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "$PROJECT_ROOT/.env.local"
  set +a
fi

if [[ ! -d "$ORCH_DIR/venv" ]]; then
  echo "Missing venv: $ORCH_DIR/venv" >&2
  exit 1
fi

PY_BIN=""
for candidate in "$ORCH_DIR/venv/bin/python" "$ORCH_DIR/venv/bin/python3" "$ORCH_DIR/venv/Scripts/python.exe"; do
  if [[ -x "$candidate" ]]; then
    PY_BIN="$candidate"
    break
  fi
done

if [[ -z "$PY_BIN" ]]; then
  echo "No executable python found in orchestrator/venv" >&2
  exit 1
fi

if ! "$PY_BIN" -c "import django" >/dev/null 2>&1; then
  echo "Django is not available in $PY_BIN" >&2
  exit 1
fi

CODE="$*"
cd "$ORCH_DIR"
"$PY_BIN" manage.py shell -c "$CODE"

