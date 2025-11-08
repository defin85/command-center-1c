#!/bin/bash

##############################################################################
# CommandCenter1C - Stop All Services
##############################################################################
# Останавливает все локально запущенные сервисы
##############################################################################

set -e

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$PROJECT_ROOT"

PIDS_DIR="$PROJECT_ROOT/pids"

# Цвета для вывода
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}  CommandCenter1C - Stopping Services  ${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

##############################################################################
# Функция остановки процесса по PID файлу
##############################################################################
stop_service() {
    local service_name=$1
    local pid_file="$PIDS_DIR/${service_name}.pid"

    if [ ! -f "$pid_file" ]; then
        echo -e "${YELLOW}⚠️  ${service_name}: PID файл не найден${NC}"
        return 0
    fi

    local pid=$(cat "$pid_file")

    if [ -z "$pid" ]; then
        echo -e "${YELLOW}⚠️  ${service_name}: PID файл пуст${NC}"
        rm -f "$pid_file"
        return 0
    fi

    if ! kill -0 "$pid" 2>/dev/null; then
        echo -e "${YELLOW}⚠️  ${service_name}: процесс уже остановлен (PID: $pid)${NC}"
        rm -f "$pid_file"
        return 0
    fi

    echo -e "${BLUE}Остановка ${service_name} (PID: $pid)...${NC}"

    # Graceful shutdown (SIGTERM)
    kill -TERM "$pid" 2>/dev/null || true

    # Ожидать завершения (до 10 секунд)
    local count=0
    while kill -0 "$pid" 2>/dev/null && [ $count -lt 10 ]; do
        sleep 1
        count=$((count + 1))
    done

    # Если не завершился - SIGKILL
    if kill -0 "$pid" 2>/dev/null; then
        echo -e "${YELLOW}   Процесс не завершился gracefully, принудительная остановка...${NC}"
        kill -KILL "$pid" 2>/dev/null || true
        sleep 1
    fi

    # Проверить что процесс действительно остановлен
    if kill -0 "$pid" 2>/dev/null; then
        echo -e "${RED}✗ Не удалось остановить ${service_name}${NC}"
        return 1
    else
        echo -e "${GREEN}✓ ${service_name} остановлен${NC}"
        rm -f "$pid_file"
        return 0
    fi
}

##############################################################################
# Остановка всех сервисов в обратном порядке запуска
##############################################################################

# 11. Frontend
stop_service "frontend"

# 10. Batch Service
stop_service "batch-service"

# 9. Cluster Service
stop_service "cluster-service"

# 8. ras-grpc-gw
stop_service "ras-grpc-gw"

# 7. Go Worker
stop_service "worker"

# 6. API Gateway
stop_service "api-gateway"

# 5. Celery Beat
stop_service "celery-beat"

# 4. Celery Worker
stop_service "celery-worker"

# 3. Django Orchestrator
stop_service "orchestrator"

echo ""

##############################################################################
# Остановка Docker сервисов
##############################################################################
echo -e "${BLUE}Остановка Docker сервисов...${NC}"

if [ -f "$PROJECT_ROOT/docker-compose.local.yml" ]; then
    docker-compose -f docker-compose.local.yml down
    echo -e "${GREEN}✓ Docker сервисы остановлены${NC}"
else
    echo -e "${YELLOW}⚠️  docker-compose.local.yml не найден${NC}"
fi

echo ""

##############################################################################
# Очистка дополнительных процессов (на случай если PID файлы потеряны)
##############################################################################
echo -e "${BLUE}Проверка остаточных процессов...${NC}"

# Поиск процессов по портам
check_and_kill_port() {
    local port=$1
    local service_name=$2

    # Windows (GitBash)
    local pid=$(netstat -ano 2>/dev/null | grep ":$port" | grep LISTENING | awk '{print $5}' | head -1)

    if [ -n "$pid" ] && [ "$pid" != "0" ]; then
        echo -e "${YELLOW}⚠️  Найден процесс на порту $port ($service_name), PID: $pid${NC}"
        taskkill //PID "$pid" //F 2>/dev/null || kill -9 "$pid" 2>/dev/null || true
        echo -e "${GREEN}✓ Процесс на порту $port остановлен${NC}"
    fi
}

check_and_kill_port 5173 "Frontend"
check_and_kill_port 8087 "Batch Service"
check_and_kill_port 8088 "Cluster Service"
check_and_kill_port 8081 "ras-grpc-gw HTTP"
check_and_kill_port 9999 "ras-grpc-gw gRPC"
check_and_kill_port 8080 "API Gateway"
check_and_kill_port 8000 "Orchestrator"

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  ✓ Все сервисы остановлены!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
