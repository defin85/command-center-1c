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

# Загрузить переменные окружения (нужно для VITE_BASE_HOST и режимов)
load_env_file
FRONTEND_PORT="${FRONTEND_PORT:-15173}"

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

FRONTEND_URL="http://localhost:${FRONTEND_PORT}"
if [ -n "${VITE_BASE_HOST:-}" ]; then
    FRONTEND_URL="http://${VITE_BASE_HOST}:${FRONTEND_PORT}"
fi
if [ -f "$PROJECT_ROOT/frontend/.env.local" ]; then
    frontend_dev_url=$(awk -F= '/^VITE_DEV_SERVER_URL=/{print $2}' "$PROJECT_ROOT/frontend/.env.local" | tail -n 1)
    frontend_dev_host=$(awk -F= '/^VITE_DEV_SERVER_HOST=/{print $2}' "$PROJECT_ROOT/frontend/.env.local" | tail -n 1)
    frontend_base_host=$(awk -F= '/^VITE_BASE_HOST=/{print $2}' "$PROJECT_ROOT/frontend/.env.local" | tail -n 1)
    frontend_ws_host=$(awk -F= '/^VITE_WS_HOST=/{print $2}' "$PROJECT_ROOT/frontend/.env.local" | tail -n 1)
    frontend_api_url=$(awk -F= '/^VITE_API_URL=/{print $2}' "$PROJECT_ROOT/frontend/.env.local" | tail -n 1)

    if [ -n "$frontend_dev_url" ]; then
        FRONTEND_URL="$frontend_dev_url"
    elif [ -n "$frontend_dev_host" ]; then
        FRONTEND_URL="http://${frontend_dev_host}:${FRONTEND_PORT}"
    elif [ -n "$frontend_base_host" ]; then
        FRONTEND_URL="http://${frontend_base_host}:${FRONTEND_PORT}"
    elif [ -n "$frontend_ws_host" ]; then
        ws_host=${frontend_ws_host%%:*}
        FRONTEND_URL="http://${ws_host}:${FRONTEND_PORT}"
    elif [ -n "$frontend_api_url" ]; then
        api_host=$(echo "$frontend_api_url" | sed -E 's#^[^/]*//##; s#/.*##; s#:.*##')
        if [ -n "$api_host" ]; then
            FRONTEND_URL="http://${api_host}:${FRONTEND_PORT}"
        fi
    fi
fi

check_http "Frontend" "$FRONTEND_URL"
check_http "API Gateway" "http://localhost:8180/health"
check_http "Orchestrator" "http://localhost:8200/health"

echo ""

##############################################################################
# Проверка инфраструктуры (Docker или Native)
##############################################################################
echo -e "${BLUE}[3] Проверка инфраструктуры:${NC}"
echo ""

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

check_port "$FRONTEND_PORT" "Frontend"
check_port 8180 "API Gateway"
check_port 8200 "Orchestrator"
check_port 8188 "RAS Adapter"
check_port "${RAS_PORT:-1539}" "RAS (1C Remote Admin)"
check_port 5432 "PostgreSQL"
check_port 6379 "Redis"
check_port 9000 "MinIO"

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
TOTAL=6
RUNNING=0

# Week 4+: RAS Adapter is the only RAS service
SERVICES=("orchestrator" "api-gateway" "worker" "ras" "frontend")

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
check_exporter "Blackbox Exporter" "blackbox-exporter"

echo ""
echo -e "${BLUE}Blackbox Probes (frontend/ras):${NC}"
echo ""
if command -v curl &>/dev/null; then
    if curl -sS "http://localhost:9090/api/v1/query?query=max(probe_success%7Bcc1c_service%3D%22frontend%22%7D)" \
        | grep -q '"value":[^]]*"1"'; then
        echo -e "  Frontend probe: ${GREEN}✓ online${NC}"
    else
        echo -e "  Frontend probe: ${YELLOW}⚠️  offline${NC}"
        echo -e "    check: http://localhost:9115/probe?module=http_2xx&target=http://localhost:${FRONTEND_PORT}/"
    fi
    if curl -sS "http://localhost:9090/api/v1/query?query=max(probe_success%7Bcc1c_service%3D%22ras-server%22%7D)" \
        | grep -q '"value":[^]]*"1"'; then
        echo -e "  RAS probe: ${GREEN}✓ online${NC}"
    else
        echo -e "  RAS probe: ${YELLOW}⚠️  offline${NC}"
        echo -e "    check: http://localhost:9115/probe?module=tcp_connect&target=${RAS_SERVER_ADDR:-${RAS_SERVER:-172.24.80.1:1545}}"
    fi
else
    echo -e "  Frontend probe: ${YELLOW}⚠️  curl not found${NC}"
fi

echo ""
echo -e "${BLUE}Управление:${NC}"
echo -e "  Запустить все:    ${GREEN}./scripts/dev/start-all.sh${NC}"
echo -e "  Остановить все:   ${GREEN}./scripts/dev/stop-all.sh${NC}"
echo -e "  Перезапустить:    ${GREEN}./scripts/dev/restart.sh <service>${NC}"
echo -e "  Просмотр логов:   ${GREEN}./scripts/dev/logs.sh <service>${NC}"
echo ""
