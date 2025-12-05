#!/bin/bash

##############################################################################
# CommandCenter1C - Stop All Services
##############################################################################
# Останавливает все локально запущенные сервисы
##############################################################################

set -e

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$PROJECT_ROOT"

# Source unified library (загружает lifecycle.sh с stop_service/stop_services)
source "$PROJECT_ROOT/scripts/lib/init.sh"
load_env_file

# Константы проекта
PIDS_DIR="$PROJECT_ROOT/pids"
LOGS_DIR="$PROJECT_ROOT/logs"

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}  CommandCenter1C - Stopping Services  ${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

##############################################################################
# Остановка всех сервисов (использует lifecycle.sh)
##############################################################################

# Остановка всех сервисов по SERVICE_STOP_ORDER
# (frontend, batch-service, ras-adapter, worker, api-gateway, flower, celery-beat, celery-worker, orchestrator)
stop_services

##############################################################################
# RAS - особая обработка для Windows службы
##############################################################################

if [ "${RAS_SKIP_START:-false}" == "true" ]; then
    echo -e "${CYAN}RAS: пропущен (работает как Windows служба)${NC}"
else
    echo -e "${BLUE}Остановка RAS (1C Remote Administration Server)...${NC}"
    if is_wsl; then
        # WSL: RAS запущен как Windows процесс, останавливаем через PowerShell
        if powershell.exe -Command "Get-Process ras -ErrorAction SilentlyContinue | Stop-Process -Force" 2>/dev/null; then
            echo -e "${GREEN}RAS остановлен (Windows процесс)${NC}"
        else
            echo -e "${YELLOW}RAS: процесс не найден или уже остановлен${NC}"
        fi
    else
        # Native Windows: используем стандартную остановку по PID
        stop_service "ras"
    fi
fi

echo ""

##############################################################################
# Остановка инфраструктуры (Docker или Native)
##############################################################################

if is_docker_mode; then
    echo -e "${BLUE}Остановка Docker сервисов (PostgreSQL, Redis, Prometheus, Grafana, Jaeger)...${NC}"

    COMPOSE_PROJECT="cc1c-local"
    COMPOSE_FILES=""

    if [ -f "$PROJECT_ROOT/docker-compose.local.yml" ]; then
        COMPOSE_FILES="-f docker-compose.local.yml"
    fi
    if [ -f "$PROJECT_ROOT/docker-compose.local.monitoring.yml" ]; then
        COMPOSE_FILES="$COMPOSE_FILES -f docker-compose.local.monitoring.yml"
    fi

    if [ -n "$COMPOSE_FILES" ]; then
        docker compose -p "$COMPOSE_PROJECT" $COMPOSE_FILES down
        echo -e "${GREEN}Docker сервисы остановлены${NC}"
    else
        echo -e "${YELLOW}docker-compose файлы не найдены${NC}"
    fi
else
    echo -e "${BLUE}Проверка нативных сервисов (PostgreSQL, Redis, Prometheus, Grafana, Jaeger)...${NC}"

    # Остановка мониторинга и инфраструктуры (пропускает сервисы с автозапуском)
    stop_native_monitoring
    stop_native_infrastructure

    echo -e "${GREEN}Нативные сервисы проверены (автозапуск сохранен)${NC}"
    echo -e "${CYAN}   Для принудительной остановки: ./scripts/dev/infrastructure.sh stop${NC}"
fi

echo ""

##############################################################################
# Очистка остаточных процессов по портам
##############################################################################

echo -e "${BLUE}Проверка остаточных процессов...${NC}"

# Очистка по портам (на случай если PID файлы потеряны)
kill_process_on_port 5173 "Frontend" || true
kill_process_on_port 8187 "Batch Service" || true
kill_process_on_port 8188 "RAS Adapter" || true

# RAS - пропускаем если работает как Windows служба
if [ "${RAS_SKIP_START:-false}" != "true" ]; then
    RAS_CHECK_PORT="${RAS_PORT:-1539}"
    if check_port_listening "$RAS_CHECK_PORT"; then
        echo -e "${YELLOW}   Порт $RAS_CHECK_PORT (RAS) все еще занят, принудительная остановка...${NC}"
        if is_wsl; then
            powershell.exe -Command "Get-Process ras -ErrorAction SilentlyContinue | Stop-Process -Force" 2>/dev/null || true
        else
            kill_process_on_port "$RAS_CHECK_PORT" "RAS" || true
        fi
    fi
else
    echo -e "${CYAN}   RAS работает как Windows служба, пропускаем остановку${NC}"
fi

# Legacy порты (для очистки устаревших процессов)
kill_process_on_port 8080 "API Gateway (legacy)" || true
kill_process_on_port 8000 "Orchestrator (legacy)" || true

# Актуальные порты
kill_process_on_port 8180 "API Gateway" || true
kill_process_on_port 8200 "Orchestrator" || true

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  Все сервисы остановлены!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo -e "${BLUE}Управление:${NC}"
echo -e "  Запустить все:         ${GREEN}./scripts/dev/start-all.sh${NC}"
echo -e "  Запустить мониторинг:  ${GREEN}./scripts/dev/start-monitoring.sh${NC}"
echo -e "  Проверить статус:      ${GREEN}./scripts/dev/health-check.sh${NC}"
echo ""
