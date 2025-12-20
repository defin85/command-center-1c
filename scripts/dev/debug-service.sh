#!/bin/bash

##############################################################################
# CommandCenter1C - Debug Go Service with Delve
##############################################################################
# Usage: ./debug-service.sh <service-name> [port]
##############################################################################

set -e

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$PROJECT_ROOT"

# Source unified library
source "$PROJECT_ROOT/scripts/lib/init.sh"

# Константы проекта
GO_SERVICES=("api-gateway" "worker" "ras-adapter")

SERVICE=$1
PORT=${2:-2345}  # Default port 2345

if [[ -z "$SERVICE" ]]; then
    log_error "Не указан сервис"
    echo ""
    echo -e "${BLUE}Usage:${NC}"
    echo "  ./scripts/dev/debug-service.sh <service-name> [port]"
    echo ""
    echo -e "${BLUE}Available services:${NC}"
    echo "  api-gateway   (default port: 2345)"
    echo "  worker        (default port: 2346)"
    echo "  ras-adapter (default port: 2347)"
    echo ""
    echo -e "${BLUE}Example:${NC}"
    echo "  ./scripts/dev/debug-service.sh api-gateway 2345"
    exit 1
fi

# Set default ports based on service
case $SERVICE in
    api-gateway)   PORT=${2:-2345} ;;
    worker)        PORT=${2:-2346} ;;
    ras-adapter)   PORT=${2:-2347} ;;
    *)
        log_error "Неизвестный сервис: $SERVICE"
        echo "Available: api-gateway, worker, ras-adapter"
        exit 1
        ;;
esac

SERVICE_PATH="$PROJECT_ROOT/go-services/$SERVICE"

if [[ ! -d "$SERVICE_PATH" ]]; then
    log_error "Директория сервиса не найдена: $SERVICE_PATH"
    exit 1
fi

if [[ ! -f "$SERVICE_PATH/cmd/main.go" ]]; then
    log_error "main.go не найден: $SERVICE_PATH/cmd/main.go"
    exit 1
fi

print_header "Debugging $SERVICE"

log_info "Запускаем Delve debugger..."
echo "   Service: $SERVICE"
echo "   Port: $PORT"
echo "   Path: $SERVICE_PATH"
echo ""
echo -e "${BLUE}Теперь используй MCP tools для отладки:${NC}"
echo "   1. start_debugger(port=$PORT)"
echo "   2. debug_program(path=\"$SERVICE_PATH/cmd/main.go\")"
echo "   3. set_breakpoints(...)"
echo "   4. continue() / next() / step_in() / ..."
echo ""
echo "Для остановки нажми Ctrl+C"
echo ""

cd "$SERVICE_PATH"
dlv debug --headless --listen=:$PORT --api-version=2 --accept-multiclient cmd/main.go
