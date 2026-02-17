#!/bin/bash

##############################################################################
# CommandCenter1C - Start All Services Locally
##############################################################################
# Запускает все сервисы проекта локально на хост-машине
# - Docker: PostgreSQL, Redis, ClickHouse
# - 1C Platform: RAS (Remote Administration Server)
# - Python: Django Orchestrator
# - Go: API Gateway, Worker, RAS Adapter
# - Frontend: React dev server
##############################################################################

set -e

# Source library
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/../lib/init.sh"

# Project-specific constants
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
GO_SERVICES_DIR="$PROJECT_ROOT/go-services"
BIN_DIR="$PROJECT_ROOT/bin"
PIDS_DIR="$PROJECT_ROOT/pids"
LOGS_DIR="$PROJECT_ROOT/logs"

# Список Go сервисов (в порядке приоритета)
GO_SERVICES=("api-gateway" "worker")

# Изменить рабочую директорию на PROJECT_ROOT
cd "$PROJECT_ROOT"

# Load environment variables from .env.local
load_env_file

# Generate Prometheus Blackbox targets from .env.local (single source of truth)
if [[ -x "$PROJECT_ROOT/scripts/dev/generate-blackbox-targets.sh" ]]; then
    if ! "$PROJECT_ROOT/scripts/dev/generate-blackbox-targets.sh" >/dev/null 2>&1; then
        echo -e "${YELLOW}⚠️  Не удалось сгенерировать blackbox targets (RAS probe может быть неактуален)${NC}"
    fi
fi

# Native mode: Prometheus reads /etc/*, so sync configs/targets on start (best-effort)
# If restart-all already did the sync, it exports CC1C_NATIVE_MONITORING_SYNC_DONE=1.
if is_native_mode && [[ -x "$PROJECT_ROOT/scripts/dev/sync-native-monitoring.sh" ]] && [[ "${CC1C_NATIVE_MONITORING_SYNC_DONE:-}" != "1" ]]; then
    "$PROJECT_ROOT/scripts/dev/sync-native-monitoring.sh" || true
fi

# Флаги по умолчанию
FORCE_REBUILD=false
NO_REBUILD=false
PARALLEL_BUILD=false
VERBOSE=false
RUN_MAKEMIGRATIONS=false

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
    echo "  --makemigrations         Создать миграции Django перед migrate"
    echo "  --verbose                Детальный вывод для отладки"
    echo ""
    echo "Examples:"
    echo "  $0                           # Smart rebuild (по умолчанию)"
    echo "  $0 --force-rebuild           # Принудительная пересборка всех"
    echo "  $0 --no-rebuild              # Быстрый старт без пересборки"
    echo "  $0 --parallel-build          # Параллельная сборка"
    echo "  $0 --makemigrations          # Создать миграции перед запуском"
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
        --makemigrations)
            RUN_MAKEMIGRATIONS=true
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

# Sync frontend/.env.local for standalone runs (keeps VITE_* consistent)
# Do this before loading frontend env to auto-heal malformed files.
if [[ -x "$PROJECT_ROOT/scripts/dev/sync-frontend-env.sh" ]]; then
    "$PROJECT_ROOT/scripts/dev/sync-frontend-env.sh" >/dev/null 2>&1 || true
fi

# Загрузить frontend env (доп. VITE_* переменные, например Jaeger)
if [ -f "$PROJECT_ROOT/frontend/.env.local" ]; then
    set -a
    if ! source <(
        tr -d '\000' < "$PROJECT_ROOT/frontend/.env.local" \
        | grep -a -v '^#' \
        | grep -a -v '^[[:space:]]*$' \
        | sed 's/\r$//'
    ); then
        echo -e "${YELLOW}⚠️  Не удалось загрузить frontend/.env.local, продолжаю без frontend overrides${NC}"
    fi
    set +a
fi

# Dev default: enable Go scheduler unless explicitly disabled in env.
if [[ -z "${ENABLE_GO_SCHEDULER:-}" ]]; then
    export ENABLE_GO_SCHEDULER=true
fi

# Прокинуть VITE_BASE_HOST из CC1C_BASE_HOST если он не задан
if [[ -n "${CC1C_BASE_HOST:-}" ]]; then
    if [[ -z "${VITE_BASE_HOST:-}" ]]; then
        export VITE_BASE_HOST="$CC1C_BASE_HOST"
    fi
    # Default: same-origin (dev via Vite proxy, prod via reverse proxy).
    # Keep VITE_API_URL / VITE_WS_HOST unset unless explicitly provided to enable prod-like mode.
fi

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
# Phase 1.5a: Generate Service Configuration from config/services.json
##############################################################################
echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}  Phase 1.5a: Генерация конфигурации сервисов${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

if [ -f "$PROJECT_ROOT/scripts/config/generate.sh" ]; then
    if ! "$PROJECT_ROOT/scripts/config/generate.sh" --mode local; then
        echo ""
        echo -e "${RED}✗ Ошибка при генерации конфигурации${NC}"
        echo -e "${YELLOW}Совет: Проверьте config/services.json${NC}"
        exit 1
    fi
    # Перезагрузить сгенерированные переменные, чтобы использовать их в этом запуске.
    generated_env="$PROJECT_ROOT/generated/.env.services"
    if [[ -f "$generated_env" ]]; then
        set -a
        # shellcheck source=/dev/null
        source <(grep -v '^#' "$generated_env" | grep -v '^[[:space:]]*$' | grep -v '^=' | sed 's/\r$//')
        set +a
    fi
else
    echo -e "${YELLOW}⚠️  Скрипт генерации не найден (scripts/config/generate.sh)${NC}"
    echo -e "${YELLOW}   Пропускаем генерацию конфигурации${NC}"
fi

echo ""

##############################################################################
# Phase 1.5b: Validate OpenAPI + Generate API Clients + Verify Generated Code
##############################################################################
echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}  Phase 1.5b: OpenAPI Validation & Generation${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# Step 1: Validate OpenAPI specifications
echo -e "${CYAN}   [1/3] Валидация OpenAPI спецификаций...${NC}"
if [ -f "$PROJECT_ROOT/contracts/scripts/validate-specs.sh" ]; then
    if ! "$PROJECT_ROOT/contracts/scripts/validate-specs.sh"; then
        echo ""
        echo -e "${RED}✗ OpenAPI спецификации невалидны${NC}"
        echo -e "${YELLOW}Совет: Проверьте YAML синтаксис и структуру в contracts/*/openapi.yaml${NC}"
        exit 1
    fi
else
    echo -e "${YELLOW}⚠️  Скрипт валидации не найден (contracts/scripts/validate-specs.sh)${NC}"
fi
echo ""

# Step 2: Generate API clients from OpenAPI specs
echo -e "${CYAN}   [2/3] Генерация API клиентов...${NC}"
if [ -f "$PROJECT_ROOT/contracts/scripts/generate-all.sh" ]; then
    if ! "$PROJECT_ROOT/contracts/scripts/generate-all.sh"; then
        echo ""
        echo -e "${RED}✗ Ошибка при генерации API клиентов${NC}"
        echo -e "${YELLOW}Совет: Проверьте OpenAPI спецификации в contracts/${NC}"
        exit 1
    fi
else
    echo -e "${YELLOW}⚠️  Скрипт генерации не найден (contracts/scripts/generate-all.sh)${NC}"
    echo -e "${YELLOW}   Пропускаем генерацию контрактов${NC}"
fi
echo ""

# Step 3: Verify generated code compiles
echo -e "${CYAN}   [3/3] Проверка сгенерированного кода...${NC}"
if [ -f "$PROJECT_ROOT/contracts/scripts/verify-generated-code.sh" ]; then
    # Use --quick mode during startup for faster feedback
    if ! "$PROJECT_ROOT/contracts/scripts/verify-generated-code.sh" --quick; then
        echo ""
        echo -e "${RED}✗ Сгенерированный код не компилируется${NC}"
        echo -e "${YELLOW}Совет: Запустите contracts/scripts/generate-all.sh --force${NC}"
        exit 1
    fi
else
    echo -e "${YELLOW}⚠️  Скрипт верификации не найден (contracts/scripts/verify-generated-code.sh)${NC}"
fi

# Phase 1.5c: Rebuild Go services again if OpenAPI generation touched Go sources
# (e.g., api-gateway proxy routes are generated from Django OpenAPI)
echo ""
echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}  Phase 1.5c: Пересборка Go сервисов после генерации${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

if ! smart_rebuild_services; then
    echo ""
    echo -e "${RED}✗ Ошибка при пересборке Go сервисов (после генерации)${NC}"
    echo -e "${YELLOW}Совет: Проверьте логи сборки выше${NC}"
    exit 1
fi

# После Phase 1.5c Go бинарники гарантированно актуальны - пропускаем rebuild в start_service
export SKIP_GO_REBUILD=true

echo ""

##############################################################################
# Phase 2: Запуск инфраструктуры (PostgreSQL, Redis) - Docker или Native
##############################################################################
if is_native_mode; then
    echo -e "${BLUE}[1/9] Проверка инфраструктуры (systemd)...${NC}"
else
    echo -e "${BLUE}[1/9] Запуск инфраструктуры...${NC}"
fi

# Определить режим запуска (Docker по умолчанию для обратной совместимости)
if is_docker_mode; then
    echo -e "${CYAN}   Режим: Docker${NC}"

    # Проверить docker-compose.local.yml
    if [ ! -f "$PROJECT_ROOT/docker-compose.local.yml" ]; then
        echo -e "${YELLOW}⚠️  docker-compose.local.yml не найден${NC}"
        echo -e "${YELLOW}   Используйте docker-compose.local.yml для запуска ТОЛЬКО инфраструктурных сервисов${NC}"
        exit 1
    fi

    # Единое имя проекта для всех compose файлов (избегает orphan containers warning)
    COMPOSE_PROJECT="cc1c-local"

    # Создать сеть если не существует (нужна для external: true в monitoring compose)
    if ! docker network inspect cc1c-local-network > /dev/null 2>&1; then
        docker network create cc1c-local-network > /dev/null 2>&1
    fi

    # Собрать список compose файлов для запуска
    COMPOSE_FILES="-f docker-compose.local.yml"
    if [ -f "$PROJECT_ROOT/docker-compose.local.monitoring.yml" ]; then
        COMPOSE_FILES="$COMPOSE_FILES -f docker-compose.local.monitoring.yml"
    fi

    docker compose -p "$COMPOSE_PROJECT" $COMPOSE_FILES up -d

    # Ожидать готовности БД
    echo -e "${YELLOW}   Ожидание готовности PostgreSQL...${NC}"
    for i in {1..30}; do
        if docker compose -p "$COMPOSE_PROJECT" -f docker-compose.local.yml exec -T postgres pg_isready -U commandcenter &>/dev/null; then
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
        if docker compose -p "$COMPOSE_PROJECT" -f docker-compose.local.yml exec -T redis redis-cli ping &>/dev/null; then
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

    # Проверка мониторинга (уже запущен выше вместе с infrastructure)
    if [ -f "$PROJECT_ROOT/docker-compose.local.monitoring.yml" ]; then
        echo -e "${CYAN}   Ожидание готовности мониторинга (Prometheus, Grafana, Jaeger)...${NC}"

        # Функция ожидания сервиса с retry
        wait_for_monitoring_service() {
            local name=$1
            local url=$2
            local max_attempts=${3:-10}
            local attempt=1

            while [ $attempt -le $max_attempts ]; do
                # --noproxy '*' важен для WSL где может быть настроен proxy
                if curl --noproxy '*' -sf "$url" > /dev/null 2>&1; then
                    return 0
                fi
                sleep 1
                attempt=$((attempt + 1))
            done
            return 1
        }

        # Проверить Prometheus (до 10 секунд)
        if wait_for_monitoring_service "Prometheus" "http://localhost:9090/-/healthy" 10; then
            echo -e "${GREEN}✓ Prometheus запущен (http://localhost:9090)${NC}"
        else
            echo -e "${YELLOW}⚠️  Prometheus не отвечает (проверьте docker logs prometheus)${NC}"
        fi

        # Проверить Grafana (до 15 секунд - стартует дольше)
        if wait_for_monitoring_service "Grafana" "http://localhost:5000/api/health" 15; then
            echo -e "${GREEN}✓ Grafana запущен (http://localhost:5000)${NC}"
        else
            echo -e "${YELLOW}⚠️  Grafana не отвечает (это не критично)${NC}"
        fi

        # Проверить Jaeger (до 10 секунд)
        if wait_for_monitoring_service "Jaeger" "http://localhost:16686/" 10; then
            echo -e "${GREEN}✓ Jaeger запущен (http://localhost:16686)${NC}"
        else
            echo -e "${YELLOW}⚠️  Jaeger не отвечает (это не критично)${NC}"
        fi
    fi
else
    # Native mode - использует systemd сервисы
    echo -e "${CYAN}   Режим: Native (systemd)${NC}"

    # Проверка/запуск нативной инфраструктуры (PostgreSQL, Redis через systemd)
    # Если сервисы в автозапуске - только проверяет статус
    if ! start_native_infrastructure; then
        echo -e "${RED}✗ Ошибка проверки нативной инфраструктуры${NC}"
        echo -e "${YELLOW}Совет: Проверьте что PostgreSQL и Redis установлены:${NC}"
        echo -e "${YELLOW}  pacman -S postgresql redis${NC}"
        echo -e "${YELLOW}  sudo systemctl enable postgresql redis${NC}"
        exit 1
    fi

    # Проверка/запуск мониторинга (опционально)
    # Если сервисы в автозапуске - только проверяет статус
    echo -e "${CYAN}   Проверка нативного мониторинга...${NC}"
    if ! start_native_monitoring; then
        echo -e "${YELLOW}⚠️  Мониторинг не полностью готов (это не критично)${NC}"
    fi
fi

echo ""

##############################################################################
# Шаг 2: Django Migrations
##############################################################################
echo -e "${BLUE}[2/9] Применение миграций Django...${NC}"

cd "$PROJECT_ROOT/orchestrator"

# Активировать виртуальное окружение если есть
if [ -d "venv" ]; then
    activate_venv "$(pwd)/venv"
fi

if ! python manage.py makemigrations --check --dry-run >/dev/null 2>&1; then
    if [[ "$RUN_MAKEMIGRATIONS" == "true" ]]; then
        echo -e "${CYAN}   Есть изменения моделей — создаю миграции...${NC}"
        python manage.py makemigrations
    else
        echo -e "${RED}✗ Есть изменения моделей без миграций${NC}"
        echo -e "${YELLOW}Запусти: python manage.py makemigrations${NC}"
        echo -e "${YELLOW}Или повтори с флагом: $0 --makemigrations${NC}"
        exit 1
    fi
fi

python manage.py migrate --noinput
echo -e "${GREEN}✓ Миграции применены${NC}"

# Создание superuser если не существует
echo -e "${CYAN}   Проверка superuser...${NC}"
DJANGO_SUPERUSER_USERNAME="${DJANGO_SUPERUSER_USERNAME:-admin}"
DJANGO_SUPERUSER_EMAIL="${DJANGO_SUPERUSER_EMAIL:-admin@localhost}"
DJANGO_SUPERUSER_PASSWORD="${DJANGO_SUPERUSER_PASSWORD:-p-123456}"

# Проверяем существование пользователя и создаем если нет
if python manage.py shell -c "from django.contrib.auth import get_user_model; User = get_user_model(); exit(0 if User.objects.filter(username='$DJANGO_SUPERUSER_USERNAME').exists() else 1)" 2>/dev/null; then
    echo -e "${GREEN}✓ Superuser '$DJANGO_SUPERUSER_USERNAME' уже существует${NC}"
else
    echo -e "${CYAN}   Создание superuser '$DJANGO_SUPERUSER_USERNAME'...${NC}"
    DJANGO_SUPERUSER_PASSWORD="$DJANGO_SUPERUSER_PASSWORD" python manage.py createsuperuser --noinput --username "$DJANGO_SUPERUSER_USERNAME" --email "$DJANGO_SUPERUSER_EMAIL" 2>/dev/null
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✓ Superuser '$DJANGO_SUPERUSER_USERNAME' создан (пароль: $DJANGO_SUPERUSER_PASSWORD)${NC}"
    else
        echo -e "${YELLOW}⚠️  Не удалось создать superuser (возможно, уже существует)${NC}"
    fi
fi

# Собрать статические файлы (требуется для Daphne/ASGI с whitenoise)
echo -e "${CYAN}   Сборка статических файлов...${NC}"
manifest_file="$PROJECT_ROOT/orchestrator/staticfiles/staticfiles.json"
if [[ -f "$manifest_file" && ! -s "$manifest_file" ]]; then
    echo -e "${YELLOW}⚠️  Найден пустой staticfiles manifest, удаляю перед collectstatic...${NC}"
    rm -f "$manifest_file"
fi
if ! python manage.py collectstatic --noinput -v 0; then
    if [[ -f "$manifest_file" ]]; then
        echo -e "${YELLOW}⚠️  collectstatic не прошел, удаляю поврежденный manifest и пробую повторно...${NC}"
        rm -f "$manifest_file"
        python manage.py collectstatic --noinput -v 0
    else
        exit 1
    fi
fi
echo -e "${GREEN}✓ Статика собрана${NC}"
echo ""

##############################################################################
# Шаг 3: Django Orchestrator
##############################################################################
# Port 8200 - outside Windows reserved ranges (7913-8012, 8013-8112)
ORCHESTRATOR_PORT="${ORCHESTRATOR_PORT:-8200}"
echo -e "${BLUE}[3/9] Запуск Django Orchestrator (port $ORCHESTRATOR_PORT)...${NC}"

cd "$PROJECT_ROOT/orchestrator"

# Активировать виртуальное окружение
if [ -d "venv" ]; then
    activate_venv "$(pwd)/venv"
fi

# .env.local уже загружен в начале скрипта

# Используем Daphne (ASGI) вместо runserver для поддержки WebSocket
# Daphne поддерживает HTTP + WebSocket через единый порт
nohup daphne -b 0.0.0.0 -p $ORCHESTRATOR_PORT config.asgi:application > "$LOGS_DIR/orchestrator.log" 2>&1 &
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
# Шаг 4: Event Subscriber (Redis Streams consumer)
##############################################################################
echo -e "${BLUE}[4/9] Запуск Event Subscriber...${NC}"

if ! start_service "event-subscriber"; then
    log_error "Не удалось запустить event-subscriber"
    cat "$LOGS_DIR/event-subscriber.log"
    exit 1
fi
echo ""

##############################################################################
# Шаг 5: API Gateway (Go)
##############################################################################
echo -e "${BLUE}[5/9] Запуск API Gateway (port 8180)...${NC}"

if ! start_service "api-gateway"; then
    log_error "Не удалось запустить api-gateway"
    cat "$LOGS_DIR/api-gateway.log"
    exit 1
fi
echo ""

##############################################################################
# Шаг 6: Go Workers (ops + workflows)
##############################################################################
echo -e "${BLUE}[6/9] Запуск Go Workers (ops + workflows)...${NC}"

if ! start_service "worker"; then
    log_error "Не удалось запустить worker"
    cat "$LOGS_DIR/worker.log"
    exit 1
fi

if ! start_service "worker-workflows"; then
    log_error "Не удалось запустить worker-workflows"
    cat "$LOGS_DIR/worker-workflows.log"
    exit 1
fi
echo ""

# Шаг 7: RAS (1C Remote Administration Server)
##############################################################################
echo -e "${BLUE}[7/9] Запуск RAS (1C Remote Administration Server, port ${RAS_PORT:-1545})...${NC}"

# Проверить флаг пропуска запуска RAS (если RAS работает как Windows служба)
if [ "${RAS_SKIP_START:-false}" = "true" ]; then
    echo -e "${GREEN}✓ RAS запущен как Windows служба (RAS_SKIP_START=true)${NC}"
    echo -e "${CYAN}   Используется внешний RAS на порту ${RAS_PORT:-1545}${NC}"
    echo ""

# Проверить что RAS еще не запущен
elif check_port_listening "${RAS_PORT:-1545}"; then
    echo -e "${YELLOW}⚠️  Порт ${RAS_PORT:-1545} уже занят (RAS уже запущен?)${NC}"
    echo -e "${GREEN}✓ Используется существующий процесс RAS${NC}"
else
    # Определяем порт ragent (1C Server Agent)
    RAGENT_PORT="${RAGENT_PORT:-1540}"
    RAGENT_HOST="${RAGENT_HOST:-localhost}"
    # Проверить что ragent доступен (порт 1540)
    if ! check_port_listening "$RAGENT_PORT"; then
        echo -e "${YELLOW}⚠️  1C Server Agent (ragent) не найден на порту $RAGENT_PORT${NC}"
        echo -e "${YELLOW}   Убедитесь, что служба 'Агент сервера 1С:Предприятия' запущена${NC}"
        echo -e "${YELLOW}   Продолжаю без RAS...${NC}"
    elif [ -z "$PLATFORM_1C_BIN_PATH" ]; then
        echo -e "${YELLOW}⚠️  PLATFORM_1C_BIN_PATH не задан в .env.local${NC}"
        echo -e "${YELLOW}   RAS не будет запущен. Установите путь к платформе 1С:${NC}"
        if is_wsl; then
            echo -e "${YELLOW}   PLATFORM_1C_BIN_PATH=\"/mnt/c/Program Files/1cv8/8.3.27.1786/bin\"${NC}"
        else
            echo -e "${YELLOW}   PLATFORM_1C_BIN_PATH=\"C:\\Program Files\\1cv8\\8.3.27.1786\\bin\"${NC}"
        fi
        echo -e "${YELLOW}   Продолжаю без RAS...${NC}"
    else
        # Определяем путь к ras.exe в зависимости от платформы
        if is_wsl; then
            # WSL: конвертируем путь и запускаем через PowerShell
            if [[ "$PLATFORM_1C_BIN_PATH" == /mnt/* ]]; then
                # WSL путь типа /mnt/c/Program Files/... -> C:\Program Files\...
                WIN_DRIVE=$(echo "$PLATFORM_1C_BIN_PATH" | sed 's|/mnt/\([a-z]\)/|\U\1:\\|' | sed 's|/|\\|g')
                RAS_WIN_PATH="${WIN_DRIVE}\\ras.exe"
            else
                RAS_WIN_PATH="${PLATFORM_1C_BIN_PATH}\\ras.exe"
            fi
            RAS_EXE="$PLATFORM_1C_BIN_PATH/ras.exe"
        else
            # Native Windows (Git Bash / MSYS2): используем путь напрямую
            RAS_EXE="$PLATFORM_1C_BIN_PATH/ras.exe"
            RAS_WIN_PATH="$PLATFORM_1C_BIN_PATH\\ras.exe"
        fi

        # Проверить что ras.exe существует
        if [ ! -f "$RAS_EXE" ]; then
            echo -e "${YELLOW}⚠️  ras.exe не найден: $RAS_EXE${NC}"
            echo -e "${YELLOW}   Продолжаю без RAS...${NC}"
        else
            # RAS в режиме cluster подключается к ragent и предоставляет API на порту 1545
            echo -e "${CYAN}   Запуск: ras.exe cluster --port=${RAS_PORT:-1545} ${RAGENT_HOST}:${RAGENT_PORT}${NC}"

            if is_wsl; then
                # WSL: запуск через PowerShell (создает Windows процесс)
                powershell.exe -Command "Start-Process -FilePath '$RAS_WIN_PATH' -ArgumentList 'cluster','--port=${RAS_PORT:-1545}','${RAGENT_HOST}:${RAGENT_PORT}' -WindowStyle Hidden" > "$LOGS_DIR/ras.log" 2>&1
            else
                # Native Windows: запуск напрямую в фоне
                nohup "$RAS_EXE" cluster --port=${RAS_PORT:-1545} ${RAGENT_HOST}:${RAGENT_PORT} > "$LOGS_DIR/ras.log" 2>&1 &
                RAS_PID=$!
                echo $RAS_PID > "$PIDS_DIR/ras.pid"
            fi

            # Ждем запуска RAS
            sleep 3

            if check_port_listening "${RAS_PORT:-1545}"; then
                echo -e "${GREEN}✓ RAS запущен (port: ${RAS_PORT:-1545}, ragent: ${RAGENT_HOST}:${RAGENT_PORT})${NC}"
            else
                echo -e "${RED}✗ Не удалось запустить RAS${NC}"
                echo -e "${YELLOW}   Проверьте логи: $LOGS_DIR/ras.log${NC}"
                cat "$LOGS_DIR/ras.log" 2>/dev/null || true
                echo -e "${YELLOW}   Продолжаю без RAS...${NC}"
            fi
        fi
    fi
fi
echo ""

##############################################################################
# Шаг 8: Frontend (React)
##############################################################################
echo -e "${BLUE}[8/8] Запуск Frontend (port ${FRONTEND_PORT:-15173})...${NC}"

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
echo -e "  Frontend:         ${GREEN}http://localhost:${FRONTEND_PORT:-15173}${NC} (admin / p-123456)"
echo -e "  API Gateway:      ${GREEN}http://localhost:${SERVER_PORT:-8180}/health${NC}"
echo -e "  Orchestrator:"
echo -e "    Admin Panel:    ${GREEN}http://localhost:${ORCHESTRATOR_PORT:-8200}/admin${NC} (admin / p-123456)"
echo -e "    API Docs:       ${GREEN}http://localhost:${ORCHESTRATOR_PORT:-8200}/api/docs${NC}"
echo -e "  Worker (ops):     ${GREEN}http://localhost:${WORKER_PORT:-9191}/health${NC}"
echo -e "  Worker (flows):   ${GREEN}http://localhost:${WORKER_WORKFLOWS_METRICS_PORT:-9092}/health${NC}"
MINIO_ENDPOINT="${MINIO_ENDPOINT:-localhost:9000}"
MINIO_ENDPOINT="${MINIO_ENDPOINT#*://}"
echo -e "  MinIO:            ${GREEN}http://${MINIO_ENDPOINT}${NC}"
echo ""
echo -e "${BLUE}Мониторинг и Tracing:${NC}"

# Prometheus - проверяем реальный health endpoint
PROM_PORT="${PROMETHEUS_PORT:-9090}"
if curl --noproxy '*' -sf "http://localhost:${PROM_PORT}/-/healthy" &>/dev/null; then
    echo -e "  Prometheus:       ${GREEN}http://localhost:${PROM_PORT}${NC}"
else
    echo -e "  Prometheus:       ${YELLOW}не запущен${NC}"
fi

# Grafana - порт зависит от режима (Native: 3000, Docker: из конфига)
if is_docker_mode; then
    GRAFANA_DISPLAY_PORT="${GRAFANA_PORT:-5000}"
else
    GRAFANA_DISPLAY_PORT=3000  # Native systemd использует стандартный порт
fi
if curl --noproxy '*' -sf "http://localhost:${GRAFANA_DISPLAY_PORT}/api/health" &>/dev/null; then
    echo -e "  Grafana:          ${GREEN}http://localhost:${GRAFANA_DISPLAY_PORT}${NC} (admin / admin)"
else
    echo -e "  Grafana:          ${YELLOW}не запущен (порт ${GRAFANA_DISPLAY_PORT})${NC}"
fi

# Jaeger - проверяем реальный endpoint
JAEGER_DISPLAY_PORT="${JAEGER_PORT:-16686}"
if curl --noproxy '*' -sf "http://localhost:${JAEGER_DISPLAY_PORT}/" &>/dev/null; then
    echo -e "  Jaeger UI:        ${GREEN}http://localhost:${JAEGER_DISPLAY_PORT}${NC} (OpenTelemetry Tracing)"
else
    if is_docker_mode; then
        echo -e "  Jaeger UI:        ${YELLOW}не запущен${NC}"
    else
        echo -e "  Jaeger UI:        ${YELLOW}не установлен (yay -S jaeger)${NC}"
    fi
fi

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
