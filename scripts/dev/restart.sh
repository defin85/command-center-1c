#!/bin/bash

##############################################################################
# CommandCenter1C - Restart Service
##############################################################################
# Перезапускает конкретный сервис
# Usage: ./restart.sh <service-name>
##############################################################################

set -e

# Source common functions
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/common-functions.sh"

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$PROJECT_ROOT"

# Load environment variables from .env.local
load_env_file

PIDS_DIR="$PROJECT_ROOT/pids"
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
    echo -e "  ./scripts/dev/restart.sh <service-name>"
    echo ""
    echo -e "${BLUE}Available services:${NC}"
    echo -e "  orchestrator      - Django Orchestrator (port 8000)"
    echo -e "  celery-worker     - Celery Worker"
    echo -e "  celery-beat       - Celery Beat"
    echo -e "  api-gateway       - Go API Gateway (port 8080)"
    echo -e "  worker            - Go Worker"
    echo -e "  ras               - 1C RAS Server (port 1545)"
    echo -e "  ras-adapter       - Go RAS Adapter (port 8088)"
    echo -e "  batch-service     - Go Batch Service (port 8087)"
    echo -e "  frontend          - React Frontend (port 5173)"
    echo ""
    exit 1
fi

SERVICE_NAME=$1
PID_FILE="$PIDS_DIR/${SERVICE_NAME}.pid"
LOG_FILE="$LOGS_DIR/${SERVICE_NAME}.log"

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}  Перезапуск сервиса: ${SERVICE_NAME}${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

##############################################################################
# Остановка сервиса
##############################################################################
echo -e "${BLUE}[1/2] Остановка ${SERVICE_NAME}...${NC}"

if [ -f "$PID_FILE" ]; then
    PID=$(cat "$PID_FILE")

    if [ -n "$PID" ] && kill -0 "$PID" 2>/dev/null; then
        echo -e "${YELLOW}   Остановка процесса (PID: $PID)...${NC}"
        kill -TERM "$PID" 2>/dev/null || true

        # Ожидать завершения
        count=0
        while kill -0 "$PID" 2>/dev/null && [ $count -lt 10 ]; do
            sleep 1
            count=$((count + 1))
        done

        # Принудительная остановка если не завершился
        if kill -0 "$PID" 2>/dev/null; then
            kill -KILL "$PID" 2>/dev/null || true
        fi

        echo -e "${GREEN}✓ Процесс остановлен${NC}"
    else
        echo -e "${YELLOW}⚠️  Процесс не запущен${NC}"
    fi

    rm -f "$PID_FILE"
else
    echo -e "${YELLOW}⚠️  PID файл не найден, пропуск остановки${NC}"
fi

echo ""

##############################################################################
# Запуск сервиса
##############################################################################
echo -e "${BLUE}[2/2] Запуск ${SERVICE_NAME}...${NC}"

# Очистить старый лог файл
> "$LOG_FILE"

case "$SERVICE_NAME" in
    orchestrator)
        cd "$PROJECT_ROOT/orchestrator"
        if [ -d "venv" ]; then
            source venv/bin/activate 2>/dev/null || source venv/Scripts/activate 2>/dev/null
        fi
        nohup python manage.py runserver 0.0.0.0:8000 > "$LOG_FILE" 2>&1 &
        NEW_PID=$!
        ;;

    celery-worker)
        cd "$PROJECT_ROOT/orchestrator"
        if [ -d "venv" ]; then
            source venv/bin/activate 2>/dev/null || source venv/Scripts/activate 2>/dev/null
        fi
        # Using gevent pool for async I/O operations (Windows compatible)
        # -P gevent: lightweight concurrency via green threads
        # --concurrency=100: up to 100 concurrent greenlets
        nohup celery -A config worker -P gevent --concurrency=100 --loglevel=info > "$LOG_FILE" 2>&1 &
        NEW_PID=$!
        ;;

    celery-beat)
        cd "$PROJECT_ROOT/orchestrator"
        if [ -d "venv" ]; then
            source venv/bin/activate 2>/dev/null || source venv/Scripts/activate 2>/dev/null
        fi
        rm -f celerybeat-schedule celerybeat-schedule.db
        nohup celery -A config beat --loglevel=info > "$LOG_FILE" 2>&1 &
        NEW_PID=$!
        ;;


    api-gateway)
        BINARY_PATH="$PROJECT_ROOT/bin/cc1c-api-gateway.exe"
        if [ -f "$BINARY_PATH" ]; then
            nohup "$BINARY_PATH" > "$LOG_FILE" 2>&1 &
        else
            cd "$PROJECT_ROOT/go-services/api-gateway"
            nohup go run cmd/main.go > "$LOG_FILE" 2>&1 &
        fi
        NEW_PID=$!
        ;;

    worker)
        BINARY_PATH="$PROJECT_ROOT/bin/cc1c-worker.exe"
        if [ -f "$BINARY_PATH" ]; then
            nohup "$BINARY_PATH" > "$LOG_FILE" 2>&1 &
        else
            cd "$PROJECT_ROOT/go-services/worker"
            nohup go run cmd/main.go > "$LOG_FILE" 2>&1 &
        fi
        NEW_PID=$!
        ;;

    ras)
        # .env.local уже загружен в начале скрипта

        if [ -z "$PLATFORM_1C_BIN_PATH" ]; then
            echo -e "${RED}✗ PLATFORM_1C_BIN_PATH не задан в .env.local${NC}"
            exit 1
        fi

        RAS_EXE="$PLATFORM_1C_BIN_PATH/ras.exe"
        if [ ! -f "$RAS_EXE" ]; then
            echo -e "${RED}✗ ras.exe не найден: $RAS_EXE${NC}"
            exit 1
        fi

        nohup "$RAS_EXE" cluster --port=${RAS_PORT:-1545} > "$LOG_FILE" 2>&1 &
        NEW_PID=$!
        ;;

    ras-adapter)
        # .env.local уже загружен в начале скрипта
        export SERVER_PORT=8088

        BINARY_PATH="$PROJECT_ROOT/bin/cc1c-ras-adapter.exe"
        if [ -f "$BINARY_PATH" ]; then
            nohup "$BINARY_PATH" > "$LOG_FILE" 2>&1 &
        else
            cd "$PROJECT_ROOT/go-services/ras-adapter"
            nohup go run cmd/main.go > "$LOG_FILE" 2>&1 &
        fi
        NEW_PID=$!
        ;;

    batch-service)
        # .env.local уже загружен в начале скрипта
        export SERVER_PORT=8087
        
        BINARY_PATH="$PROJECT_ROOT/bin/cc1c-batch-service.exe"
        if [ -f "$BINARY_PATH" ]; then
            nohup "$BINARY_PATH" > "$LOG_FILE" 2>&1 &
        else
            cd "$PROJECT_ROOT/go-services/batch-service"
            nohup go run cmd/main.go > "$LOG_FILE" 2>&1 &
        fi
        NEW_PID=$!
        ;;

    frontend)
        cd "$PROJECT_ROOT/frontend"
        nohup npm run dev > "$LOG_FILE" 2>&1 &
        NEW_PID=$!
        ;;

    *)
        echo -e "${RED}✗ Неизвестный сервис: ${SERVICE_NAME}${NC}"
        echo ""
        echo -e "${BLUE}Available services:${NC}"
        echo -e "  orchestrator, celery-worker, celery-beat, api-gateway,"
        echo -e "  worker, ras-adapter, batch-service, frontend"
        echo ""
        exit 1
        ;;
esac

# Сохранить PID
echo $NEW_PID > "$PID_FILE"

# Проверить что процесс запущен
sleep 3
if kill -0 $NEW_PID 2>/dev/null; then
    echo -e "${GREEN}✓ ${SERVICE_NAME} успешно запущен (PID: $NEW_PID)${NC}"
else
    echo -e "${RED}✗ Не удалось запустить ${SERVICE_NAME}${NC}"
    echo -e "${YELLOW}Логи:${NC}"
    tail -n 20 "$LOG_FILE"
    exit 1
fi

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  ✓ Сервис перезапущен!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo -e "${BLUE}Лог файл:${NC} $LOG_FILE"
echo -e "${BLUE}PID файл:${NC} $PID_FILE"
echo ""
echo -e "${YELLOW}Просмотр логов:${NC}"
echo -e "  tail -f $LOG_FILE"
echo -e "  ./scripts/dev/logs.sh ${SERVICE_NAME}"
echo ""
