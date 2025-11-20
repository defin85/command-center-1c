#!/bin/bash

##############################################################################
# CommandCenter1C - Start All Services Locally
##############################################################################
# Запускает все сервисы проекта локально на хост-машине
# - Docker: PostgreSQL, Redis, ClickHouse
# - 1C Platform: RAS (Remote Administration Server)
# - Python: Django Orchestrator, Celery Worker, Celery Beat
# - Go: API Gateway, Worker, ras-grpc-gw, cluster-service
# - Frontend: React dev server
##############################################################################

set -e

# Source common functions
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/common-functions.sh"

# Изменить рабочую директорию на PROJECT_ROOT
cd "$PROJECT_ROOT"

# Load environment variables from .env.local
load_env_file

# Флаги по умолчанию
FORCE_REBUILD=false
NO_REBUILD=false
PARALLEL_BUILD=false
VERBOSE=false

# Массивы для отчетности
declare -a REBUILD_SERVICES=()
declare -a SKIPPED_SERVICES=()

# Создать директории если нет
mkdir -p "$PIDS_DIR" "$LOGS_DIR"

##############################################################################
# HELP FUNCTION
##############################################################################

show_help() {
    echo -e "${BLUE}CommandCenter1C - Start All Services with Smart Rebuild${NC}"
    echo ""
    echo "Запускает все сервисы с автоматической пересборкой измененных Go сервисов."
    echo ""
    echo "Usage: $0 [OPTIONS]"
    echo ""
    echo "Options:"
    echo "  --help                   Показать эту справку"
    echo "  --force-rebuild          Принудительно пересобрать все Go сервисы"
    echo "  --no-rebuild             Пропустить проверку/пересборку"
    echo "  --parallel-build         Параллельная пересборка (быстрее)"
    echo "  --verbose                Детальный вывод для отладки"
    echo ""
    echo "Examples:"
    echo "  $0                           # Smart rebuild (по умолчанию)"
    echo "  $0 --force-rebuild           # Принудительная пересборка всех"
    echo "  $0 --no-rebuild              # Быстрый старт без пересборки"
    echo "  $0 --parallel-build          # Параллельная сборка"
    echo ""
}

##############################################################################
# ARGUMENT PARSING
##############################################################################

# Парсинг аргументов
while [[ $# -gt 0 ]]; do
    case $1 in
        --help)
            show_help
            exit 0
            ;;
        --force-rebuild)
            FORCE_REBUILD=true
            shift
            ;;
        --no-rebuild)
            NO_REBUILD=true
            shift
            ;;
        --parallel-build)
            PARALLEL_BUILD=true
            shift
            ;;
        --verbose)
            VERBOSE=true
            shift
            ;;
        *)
            echo -e "${RED}Неизвестный флаг: $1${NC}"
            show_help
            exit 1
            ;;
    esac
done

# Валидация конфликтующих флагов
if [ "$FORCE_REBUILD" = true ] && [ "$NO_REBUILD" = true ]; then
    echo -e "${RED}Ошибка: --force-rebuild и --no-rebuild несовместимы${NC}"
    exit 1
fi

##############################################################################
# MAIN EXECUTION
##############################################################################

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}  CommandCenter1C - Starting Services  ${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# Проверить .env файл
if [ ! -f "$PROJECT_ROOT/.env.local" ]; then
    echo -e "${YELLOW}⚠️  .env.local не найден, копирую из .env.example${NC}"
    cp "$PROJECT_ROOT/.env.example" "$PROJECT_ROOT/.env.local"
    echo -e "${GREEN}✓ Создан .env.local${NC}"
fi

# Загрузить переменные окружения (безопасно для путей с пробелами)
set -a
source "$PROJECT_ROOT/.env.local"
set +a

##############################################################################
# Phase 1: Smart Go Rebuild (NEW!)
##############################################################################
echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}  Phase 1: Проверка и пересборка Go сервисов${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

if ! smart_rebuild_services; then
    echo ""
    echo -e "${RED}✗ Ошибка при пересборке Go сервисов${NC}"
    echo -e "${YELLOW}Совет: Проверьте логи сборки выше${NC}"
    exit 1
fi

echo ""

##############################################################################
# Phase 2: Запуск Docker сервисов (PostgreSQL, Redis, ClickHouse)
##############################################################################
echo -e "${BLUE}[1/12] Запуск Docker сервисов...${NC}"

# Проверить docker-compose.local.yml
if [ ! -f "$PROJECT_ROOT/docker-compose.local.yml" ]; then
    echo -e "${YELLOW}⚠️  docker-compose.local.yml не найден${NC}"
    echo -e "${YELLOW}   Используйте docker-compose.local.yml для запуска ТОЛЬКО инфраструктурных сервисов${NC}"
    exit 1
fi

docker-compose -f docker-compose.local.yml up -d

# Ожидать готовности БД
echo -e "${YELLOW}   Ожидание готовности PostgreSQL...${NC}"
for i in {1..30}; do
    if docker-compose -f docker-compose.local.yml exec -T postgres pg_isready -U commandcenter &>/dev/null; then
        echo -e "${GREEN}✓ PostgreSQL готов${NC}"
        break
    fi
    if [ $i -eq 30 ]; then
        echo -e "${RED}✗ PostgreSQL не запустился${NC}"
        exit 1
    fi
    sleep 1
done

# Ожидать готовности Redis
echo -e "${YELLOW}   Ожидание готовности Redis...${NC}"
for i in {1..30}; do
    if docker-compose -f docker-compose.local.yml exec -T redis redis-cli ping &>/dev/null; then
        echo -e "${GREEN}✓ Redis готов${NC}"
        break
    fi
    if [ $i -eq 30 ]; then
        echo -e "${RED}✗ Redis не запустился${NC}"
        exit 1
    fi
    sleep 1
done

echo -e "${GREEN}✓ Docker infrastructure запущена (PostgreSQL, Redis)${NC}"

# Запуск мониторинга (Prometheus + Grafana)
echo -e "${YELLOW}   Запуск мониторинга (Prometheus, Grafana)...${NC}"

if [ ! -f "$PROJECT_ROOT/docker-compose.local.monitoring.yml" ]; then
    echo -e "${YELLOW}⚠️  docker-compose.local.monitoring.yml не найден, пропускаем мониторинг${NC}"
else
    # Проверить что Docker запущен
    if ! docker info > /dev/null 2>&1; then
        echo -e "${YELLOW}⚠️  Docker не запущен, пропускаем мониторинг${NC}"
    else
        # Проверить/создать сеть
        if ! docker network inspect cc1c-local-network > /dev/null 2>&1; then
            echo -e "${YELLOW}   Создание сети cc1c-local-network...${NC}"
            docker network create cc1c-local-network
        fi

        # Запустить мониторинг
        docker-compose -f docker-compose.local.monitoring.yml up -d

        # Подождать готовности
        sleep 3

        # Проверить Prometheus
        if curl -sf http://localhost:9090/-/healthy > /dev/null 2>&1; then
            echo -e "${GREEN}✓ Prometheus запущен (http://localhost:9090)${NC}"
        else
            echo -e "${YELLOW}⚠️  Prometheus может быть еще не готов${NC}"
        fi

        # Проверить Grafana
        if curl -sf http://localhost:3001/api/health > /dev/null 2>&1; then
            echo -e "${GREEN}✓ Grafana запущен (http://localhost:3001)${NC}"
        else
            echo -e "${YELLOW}⚠️  Grafana может быть еще не готов${NC}"
        fi
    fi
fi

echo ""

##############################################################################
# Шаг 2: Django Migrations
##############################################################################
echo -e "${BLUE}[2/12] Применение миграций Django...${NC}"

cd "$PROJECT_ROOT/orchestrator"

# Активировать виртуальное окружение если есть
if [ -d "venv" ]; then
    source venv/bin/activate 2>/dev/null || source venv/Scripts/activate 2>/dev/null
fi

python manage.py migrate --noinput
echo -e "${GREEN}✓ Миграции применены${NC}"
echo ""

##############################################################################
# Шаг 3: Django Orchestrator
##############################################################################
echo -e "${BLUE}[3/12] Запуск Django Orchestrator (port 8000)...${NC}"

cd "$PROJECT_ROOT/orchestrator"

# Активировать виртуальное окружение
if [ -d "venv" ]; then
    source venv/bin/activate 2>/dev/null || source venv/Scripts/activate 2>/dev/null
fi

# .env.local уже загружен в начале скрипта

nohup python manage.py runserver 0.0.0.0:8000 > "$LOGS_DIR/orchestrator.log" 2>&1 &
ORCHESTRATOR_PID=$!
echo $ORCHESTRATOR_PID > "$PIDS_DIR/orchestrator.pid"

sleep 3
if kill -0 $ORCHESTRATOR_PID 2>/dev/null; then
    echo -e "${GREEN}✓ Django Orchestrator запущен (PID: $ORCHESTRATOR_PID)${NC}"
else
    echo -e "${RED}✗ Не удалось запустить Django Orchestrator${NC}"
    cat "$LOGS_DIR/orchestrator.log"
    exit 1
fi
echo ""

##############################################################################
# Шаг 4: Celery Worker
##############################################################################
echo -e "${BLUE}[4/12] Запуск Celery Worker...${NC}"

cd "$PROJECT_ROOT/orchestrator"

# Активировать виртуальное окружение
if [ -d "venv" ]; then
    source venv/bin/activate 2>/dev/null || source venv/Scripts/activate 2>/dev/null
fi

# NOTE: Using gevent pool for async I/O operations (Windows compatible)
# - prefork causes ACCESS_VIOLATION on Windows (spawn process issues)
# - gevent provides lightweight concurrency via green threads (cooperative)
# - Ideal for I/O-bound tasks: DB queries, Redis operations, HTTP calls
# - Concurrency 100 = up to 100 concurrent greenlets (minimal memory overhead)
# - Using -P instead of --pool (short form required by Celery 5.x)
nohup celery -A config worker -P gevent --concurrency=100 --loglevel=info > "$LOGS_DIR/celery-worker.log" 2>&1 &
CELERY_WORKER_PID=$!
echo $CELERY_WORKER_PID > "$PIDS_DIR/celery-worker.pid"

sleep 3
if kill -0 $CELERY_WORKER_PID 2>/dev/null; then
    echo -e "${GREEN}✓ Celery Worker запущен (PID: $CELERY_WORKER_PID)${NC}"
else
    echo -e "${RED}✗ Не удалось запустить Celery Worker${NC}"
    cat "$LOGS_DIR/celery-worker.log"
    exit 1
fi
echo ""

##############################################################################
# Шаг 5: Celery Beat
##############################################################################
echo -e "${BLUE}[5/12] Запуск Celery Beat...${NC}"

cd "$PROJECT_ROOT/orchestrator"

# Активировать виртуальное окружение
if [ -d "venv" ]; then
    source venv/bin/activate 2>/dev/null || source venv/Scripts/activate 2>/dev/null
fi

# Удалить старый celerybeat-schedule файл
rm -f celerybeat-schedule celerybeat-schedule.db

nohup celery -A config beat --loglevel=info > "$LOGS_DIR/celery-beat.log" 2>&1 &
CELERY_BEAT_PID=$!
echo $CELERY_BEAT_PID > "$PIDS_DIR/celery-beat.pid"

sleep 2
if kill -0 $CELERY_BEAT_PID 2>/dev/null; then
    echo -e "${GREEN}✓ Celery Beat запущен (PID: $CELERY_BEAT_PID)${NC}"
else
    echo -e "${RED}✗ Не удалось запустить Celery Beat${NC}"
    cat "$LOGS_DIR/celery-beat.log"
    exit 1
fi
echo ""

##############################################################################
##############################################################################
# Шаг 6: API Gateway (Go)
##############################################################################
echo -e "${BLUE}[6/12] Запуск API Gateway (port 8080)...${NC}"

# Бинарник гарантированно существует и актуален после Phase 1
BINARY_PATH="$BIN_DIR/cc1c-api-gateway.exe"

# .env.local уже загружен в начале скрипта

nohup "$BINARY_PATH" > "$LOGS_DIR/api-gateway.log" 2>&1 &
API_GATEWAY_PID=$!
echo $API_GATEWAY_PID > "$PIDS_DIR/api-gateway.pid"

sleep 3
if kill -0 $API_GATEWAY_PID 2>/dev/null; then
    echo -e "${GREEN}✓ API Gateway запущен (PID: $API_GATEWAY_PID)${NC}"
else
    echo -e "${RED}✗ Не удалось запустить API Gateway${NC}"
    cat "$LOGS_DIR/api-gateway.log"
    exit 1
fi
echo ""

##############################################################################
# Шаг 7: Go Worker
##############################################################################
echo -e "${BLUE}[7/12] Запуск Go Worker...${NC}"

# Бинарник гарантированно существует и актуален после Phase 1
BINARY_PATH="$BIN_DIR/cc1c-worker.exe"

# .env.local уже загружен в начале скрипта

nohup "$BINARY_PATH" > "$LOGS_DIR/worker.log" 2>&1 &
WORKER_PID=$!
echo $WORKER_PID > "$PIDS_DIR/worker.pid"

sleep 2
if kill -0 $WORKER_PID 2>/dev/null; then
    echo -e "${GREEN}✓ Go Worker запущен (PID: $WORKER_PID)${NC}"
else
    echo -e "${RED}✗ Не удалось запустить Go Worker${NC}"
    cat "$LOGS_DIR/worker.log"
    exit 1
fi
echo ""

# Шаг 8: RAS (1C Remote Administration Server)
##############################################################################
echo -e "${BLUE}[8/12] Запуск RAS (1C Remote Administration Server, port ${RAS_PORT:-1545})...${NC}"

# Проверить что PLATFORM_1C_BIN_PATH задан
if [ -z "$PLATFORM_1C_BIN_PATH" ]; then
    echo -e "${YELLOW}⚠️  PLATFORM_1C_BIN_PATH не задан в .env.local${NC}"
    echo -e "${YELLOW}   RAS не будет запущен. Установите путь к платформе 1С:${NC}"
    echo -e "${YELLOW}   PLATFORM_1C_BIN_PATH=C:\\Program Files\\1cv8\\8.3.27.1786\\bin${NC}"
    echo -e "${YELLOW}   Продолжаю без RAS...${NC}"
else
    RAS_EXE="$PLATFORM_1C_BIN_PATH/ras.exe"

    # Проверить что ras.exe существует
    if [ ! -f "$RAS_EXE" ]; then
        echo -e "${YELLOW}⚠️  ras.exe не найден: $RAS_EXE${NC}"
        echo -e "${YELLOW}   Продолжаю без RAS...${NC}"
    else
        # Проверить что RAS еще не запущен
        if netstat -ano 2>/dev/null | grep -q ":${RAS_PORT:-1545}.*LISTENING" || lsof -i ":${RAS_PORT:-1545}" >/dev/null 2>&1; then
            echo -e "${YELLOW}⚠️  Порт ${RAS_PORT:-1545} уже занят (RAS уже запущен?)${NC}"
            echo -e "${GREEN}✓ Используется существующий процесс RAS${NC}"
        else
            # Запустить RAS
            nohup "$RAS_EXE" cluster --port=${RAS_PORT:-1545} > "$LOGS_DIR/ras.log" 2>&1 &
            RAS_PID=$!
            echo $RAS_PID > "$PIDS_DIR/ras.pid"

            sleep 3
            if kill -0 $RAS_PID 2>/dev/null; then
                echo -e "${GREEN}✓ RAS запущен (PID: $RAS_PID, port: ${RAS_PORT:-1545})${NC}"
            else
                echo -e "${RED}✗ Не удалось запустить RAS${NC}"
                cat "$LOGS_DIR/ras.log"
                echo -e "${YELLOW}   Продолжаю без RAS...${NC}"
            fi
        fi
    fi
fi
echo ""

# Шаг 9: ras-grpc-gw (Go)
##############################################################################
echo -e "${BLUE}[9/12] Запуск ras-grpc-gw (port 9999)...${NC}"

# Проверить что директория ras-grpc-gw существует
RAS_GW_DIR="/c/1CProject/ras-grpc-gw"
if [ ! -d "$RAS_GW_DIR" ]; then
    echo -e "${RED}✗ Директория ras-grpc-gw не найдена: $RAS_GW_DIR${NC}"
    echo -e "${YELLOW}   Это форк проекта, должен быть в C:/1CProject/ras-grpc-gw${NC}"
    exit 1
fi

cd "$RAS_GW_DIR"

# .env.local уже загружен в начале скрипта

# Проверить наличие бинарника
BINARY_PATH="$RAS_GW_DIR/bin/ras-grpc-gw.exe"
if [ -f "$BINARY_PATH" ]; then
    echo -e "${YELLOW}   Используется собранный бинарник: bin/ras-grpc-gw.exe${NC}"
    nohup "$BINARY_PATH" --bind 0.0.0.0:9999 --health 0.0.0.0:8081 localhost:1545 > "$LOGS_DIR/ras-grpc-gw.log" 2>&1 &
else
    echo -e "${YELLOW}   Бинарник не найден, используется 'go run'${NC}"
    echo -e "${YELLOW}   Совет: Запустите 'make build' в $RAS_GW_DIR для компиляции${NC}"
    nohup go run cmd/main.go --bind 0.0.0.0:9999 --health 0.0.0.0:8081 localhost:1545 > "$LOGS_DIR/ras-grpc-gw.log" 2>&1 &
fi
RAS_GW_PID=$!
echo $RAS_GW_PID > "$PIDS_DIR/ras-grpc-gw.pid"

sleep 3
if kill -0 $RAS_GW_PID 2>/dev/null; then
    echo -e "${GREEN}✓ ras-grpc-gw запущен (PID: $RAS_GW_PID)${NC}"
else
    echo -e "${RED}✗ Не удалось запустить ras-grpc-gw${NC}"
    cat "$LOGS_DIR/ras-grpc-gw.log"
    exit 1
fi
echo ""

##############################################################################
##############################################################################
# Шаг 10: Cluster Service (Go)
##############################################################################
echo -e "${BLUE}[10/12] Запуск Cluster Service (port 8088)...${NC}"

# Бинарник гарантированно существует и актуален после Phase 1
BINARY_PATH="$BIN_DIR/cc1c-cluster-service.exe"

# .env.local уже загружен в начале скрипта

# Переопределить порт для cluster-service (default 8088, не 8080 из .env.local)
export SERVER_PORT=8088

nohup "$BINARY_PATH" > "$LOGS_DIR/cluster-service.log" 2>&1 &
CLUSTER_SERVICE_PID=$!
echo $CLUSTER_SERVICE_PID > "$PIDS_DIR/cluster-service.pid"

sleep 2
if kill -0 $CLUSTER_SERVICE_PID 2>/dev/null; then
    echo -e "${GREEN}✓ Cluster Service запущен (PID: $CLUSTER_SERVICE_PID)${NC}"
else
    echo -e "${RED}✗ Не удалось запустить Cluster Service${NC}"
    cat "$LOGS_DIR/cluster-service.log"
    exit 1
fi
echo ""

##############################################################################
# Шаг 11: Batch Service (Go)
##############################################################################
echo -e "${BLUE}[11/12] Запуск Batch Service (port 8087)...${NC}"

# Бинарник гарантированно существует и актуален после Phase 1
BINARY_PATH="$BIN_DIR/cc1c-batch-service.exe"

# .env.local уже загружен в начале скрипта

# Переопределить порт для batch-service (default 8087, не 8080 из .env.local)
export SERVER_PORT=8087

nohup "$BINARY_PATH" > "$LOGS_DIR/batch-service.log" 2>&1 &
BATCH_SERVICE_PID=$!
echo $BATCH_SERVICE_PID > "$PIDS_DIR/batch-service.pid"

sleep 2
if kill -0 $BATCH_SERVICE_PID 2>/dev/null; then
    echo -e "${GREEN}✓ Batch Service запущен (PID: $BATCH_SERVICE_PID)${NC}"
else
    echo -e "${RED}✗ Не удалось запустить Batch Service${NC}"
    cat "$LOGS_DIR/batch-service.log"
    exit 1
fi
echo ""

# Шаг 12: Frontend (React)
##############################################################################
echo -e "${BLUE}[12/12] Запуск Frontend (port 5173)...${NC}"

cd "$PROJECT_ROOT/frontend"

# Проверить node_modules
if [ ! -d "node_modules" ]; then
    echo -e "${YELLOW}   Установка npm зависимостей...${NC}"
    npm install
fi

# .env.local уже загружен в начале скрипта

nohup npm run dev > "$LOGS_DIR/frontend.log" 2>&1 &
FRONTEND_PID=$!
echo $FRONTEND_PID > "$PIDS_DIR/frontend.pid"

sleep 5
if kill -0 $FRONTEND_PID 2>/dev/null; then
    echo -e "${GREEN}✓ Frontend запущен (PID: $FRONTEND_PID)${NC}"
else
    echo -e "${RED}✗ Не удалось запустить Frontend${NC}"
    cat "$LOGS_DIR/frontend.log"
    exit 1
fi
echo ""

##############################################################################
# Summary Report
##############################################################################
echo ""
echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}  Итоговая сводка${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# Показать статус пересборки
if [ ${#REBUILD_SERVICES[@]} -gt 0 ]; then
    echo -e "${BLUE}Пересобранные Go сервисы (${#REBUILD_SERVICES[@]}):${NC}"
    for service in "${REBUILD_SERVICES[@]}"; do
        echo -e "  ${GREEN}✓${NC} $service"
    done
    echo ""
fi

if [ ${#SKIPPED_SERVICES[@]} -gt 0 ]; then
    echo -e "${BLUE}Пропущенные Go сервисы (${#SKIPPED_SERVICES[@]}):${NC}"
    for service in "${SKIPPED_SERVICES[@]}"; do
        echo -e "  ${BLUE}ℹ${NC} $service (бинарник актуален)"
    done
    echo ""
fi

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  ✓ Все сервисы успешно запущены!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo -e "${BLUE}Доступные endpoints:${NC}"
echo -e "  Frontend:         ${GREEN}http://localhost:5173${NC}"
echo -e "  API Gateway:      ${GREEN}http://localhost:8080/health${NC}"
echo -e "  Orchestrator:"
echo -e "    Admin Panel:    ${GREEN}http://localhost:8000/admin${NC}"
echo -e "    API Docs:       ${GREEN}http://localhost:8000/api/docs${NC}"
echo -e "  Cluster Service:  ${GREEN}http://localhost:8088/health${NC}"
echo -e "  Batch Service:    ${GREEN}http://localhost:8087/health${NC}"
echo -e "  ras-grpc-gw:      ${GREEN}http://localhost:8081/health${NC} (gRPC: 9999)"
echo ""
echo -e "${BLUE}Мониторинг:${NC}"
echo -e "  Prometheus:       ${GREEN}http://localhost:9090${NC}"
echo -e "  Grafana:          ${GREEN}http://localhost:3001${NC} (admin/admin)"
echo -e "  A/B Dashboard:    ${GREEN}http://localhost:3001/d/ab-testing-event-driven${NC}"
echo ""
echo -e "${BLUE}PID файлы:${NC} $PIDS_DIR/"
echo -e "${BLUE}Логи:${NC} $LOGS_DIR/"
echo ""
echo -e "${YELLOW}Управление:${NC}"
echo -e "  Просмотр логов:   ${GREEN}./scripts/dev/logs.sh <service>${NC}"
echo -e "  Остановка всех:   ${GREEN}./scripts/dev/stop-all.sh${NC}"
echo -e "  Перезапуск:       ${GREEN}./scripts/dev/restart.sh <service>${NC}"
echo -e "  Health check:     ${GREEN}./scripts/dev/health-check.sh${NC}"
echo ""
