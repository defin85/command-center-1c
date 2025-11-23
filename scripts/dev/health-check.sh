#!/bin/bash

##############################################################################
# CommandCenter1C - Health Check
##############################################################################
# Проверяет статус всех сервисов
##############################################################################

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
echo -e "${BLUE}  CommandCenter1C - Health Check${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

##############################################################################
# Проверка процессов по PID файлам
##############################################################################
echo -e "${BLUE}[1] Проверка локальных процессов:${NC}"
echo ""

check_process() {
    local service_name=$1
    local pid_file="$PIDS_DIR/${service_name}.pid"

    if [ ! -f "$pid_file" ]; then
        echo -e "  ${service_name}: ${RED}✗ не запущен (PID файл не найден)${NC}"
        return 1
    fi

    local pid=$(cat "$pid_file")

    if [ -z "$pid" ]; then
        echo -e "  ${service_name}: ${RED}✗ не запущен (PID пуст)${NC}"
        return 1
    fi

    if kill -0 "$pid" 2>/dev/null; then
        echo -e "  ${service_name}: ${GREEN}✓ запущен (PID: $pid)${NC}"
        return 0
    else
        echo -e "  ${service_name}: ${RED}✗ не запущен (процесс не найден)${NC}"
        return 1
    fi
}

check_process "orchestrator"
check_process "celery-worker"
check_process "celery-beat"
check_process "api-gateway"
check_process "worker"
check_process "ras"
# Week 4+: RAS Adapter replaces cluster-service
check_process "ras-adapter"
check_process "batch-service"
check_process "frontend"

echo ""

##############################################################################
# Проверка HTTP endpoints
##############################################################################
echo -e "${BLUE}[2] Проверка HTTP endpoints:${NC}"
echo ""

check_http() {
    local service_name=$1
    local url=$2
    local timeout=${3:-5}

    local http_code=$(curl -s -o /dev/null -w "%{http_code}" --max-time "$timeout" "$url" 2>/dev/null)

    if [ "$http_code" = "200" ]; then
        echo -e "  ${service_name}: ${GREEN}✓ доступен (HTTP $http_code)${NC}"
        return 0
    elif [ -n "$http_code" ] && [ "$http_code" != "000" ]; then
        echo -e "  ${service_name}: ${YELLOW}⚠️  отвечает (HTTP $http_code)${NC}"
        return 1
    else
        echo -e "  ${service_name}: ${RED}✗ не доступен (нет ответа)${NC}"
        return 1
    fi
}

check_http "Frontend" "http://localhost:5173"
check_http "API Gateway" "http://localhost:8080/health"
check_http "Orchestrator" "http://localhost:8000/health"
# Week 4: Check RAS Adapter (or Cluster Service for backward compatibility)
check_http "RAS Adapter / Cluster Service" "http://localhost:8088/health"
check_http "Batch Service" "http://localhost:8087/health"

echo ""

##############################################################################
# Проверка Docker сервисов
##############################################################################
echo -e "${BLUE}[3] Проверка Docker сервисов:${NC}"
echo ""

if [ -f "$PROJECT_ROOT/docker-compose.local.yml" ]; then
    # PostgreSQL
    if docker-compose -f docker-compose.local.yml ps postgres 2>/dev/null | grep -q "Up"; then
        if docker-compose -f docker-compose.local.yml exec -T postgres pg_isready -U commandcenter &>/dev/null; then
            echo -e "  PostgreSQL: ${GREEN}✓ запущен и готов${NC}"
        else
            echo -e "  PostgreSQL: ${YELLOW}⚠️  запущен, но не готов${NC}"
        fi
    else
        echo -e "  PostgreSQL: ${RED}✗ не запущен${NC}"
    fi

    # Redis
    if docker-compose -f docker-compose.local.yml ps redis 2>/dev/null | grep -q "Up"; then
        if docker-compose -f docker-compose.local.yml exec -T redis redis-cli ping &>/dev/null | grep -q "PONG"; then
            echo -e "  Redis: ${GREEN}✓ запущен и готов${NC}"
        else
            echo -e "  Redis: ${YELLOW}⚠️  запущен, но не готов${NC}"
        fi
    else
        echo -e "  Redis: ${RED}✗ не запущен${NC}"
    fi

    # ClickHouse
    if docker-compose -f docker-compose.local.yml ps clickhouse 2>/dev/null | grep -q "Up"; then
        echo -e "  ClickHouse: ${GREEN}✓ запущен${NC}"
    else
        echo -e "  ClickHouse: ${YELLOW}⚠️  не запущен (опционально)${NC}"
    fi
else
    echo -e "  ${YELLOW}⚠️  docker-compose.local.yml не найден${NC}"
fi

echo ""

##############################################################################
# Проверка соединений (детально)
##############################################################################
echo -e "${BLUE}[4] Проверка соединений:${NC}"
echo ""

# Проверить JSON response от API Gateway
if curl -s --max-time 3 http://localhost:8080/health 2>/dev/null | grep -q "healthy\|ok"; then
    echo -e "  API Gateway /health: ${GREEN}✓ возвращает валидный JSON${NC}"
else
    echo -e "  API Gateway /health: ${RED}✗ некорректный ответ${NC}"
fi

# Проверить JSON response от Orchestrator
if curl -s --max-time 3 http://localhost:8000/health 2>/dev/null | grep -q "healthy\|ok\|database"; then
    echo -e "  Orchestrator /health: ${GREEN}✓ возвращает валидный JSON${NC}"
else
    echo -e "  Orchestrator /health: ${RED}✗ некорректный ответ${NC}"
fi

echo ""

##############################################################################
# Статистика портов
##############################################################################
echo -e "${BLUE}[5] Статус портов:${NC}"
echo ""

check_port() {
    local port=$1
    local service=$2

    # Windows (GitBash) - netstat
    if netstat -ano 2>/dev/null | grep ":$port" | grep -q LISTENING; then
        echo -e "  Port $port ($service): ${GREEN}✓ открыт${NC}"
        return 0
    else
        echo -e "  Port $port ($service): ${RED}✗ закрыт${NC}"
        return 1
    fi
}

check_port 5173 "Frontend"
check_port 8080 "API Gateway"
check_port 8000 "Orchestrator"
check_port 8088 "RAS Adapter / Cluster Service"
check_port 8087 "Batch Service"
check_port 1545 "RAS (1C Remote Admin)"
check_port 5432 "PostgreSQL"
check_port 6379 "Redis"

echo ""

##############################################################################
# Проверка мониторинга (опционально)
##############################################################################
echo -e "${BLUE}[6] Проверка мониторинга (опционально):${NC}"
echo ""

# Проверка Prometheus
if docker ps --format '{{.Names}}' 2>/dev/null | grep -q "cc1c-prometheus-local"; then
    if curl -sf http://localhost:9090/-/healthy &>/dev/null; then
        echo -e "  Prometheus: ${GREEN}✓ запущен и готов (http://localhost:9090)${NC}"
        check_port 9090 "Prometheus" > /dev/null
    else
        echo -e "  Prometheus: ${YELLOW}⚠️  запущен, но не отвечает${NC}"
    fi
else
    echo -e "  Prometheus: ${YELLOW}⚠️  не запущен (запустить: ./scripts/dev/start-monitoring.sh)${NC}"
fi

# Проверка Grafana
if docker ps --format '{{.Names}}' 2>/dev/null | grep -q "cc1c-grafana-local"; then
    if curl -sf http://localhost:5000/api/health &>/dev/null; then
        echo -e "  Grafana: ${GREEN}✓ запущен и готов (http://localhost:5000, admin/admin)${NC}"
        check_port 5000 "Grafana" > /dev/null
    else
        echo -e "  Grafana: ${YELLOW}⚠️  запущен, но не отвечает${NC}"
    fi
else
    echo -e "  Grafana: ${YELLOW}⚠️  не запущен (запустить: ./scripts/dev/start-monitoring.sh)${NC}"
fi

echo ""

##############################################################################
# Итоговый статус
##############################################################################
echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}  Итоговый статус${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# Подсчитать количество работающих сервисов
TOTAL=10
RUNNING=0

# Week 4+: RAS Adapter is the only RAS service
SERVICES=("orchestrator" "celery-worker" "celery-beat" "api-gateway" "worker" "ras" "ras-adapter" "batch-service" "frontend")

for service in "${SERVICES[@]}"; do
    pid_file="$PIDS_DIR/${service}.pid"
    if [ -f "$pid_file" ]; then
        pid=$(cat "$pid_file")
        if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then
            RUNNING=$((RUNNING + 1))
        fi
    fi
done

if [ $RUNNING -eq $TOTAL ]; then
    echo -e "${GREEN}✓ Все сервисы запущены ($RUNNING/$TOTAL)${NC}"
elif [ $RUNNING -gt 0 ]; then
    echo -e "${YELLOW}⚠️  Запущено $RUNNING/$TOTAL сервисов${NC}"
else
    echo -e "${RED}✗ Сервисы не запущены (0/$TOTAL)${NC}"
fi

echo ""
echo -e "${BLUE}Управление:${NC}"
echo -e "  Запустить все:    ${GREEN}./scripts/dev/start-all.sh${NC}"
echo -e "  Остановить все:   ${GREEN}./scripts/dev/stop-all.sh${NC}"
echo -e "  Перезапустить:    ${GREEN}./scripts/dev/restart.sh <service>${NC}"
echo -e "  Просмотр логов:   ${GREEN}./scripts/dev/logs.sh <service>${NC}"
echo ""
