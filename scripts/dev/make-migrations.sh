#!/bin/bash

##############################################################################
# CommandCenter1C - Django Migrations Helper
##############################################################################
#
# Создает миграции Django для текущих изменений моделей.
#
# Usage:
#   ./scripts/dev/make-migrations.sh [app ...]
#
# Examples:
#   ./scripts/dev/make-migrations.sh
#   ./scripts/dev/make-migrations.sh artifacts
#
# Version: 1.0.0
##############################################################################

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

source "$PROJECT_ROOT/scripts/lib/init.sh"

cd "$PROJECT_ROOT/orchestrator"

ORCH_VENV_DIR="$(pwd)/venv"
ORCH_VENV_BIN_DIR="$ORCH_VENV_DIR/$VENV_BIN_DIR"
DJANGO_PYTHON_BIN=""

if [[ ! -d "$ORCH_VENV_DIR" ]]; then
    echo -e "${RED}✗ Не найдено виртуальное окружение: $ORCH_VENV_DIR${NC}"
    echo -e "${YELLOW}Создай venv и установи зависимости перед запуском миграций${NC}"
    exit 1
fi

if ! activate_venv "$ORCH_VENV_DIR"; then
    echo -e "${RED}✗ Не удалось активировать виртуальное окружение: $ORCH_VENV_DIR${NC}"
    exit 1
fi

for candidate in "$ORCH_VENV_BIN_DIR/python" "$ORCH_VENV_BIN_DIR/python3" "$ORCH_VENV_BIN_DIR/python.exe"; do
    if [[ -x "$candidate" ]]; then
        DJANGO_PYTHON_BIN="$candidate"
        break
    fi
done

if [[ -z "$DJANGO_PYTHON_BIN" ]]; then
    echo -e "${RED}✗ Python интерпретатор в venv недоступен (битое окружение?)${NC}"
    exit 1
fi

if ! "$DJANGO_PYTHON_BIN" -c "import django" >/dev/null 2>&1; then
    echo -e "${RED}✗ Django не найден в venv: $DJANGO_PYTHON_BIN${NC}"
    echo -e "${YELLOW}Установи зависимости: source venv/$VENV_BIN_DIR/activate && pip install -r requirements.txt${NC}"
    exit 1
fi

"$DJANGO_PYTHON_BIN" manage.py makemigrations "$@"
