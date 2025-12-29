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

if [ -d "venv" ]; then
    activate_venv "$(pwd)/venv"
fi

python manage.py makemigrations "$@"
