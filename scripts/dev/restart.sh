#!/bin/bash

##############################################################################
# CommandCenter1C - Restart Service
##############################################################################
# Перезапускает конкретный сервис
# Usage: ./restart.sh <service-name>
##############################################################################

set -e

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$PROJECT_ROOT"

# Source unified library
source "$PROJECT_ROOT/scripts/lib/init.sh"

# Load environment variables from .env.local
load_env_file

# Константы проекта (нужны для lifecycle.sh)
PIDS_DIR="$PROJECT_ROOT/pids"
LOGS_DIR="$PROJECT_ROOT/logs"
BIN_DIR="$PROJECT_ROOT/bin"

##############################################################################
# Проверка аргументов
##############################################################################
if [ -z "$1" ] || [[ "$1" == "--help" ]] || [[ "$1" == "-h" ]]; then
    echo -e "${BLUE}Usage:${NC} $0 <service-name>"
    echo ""
    list_services
    [[ -z "$1" ]] && exit 1 || exit 0
fi

SERVICE_NAME=$1

# Проверка что сервис существует
category=$(get_service_category "$SERVICE_NAME")
if [ "$category" == "unknown" ]; then
    log_error "Неизвестный сервис: $SERVICE_NAME"
    echo ""
    list_services
    exit 1
fi

##############################################################################
# Перезапуск
##############################################################################
echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}  Перезапуск сервиса: ${SERVICE_NAME}${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

if restart_service "$SERVICE_NAME"; then
    echo ""
    echo -e "${GREEN}========================================${NC}"
    echo -e "${GREEN}  Сервис перезапущен!${NC}"
    echo -e "${GREEN}========================================${NC}"
    echo ""
    echo -e "${BLUE}Лог файл:${NC} $LOGS_DIR/${SERVICE_NAME}.log"
    echo -e "${BLUE}PID файл:${NC} $PIDS_DIR/${SERVICE_NAME}.pid"
    echo ""
    echo -e "${YELLOW}Просмотр логов:${NC}"
    echo -e "  tail -f $LOGS_DIR/${SERVICE_NAME}.log"
    echo -e "  ./scripts/dev/logs.sh ${SERVICE_NAME}"
    echo ""
else
    log_error "Не удалось перезапустить $SERVICE_NAME"
    exit 1
fi
