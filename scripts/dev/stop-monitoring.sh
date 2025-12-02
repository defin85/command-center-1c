#!/bin/bash

##############################################################################
# Stop Monitoring & Observability Services (Prometheus + Grafana + Jaeger)
# Usage: ./scripts/dev/stop-monitoring.sh
##############################################################################

set -euo pipefail

# Определение путей
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

# Подключение библиотеки
source "$PROJECT_ROOT/scripts/lib/init.sh"

# Загрузить переменные окружения для определения режима
if [ -f "$PROJECT_ROOT/.env.local" ]; then
    set -a
    source "$PROJECT_ROOT/.env.local"
    set +a
fi

cd "$PROJECT_ROOT"

print_header "Stopping Monitoring & Observability"

if is_docker_mode; then
    docker-compose -f docker-compose.local.monitoring.yml down

    echo ""
    log_success "Monitoring Docker containers stopped"
    echo ""
    log_info "To preserve data: volumes are NOT deleted"
    log_info "To remove all data: docker volume rm cc1c-prometheus-local-data cc1c-grafana-local-data"
else
    # Native режим - пропускает сервисы с автозапуском
    log_info "Режим: Native (systemd)"
    echo ""

    stop_native_monitoring

    echo ""
    log_success "Мониторинг проверен (сервисы с автозапуском сохранены)"
    echo ""
    log_info "Для принудительной остановки (даже с автозапуском):"
    echo "  ./scripts/dev/infrastructure.sh stop --monitoring"
    echo ""
    log_info "Или вручную через systemctl:"
    echo "  sudo systemctl stop prometheus grafana jaeger"
fi
echo ""
