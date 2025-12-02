#!/bin/bash

##############################################################################
# CommandCenter1C - Stop All Services
##############################################################################
# Останавливает все локально запущенные сервисы
##############################################################################

set -e

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$PROJECT_ROOT"

# Source unified library
source "$PROJECT_ROOT/scripts/lib/init.sh"

# Константы проекта
PIDS_DIR="$PROJECT_ROOT/pids"
LOGS_DIR="$PROJECT_ROOT/logs"

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

# 12. Frontend
stop_service "frontend"

# 11. Batch Service
stop_service "batch-service"

# 10. RAS Adapter (Week 4+ replaces cluster-service)
stop_service "ras-adapter"

# 8. RAS (1C Remote Administration Server)
# Если RAS_SKIP_START=true, значит RAS работает как Windows служба — не трогаем
if [ "${RAS_SKIP_START:-false}" == "true" ]; then
    echo -e "${CYAN}ℹ️  RAS: пропущен (работает как Windows служба)${NC}"
else
    echo -e "${BLUE}Остановка RAS (1C Remote Administration Server)...${NC}"
    if is_wsl; then
        # WSL: RAS запущен как Windows процесс, останавливаем через PowerShell
        if powershell.exe -Command "Get-Process ras -ErrorAction SilentlyContinue | Stop-Process -Force" 2>/dev/null; then
            echo -e "${GREEN}✓ RAS остановлен (Windows процесс)${NC}"
        else
            echo -e "${YELLOW}⚠️  RAS: процесс не найден или уже остановлен${NC}"
        fi
    else
        # Native Windows: используем стандартную остановку по PID
        stop_service "ras"
    fi
fi

# 7. Go Worker
stop_service "worker"

# 6. API Gateway
stop_service "api-gateway"

# 5.5 Flower (Celery UI)
stop_service "flower"

# 5. Celery Beat
stop_service "celery-beat"

# 4. Celery Worker
stop_service "celery-worker"

# 3. Django Orchestrator
stop_service "orchestrator"

echo ""

##############################################################################
# Остановка инфраструктуры (Docker или Native)
##############################################################################

# Загрузить переменные окружения для определения режима
if [ -f "$PROJECT_ROOT/.env.local" ]; then
    set -a
    source "$PROJECT_ROOT/.env.local"
    set +a
fi

if is_docker_mode; then
    echo -e "${BLUE}Остановка Docker сервисов (PostgreSQL, Redis, Prometheus, Grafana, Jaeger)...${NC}"

    # Единое имя проекта (должно совпадать с start-all.sh)
    COMPOSE_PROJECT="cc1c-local"

    # Собрать список compose файлов
    COMPOSE_FILES=""
    if [ -f "$PROJECT_ROOT/docker-compose.local.yml" ]; then
        COMPOSE_FILES="-f docker-compose.local.yml"
    fi
    if [ -f "$PROJECT_ROOT/docker-compose.local.monitoring.yml" ]; then
        COMPOSE_FILES="$COMPOSE_FILES -f docker-compose.local.monitoring.yml"
    fi

    if [ -n "$COMPOSE_FILES" ]; then
        docker compose -p "$COMPOSE_PROJECT" $COMPOSE_FILES down
        echo -e "${GREEN}✓ Docker сервисы остановлены${NC}"
    else
        echo -e "${YELLOW}⚠️  docker-compose файлы не найдены${NC}"
    fi
else
    echo -e "${BLUE}Проверка нативных сервисов (PostgreSQL, Redis, Prometheus, Grafana, Jaeger)...${NC}"

    # Остановка мониторинга (пропускает сервисы с автозапуском)
    stop_native_monitoring

    # Остановка инфраструктуры (пропускает сервисы с автозапуском)
    stop_native_infrastructure

    echo -e "${GREEN}✓ Нативные сервисы проверены (автозапуск сохранён)${NC}"
    echo -e "${CYAN}   Для принудительной остановки: ./scripts/dev/infrastructure.sh stop${NC}"
fi

echo ""

##############################################################################
# Очистка дополнительных процессов (на случай если PID файлы потеряны)
##############################################################################
echo -e "${BLUE}Проверка остаточных процессов...${NC}"

# Поиск процессов по портам (используем кросс-платформенную функцию из common-functions.sh)
check_and_kill_port() {
    local port=$1
    local service_name=$2

    # Используем кросс-платформенную функцию
    kill_process_on_port "$port" "$service_name" || true
}

check_and_kill_port 5173 "Frontend"
check_and_kill_port 8087 "Batch Service"
check_and_kill_port 8088 "RAS Adapter / Cluster Service"
# RAS - пропускаем если работает как Windows служба (RAS_SKIP_START=true)
if [ "${RAS_SKIP_START:-false}" != "true" ]; then
    RAS_CHECK_PORT="${RAS_PORT:-1539}"
    if check_port_listening "$RAS_CHECK_PORT"; then
        echo -e "${YELLOW}   Порт $RAS_CHECK_PORT (RAS) все еще занят, принудительная остановка...${NC}"
        if is_wsl; then
            powershell.exe -Command "Get-Process ras -ErrorAction SilentlyContinue | Stop-Process -Force" 2>/dev/null || true
        else
            check_and_kill_port "$RAS_CHECK_PORT" "RAS"
        fi
    fi
else
    echo -e "${CYAN}   RAS работает как Windows служба, пропускаем остановку${NC}"
fi
# Legacy порты (для очистки устаревших процессов)
check_and_kill_port 8080 "API Gateway (legacy)"
check_and_kill_port 8000 "Orchestrator (legacy)"
# Актуальные порты
check_and_kill_port 8180 "API Gateway"
check_and_kill_port 8200 "Orchestrator"

# Мониторинг (обычно не нужно, т.к. Docker контейнеры)
# check_and_kill_port 9090 "Prometheus"
# check_and_kill_port 3001 "Grafana"

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  ✓ Все сервисы остановлены!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo -e "${BLUE}Управление:${NC}"
echo -e "  Запустить все:         ${GREEN}./scripts/dev/start-all.sh${NC}"
echo -e "  Запустить мониторинг:  ${GREEN}./scripts/dev/start-monitoring.sh${NC}"
echo -e "  Проверить статус:      ${GREEN}./scripts/dev/health-check.sh${NC}"
echo ""
