#!/bin/bash

##############################################################################
# CommandCenter1C - View Service Logs
##############################################################################
# Просмотр логов конкретного сервиса
# Usage: ./logs.sh <service-name> [lines]
##############################################################################

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$PROJECT_ROOT"

LOGS_DIR="$PROJECT_ROOT/logs"

# Цвета для вывода
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

##############################################################################
# Проверка аргументов
##############################################################################
if [ -z "$1" ]; then
    echo -e "${RED}✗ Не указан сервис${NC}"
    echo ""
    echo -e "${BLUE}Usage:${NC}"
    echo -e "  ./scripts/dev/logs.sh <service-name> [lines]"
    echo ""
    echo -e "${BLUE}Available services:${NC}"
    echo -e "  orchestrator      - Django Orchestrator"
    echo -e "  celery-worker     - Celery Worker"
    echo -e "  celery-beat       - Celery Beat"
    echo -e "  api-gateway       - Go API Gateway"
    echo -e "  worker            - Go Worker"
    echo -e "  ras               - 1C RAS Server"
    echo -e "  ras-adapter       - RAS Adapter (Week 4+)"
    echo -e "  batch-service     - Go Batch Service"
    echo -e "  frontend          - React Frontend"
    echo -e "  all               - Все сервисы вместе"
    echo ""
    echo -e "${BLUE}Examples:${NC}"
    echo -e "  ./scripts/dev/logs.sh orchestrator       # tail -f"
    echo -e "  ./scripts/dev/logs.sh api-gateway 100    # last 100 lines + follow"
    echo -e "  ./scripts/dev/logs.sh all                # все логи"
    echo ""
    exit 1
fi

SERVICE_NAME=$1
LINES=${2:-50}  # По умолчанию 50 строк

##############################################################################
# Функция для просмотра лога одного сервиса
##############################################################################
view_log() {
    local service=$1
    local log_file="$LOGS_DIR/${service}.log"

    if [ ! -f "$log_file" ]; then
        echo -e "${YELLOW}⚠️  Лог файл не найден: $log_file${NC}"
        return 1
    fi

    echo -e "${BLUE}========================================${NC}"
    echo -e "${BLUE}  Логи: ${service}${NC}"
    echo -e "${BLUE}========================================${NC}"
    echo ""

    # Показать последние N строк и следить за обновлениями
    tail -n "$LINES" -f "$log_file"
}

##############################################################################
# Функция для просмотра всех логов
##############################################################################
view_all_logs() {
    echo -e "${BLUE}========================================${NC}"
    echo -e "${BLUE}  Логи всех сервисов${NC}"
    echo -e "${BLUE}========================================${NC}"
    echo ""

    local services=("orchestrator" "celery-worker" "celery-beat" "api-gateway" "worker" "ras" "ras-adapter" "batch-service" "frontend")

    for service in "${services[@]}"; do
        local log_file="$LOGS_DIR/${service}.log"

        if [ -f "$log_file" ]; then
            echo -e "${GREEN}>>> ${service} (последние 10 строк):${NC}"
            tail -n 10 "$log_file"
            echo ""
        else
            echo -e "${YELLOW}>>> ${service}: лог файл не найден${NC}"
            echo ""
        fi
    done

    echo -e "${BLUE}Для просмотра логов конкретного сервиса:${NC}"
    echo -e "  ./scripts/dev/logs.sh <service-name>"
    echo ""
}

##############################################################################
# Обработка команды
##############################################################################
case "$SERVICE_NAME" in
    all)
        view_all_logs
        ;;

    orchestrator|celery-worker|celery-beat|api-gateway|worker|ras|ras-adapter|batch-service|frontend)
        view_log "$SERVICE_NAME"
        ;;

    *)
        echo -e "${RED}✗ Неизвестный сервис: ${SERVICE_NAME}${NC}"
        echo ""
        echo -e "${BLUE}Available services:${NC}"
        echo -e "  orchestrator, celery-worker, celery-beat, api-gateway,"
        echo -e "  worker, ras, ras-adapter, batch-service, frontend, all"
        echo ""
        exit 1
        ;;
esac
