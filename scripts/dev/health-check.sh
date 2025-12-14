#!/bin/bash

##############################################################################
# CommandCenter1C - Health Check
##############################################################################
# Проверяет статус всех сервисов
##############################################################################

# Определение путей
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

# Подключение библиотеки
source "$PROJECT_ROOT/scripts/lib/init.sh"

cd "$PROJECT_ROOT"

# Константы проекта
PIDS_DIR="$PROJECT_ROOT/pids"

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
check_process "event-subscriber"
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

    # --noproxy '*' важен для WSL где может быть настроен proxy
    local http_code=$(curl --noproxy '*' -s -o /dev/null -w "%{http_code}" --max-time "$timeout" "$url" 2>/dev/null)

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
check_http "API Gateway" "http://localhost:8180/health"
check_http "Orchestrator" "http://localhost:8200/health"
# Week 4: Check RAS Adapter (ports outside Windows reserved range 8013-8112)
check_http "RAS Adapter" "http://localhost:8188/health"
check_http "Batch Service" "http://localhost:8187/health"

echo ""

##############################################################################
# Проверка инфраструктуры (Docker или Native)
##############################################################################
echo -e "${BLUE}[3] Проверка инфраструктуры:${NC}"
echo ""

# Загрузить переменные окружения для определения режима
if [ -f "$PROJECT_ROOT/.env.local" ]; then
    set -a
    source "$PROJECT_ROOT/.env.local"
    set +a
fi

if is_docker_mode; then
    echo -e "  ${CYAN}Режим: Docker${NC}"

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
else
    echo -e "  ${CYAN}Режим: Native (systemd)${NC}"

    # Проверка нативной инфраструктуры
    check_native_infrastructure_health
fi

echo ""

##############################################################################
# Проверка соединений (детально)
##############################################################################
echo -e "${BLUE}[4] Проверка соединений:${NC}"
echo ""

# Проверить JSON response от API Gateway (port 8180)
if curl --noproxy '*' -s --max-time 3 http://localhost:8180/health 2>/dev/null | grep -q "healthy\|ok"; then
    echo -e "  API Gateway /health: ${GREEN}✓ возвращает валидный JSON${NC}"
else
    echo -e "  API Gateway /health: ${RED}✗ некорректный ответ${NC}"
fi

# Проверить JSON response от Orchestrator (port 8200)
if curl --noproxy '*' -s --max-time 3 http://localhost:8200/health 2>/dev/null | grep -q "healthy\|ok\|database"; then
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

    # Кросс-платформенная проверка (из common-functions.sh)
    if check_port_listening "$port"; then
        echo -e "  Port $port ($service): ${GREEN}✓ открыт${NC}"
        return 0
    else
        echo -e "  Port $port ($service): ${RED}✗ закрыт${NC}"
        return 1
    fi
}

check_port 5173 "Frontend"
check_port 8180 "API Gateway"
check_port 8200 "Orchestrator"
check_port 8188 "RAS Adapter"
check_port 8187 "Batch Service"
check_port "${RAS_PORT:-1539}" "RAS (1C Remote Admin)"
check_port 5432 "PostgreSQL"
check_port 6379 "Redis"

echo ""

##############################################################################
# Проверка мониторинга (опционально)
##############################################################################
echo -e "${BLUE}[6] Проверка мониторинга (опционально):${NC}"
echo ""

if is_docker_mode; then
    # Docker режим - проверяем контейнеры
    # Проверка Prometheus
    if docker ps --format '{{.Names}}' 2>/dev/null | grep -q "cc1c-prometheus-local"; then
        if curl --noproxy '*' -sf http://localhost:9090/-/healthy &>/dev/null; then
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
        if curl --noproxy '*' -sf http://localhost:5000/api/health &>/dev/null; then
            echo -e "  Grafana: ${GREEN}✓ запущен и готов (http://localhost:5000, admin/admin)${NC}"
            check_port 5000 "Grafana" > /dev/null
        else
            echo -e "  Grafana: ${YELLOW}⚠️  запущен, но не отвечает${NC}"
        fi
    else
        echo -e "  Grafana: ${YELLOW}⚠️  не запущен (запустить: ./scripts/dev/start-monitoring.sh)${NC}"
    fi

    # Проверка Jaeger (Distributed Tracing)
    if docker ps --format '{{.Names}}' 2>/dev/null | grep -q "cc1c-jaeger-local"; then
        if curl --noproxy '*' -sf http://localhost:16686/ &>/dev/null; then
            echo -e "  Jaeger: ${GREEN}✓ запущен и готов (http://localhost:16686)${NC}"
            check_port 16686 "Jaeger UI" > /dev/null
            check_port 4317 "OTLP gRPC" > /dev/null
        else
            echo -e "  Jaeger: ${YELLOW}⚠️  запущен, но не отвечает${NC}"
        fi
    else
        echo -e "  Jaeger: ${YELLOW}⚠️  не запущен (запустить: ./scripts/dev/start-monitoring.sh)${NC}"
    fi
else
    # Native режим - проверяем systemd сервисы
    check_native_monitoring_health
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
TOTAL=7
RUNNING=0

# Week 4+: RAS Adapter is the only RAS service
SERVICES=("orchestrator" "api-gateway" "worker" "ras" "ras-adapter" "batch-service" "frontend")

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

##############################################################################
# Проверка Prometheus exporters (опционально)
##############################################################################
echo -e "${BLUE}[7] Prometheus Exporters (опционально):${NC}"
echo ""

check_exporter() {
    local name=$1
    local service=$2
    if systemctl is-active --quiet "$service" 2>/dev/null; then
        echo -e "  ${name}: ${GREEN}✓ запущен${NC}"
    else
        echo -e "  ${name}: ${YELLOW}⚠️  не запущен (sudo systemctl start $service)${NC}"
    fi
}

check_exporter "PostgreSQL Exporter" "prometheus-postgres-exporter"
check_exporter "Redis Exporter" "prometheus-redis-exporter"
check_exporter "Node Exporter" "prometheus-node-exporter"

echo ""
echo -e "${BLUE}Управление:${NC}"
echo -e "  Запустить все:    ${GREEN}./scripts/dev/start-all.sh${NC}"
echo -e "  Остановить все:   ${GREEN}./scripts/dev/stop-all.sh${NC}"
echo -e "  Перезапустить:    ${GREEN}./scripts/dev/restart.sh <service>${NC}"
echo -e "  Просмотр логов:   ${GREEN}./scripts/dev/logs.sh <service>${NC}"
echo ""
