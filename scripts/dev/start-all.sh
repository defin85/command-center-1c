#!/bin/bash

##############################################################################
# CommandCenter1C - Start All Services Locally
##############################################################################
# Запускает все сервисы проекта локально на хост-машине
# - Docker: PostgreSQL, Redis, ClickHouse
# - Python: Django Orchestrator, Celery Worker, Celery Beat
# - Go: API Gateway, Worker, ras-grpc-gw, cluster-service
# - Frontend: React dev server
##############################################################################

set -e

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$PROJECT_ROOT"

PIDS_DIR="$PROJECT_ROOT/pids"
LOGS_DIR="$PROJECT_ROOT/logs"

# Цвета для вывода
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Создать директории если нет
mkdir -p "$PIDS_DIR" "$LOGS_DIR"

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

# Загрузить переменные окружения
export $(grep -v '^#' "$PROJECT_ROOT/.env.local" | xargs)

##############################################################################
# Шаг 1: Запуск Docker сервисов (PostgreSQL, Redis, ClickHouse, ras-grpc-gw)
##############################################################################
echo -e "${BLUE}[1/9] Запуск Docker сервисов...${NC}"

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

echo -e "${GREEN}✓ Docker сервисы запущены${NC}"
echo ""

##############################################################################
# Шаг 2: Django Migrations
##############################################################################
echo -e "${BLUE}[2/9] Применение миграций Django...${NC}"

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
echo -e "${BLUE}[3/9] Запуск Django Orchestrator (port 8000)...${NC}"

cd "$PROJECT_ROOT/orchestrator"

# Активировать виртуальное окружение
if [ -d "venv" ]; then
    source venv/bin/activate 2>/dev/null || source venv/Scripts/activate 2>/dev/null
fi

# Загрузить .env.local
export $(grep -v '^#' "$PROJECT_ROOT/.env.local" | xargs)

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
echo -e "${BLUE}[4/9] Запуск Celery Worker...${NC}"

cd "$PROJECT_ROOT/orchestrator"

# Активировать виртуальное окружение
if [ -d "venv" ]; then
    source venv/bin/activate 2>/dev/null || source venv/Scripts/activate 2>/dev/null
fi

nohup celery -A config worker --loglevel=info > "$LOGS_DIR/celery-worker.log" 2>&1 &
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
echo -e "${BLUE}[5/9] Запуск Celery Beat...${NC}"

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
# Шаг 6: API Gateway (Go)
##############################################################################
echo -e "${BLUE}[6/9] Запуск API Gateway (port 8080)...${NC}"

cd "$PROJECT_ROOT/go-services/api-gateway"

# Загрузить .env.local
export $(grep -v '^#' "$PROJECT_ROOT/.env.local" | xargs)

nohup go run cmd/main.go > "$LOGS_DIR/api-gateway.log" 2>&1 &
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
echo -e "${BLUE}[7/9] Запуск Go Worker...${NC}"

cd "$PROJECT_ROOT/go-services/worker"

# Загрузить .env.local
export $(grep -v '^#' "$PROJECT_ROOT/.env.local" | xargs)

nohup go run cmd/main.go > "$LOGS_DIR/worker.log" 2>&1 &
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

##############################################################################
# Шаг 8: ras-grpc-gw (Go)
##############################################################################
echo -e "${BLUE}[8/10] Запуск ras-grpc-gw (port 9999)...${NC}"

# Проверить что директория ras-grpc-gw существует
RAS_GW_DIR="/c/1CProject/ras-grpc-gw"
if [ ! -d "$RAS_GW_DIR" ]; then
    echo -e "${RED}✗ Директория ras-grpc-gw не найдена: $RAS_GW_DIR${NC}"
    echo -e "${YELLOW}   Это форк проекта, должен быть в C:/1CProject/ras-grpc-gw${NC}"
    exit 1
fi

cd "$RAS_GW_DIR"

# Загрузить .env.local
export $(grep -v '^#' "$PROJECT_ROOT/.env.local" | xargs 2>/dev/null || true)

nohup go run main.go --bind 0.0.0.0:9999 --health 0.0.0.0:8081 localhost:1541 > "$LOGS_DIR/ras-grpc-gw.log" 2>&1 &
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
# Шаг 9: Cluster Service (Go)
##############################################################################
echo -e "${BLUE}[9/10] Запуск Cluster Service (port 8088)...${NC}"

cd "$PROJECT_ROOT/go-services/cluster-service"

# Загрузить .env.local
export $(grep -v '^#' "$PROJECT_ROOT/.env.local" | xargs)

nohup go run cmd/main.go > "$LOGS_DIR/cluster-service.log" 2>&1 &
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
# Шаг 10: Frontend (React)
##############################################################################
echo -e "${BLUE}[10/10] Запуск Frontend (port 3000)...${NC}"

cd "$PROJECT_ROOT/frontend"

# Проверить node_modules
if [ ! -d "node_modules" ]; then
    echo -e "${YELLOW}   Установка npm зависимостей...${NC}"
    npm install
fi

# Загрузить .env.local
export $(grep -v '^#' "$PROJECT_ROOT/.env.local" | xargs)

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
# Финальная сводка
##############################################################################
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  ✓ Все сервисы успешно запущены!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo -e "${BLUE}Доступные endpoints:${NC}"
echo -e "  Frontend:         ${GREEN}http://localhost:3000${NC}"
echo -e "  API Gateway:      ${GREEN}http://localhost:8080${NC}"
echo -e "  Orchestrator:     ${GREEN}http://localhost:8000${NC}"
echo -e "  Cluster Service:  ${GREEN}http://localhost:8088${NC}"
echo -e "  ras-grpc-gw:      ${GREEN}http://localhost:8081/health${NC} (gRPC: 9999)"
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
