#!/bin/bash

##############################################################################
# CommandCenter1C - Infrastructure Installation (PostgreSQL + Redis + MinIO + pgAdmin)
##############################################################################
#
# Установка и настройка PostgreSQL, Redis, MinIO и pgAdmin для локальной разработки.
# Использует библиотеки проекта для кросс-платформенной поддержки.
#
# Usage:
#   ./scripts/setup/install-infra.sh [OPTIONS]
#
# Options:
#   --only-postgres     Установить только PostgreSQL
#   --only-redis        Установить только Redis
#   --only-minio        Установить только MinIO
#   --only-pgadmin      Установить только pgAdmin
#   --skip-postgres     Пропустить установку PostgreSQL
#   --skip-redis        Пропустить установку Redis
#   --skip-minio        Пропустить установку MinIO
#   --skip-pgadmin      Пропустить установку pgAdmin
#   --dry-run           Показать план без изменений
#   --verbose, -v       Подробный вывод
#   --help, -h          Показать справку
#
# Environment Variables (from .env.local):
#   DB_USER       PostgreSQL user (default: commandcenter)
#   DB_PASSWORD   PostgreSQL password (default: commandcenter)
#   DB_NAME       PostgreSQL database (default: commandcenter)
#   DB_HOST       PostgreSQL host (default: localhost)
#   DB_PORT       PostgreSQL port (default: 5432)
#   REDIS_HOST    Redis host (default: localhost)
#   REDIS_PORT    Redis port (default: 6379)
#   MINIO_ENDPOINT      MinIO endpoint (default: localhost:9000)
#   MINIO_ACCESS_KEY    MinIO access key (default: minioadmin)
#   MINIO_SECRET_KEY    MinIO secret key (default: minioadmin)
#   MINIO_BUCKET        MinIO bucket (default: cc1c-artifacts)
#   MINIO_SECURE        MinIO secure flag (default: false)
#   MINIO_DATA_DIR      MinIO data dir (default: /var/lib/minio)
#   MINIO_ADDRESS       MinIO bind address (default: :9000)
#   MINIO_CONSOLE_ADDRESS MinIO console address (default: :9001)
#
# Examples:
#   ./scripts/setup/install-infra.sh                  # Полная установка
#   ./scripts/setup/install-infra.sh --dry-run        # Показать план
#   ./scripts/setup/install-infra.sh --only-postgres  # Только PostgreSQL
#   ./scripts/setup/install-infra.sh --only-minio     # Только MinIO
#   ./scripts/setup/install-infra.sh --skip-redis     # Без Redis
#   ./scripts/setup/install-infra.sh --skip-minio     # Без MinIO
#   ./scripts/setup/install-infra.sh --skip-pgadmin   # Без pgAdmin
#
# Version: 1.0.0
##############################################################################

set -e

# Версия скрипта
SCRIPT_VERSION="1.0.0"

# Директории
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

##############################################################################
# LIBRARY LOADING
##############################################################################

# Подключение единой библиотеки
if [[ -f "$PROJECT_ROOT/scripts/lib/init.sh" ]]; then
    source "$PROJECT_ROOT/scripts/lib/init.sh"
else
    echo "FATAL: scripts/lib/init.sh не найден в $PROJECT_ROOT" >&2
    exit 1
fi

# Подключение PostgreSQL helpers
if [[ -f "$SCRIPT_DIR/lib/postgres.sh" ]]; then
    source "$SCRIPT_DIR/lib/postgres.sh"
else
    log_error "scripts/setup/lib/postgres.sh не найден"
    exit 1
fi

##############################################################################
# DEFAULTS & CONFIGURATION
##############################################################################

# Загрузка переменных из .env.local (если существует)
ENV_LOCAL_FILE="$PROJECT_ROOT/.env.local"
if [[ -f "$ENV_LOCAL_FILE" ]]; then
    # Экспортируем переменные, игнорируя комментарии и пустые строки
    set -a
    while IFS= read -r line || [[ -n "$line" ]]; do
        # Пропускаем комментарии и пустые строки
        [[ -z "$line" || "$line" =~ ^[[:space:]]*# ]] && continue
        # Пропускаем строки без =
        [[ "$line" != *"="* ]] && continue
        # Экспортируем переменную
        eval "export $line" 2>/dev/null || true
    done < "$ENV_LOCAL_FILE"
    set +a
fi

# Значения по умолчанию
DB_USER="${DB_USER:-commandcenter}"
DB_PASSWORD="${DB_PASSWORD:-commandcenter}"
DB_NAME="${DB_NAME:-commandcenter}"
DB_HOST="${DB_HOST:-localhost}"
DB_PORT="${DB_PORT:-5432}"
REDIS_HOST="${REDIS_HOST:-localhost}"
REDIS_PORT="${REDIS_PORT:-6379}"
MINIO_ENDPOINT="${MINIO_ENDPOINT:-localhost:9000}"
MINIO_ACCESS_KEY="${MINIO_ACCESS_KEY:-minioadmin}"
MINIO_SECRET_KEY="${MINIO_SECRET_KEY:-minioadmin}"
MINIO_BUCKET="${MINIO_BUCKET:-cc1c-artifacts}"
MINIO_SECURE="${MINIO_SECURE:-false}"
MINIO_DATA_DIR="${MINIO_DATA_DIR:-/var/lib/minio}"
MINIO_ADDRESS="${MINIO_ADDRESS:-}"
MINIO_CONSOLE_ADDRESS="${MINIO_CONSOLE_ADDRESS:-:9001}"
MINIO_ROOT_USER="${MINIO_ROOT_USER:-$MINIO_ACCESS_KEY}"
MINIO_ROOT_PASSWORD="${MINIO_ROOT_PASSWORD:-$MINIO_SECRET_KEY}"
MINIO_PROMETHEUS_AUTH_TYPE="${MINIO_PROMETHEUS_AUTH_TYPE:-public}"

if [[ -z "$MINIO_ADDRESS" ]]; then
    minio_port="${MINIO_ENDPOINT##*:}"
    if [[ "$minio_port" == "$MINIO_ENDPOINT" ]]; then
        minio_port="9000"
    fi
    MINIO_ADDRESS=":${minio_port}"
fi

##############################################################################
# CLI ARGUMENTS
##############################################################################

DRY_RUN=false
VERBOSE=false
SKIP_POSTGRES=false
SKIP_REDIS=false
SKIP_MINIO=false
SKIP_PGADMIN=false
ONLY_POSTGRES=false
ONLY_REDIS=false
ONLY_MINIO=false
ONLY_PGADMIN=false

parse_args() {
    while [[ $# -gt 0 ]]; do
        case $1 in
            --only-postgres)  ONLY_POSTGRES=true; shift ;;
            --only-redis)     ONLY_REDIS=true; shift ;;
            --only-minio)     ONLY_MINIO=true; shift ;;
            --only-pgadmin)   ONLY_PGADMIN=true; shift ;;
            --skip-postgres)  SKIP_POSTGRES=true; shift ;;
            --skip-redis)     SKIP_REDIS=true; shift ;;
            --skip-minio)     SKIP_MINIO=true; shift ;;
            --skip-pgadmin)   SKIP_PGADMIN=true; shift ;;
            --dry-run)        DRY_RUN=true; shift ;;
            --verbose|-v)     VERBOSE=true; export VERBOSE; shift ;;
            --help|-h)        show_help; exit 0 ;;
            *)
                log_error "Неизвестный параметр: $1"
                show_help
                exit 1
                ;;
        esac
    done

    # Валидация конфликтующих флагов
    validate_flags
}

validate_flags() {
    if [[ "$ONLY_POSTGRES" == "true" && "$SKIP_POSTGRES" == "true" ]]; then
        log_error "Конфликтующие флаги: --only-postgres и --skip-postgres"
        exit 1
    fi

    if [[ "$ONLY_REDIS" == "true" && "$SKIP_REDIS" == "true" ]]; then
        log_error "Конфликтующие флаги: --only-redis и --skip-redis"
        exit 1
    fi

    if [[ "$ONLY_MINIO" == "true" && "$SKIP_MINIO" == "true" ]]; then
        log_error "Конфликтующие флаги: --only-minio и --skip-minio"
        exit 1
    fi

    if [[ "$ONLY_PGADMIN" == "true" && "$SKIP_PGADMIN" == "true" ]]; then
        log_error "Конфликтующие флаги: --only-pgadmin и --skip-pgadmin"
        exit 1
    fi

    local only_count=0
    [[ "$ONLY_POSTGRES" == "true" ]] && only_count=$((only_count + 1))
    [[ "$ONLY_REDIS" == "true" ]] && only_count=$((only_count + 1))
    [[ "$ONLY_MINIO" == "true" ]] && only_count=$((only_count + 1))
    [[ "$ONLY_PGADMIN" == "true" ]] && only_count=$((only_count + 1))

    if [[ $only_count -gt 1 ]]; then
        log_error "Можно указать только один --only-X флаг"
        exit 1
    fi
}

show_help() {
    cat << 'EOF'
CommandCenter1C - Infrastructure Installation (PostgreSQL + Redis + MinIO + pgAdmin)

Usage:
  ./scripts/setup/install-infra.sh [OPTIONS]

Options:
  --only-postgres     Установить только PostgreSQL
  --only-redis        Установить только Redis
  --only-minio        Установить только MinIO
  --only-pgadmin      Установить только pgAdmin
  --skip-postgres     Пропустить установку PostgreSQL
  --skip-redis        Пропустить установку Redis
  --skip-minio        Пропустить установку MinIO
  --skip-pgadmin      Пропустить установку pgAdmin
  --dry-run           Показать план без изменений
  --verbose, -v       Подробный вывод
  --help, -h          Показать эту справку

Environment Variables (from .env.local):
  DB_USER       PostgreSQL user (default: commandcenter)
  DB_PASSWORD   PostgreSQL password (default: commandcenter)
  DB_NAME       PostgreSQL database (default: commandcenter)
  DB_HOST       PostgreSQL host (default: localhost)
  DB_PORT       PostgreSQL port (default: 5432)
  REDIS_HOST    Redis host (default: localhost)
  REDIS_PORT    Redis port (default: 6379)
  MINIO_ENDPOINT      MinIO endpoint (default: localhost:9000)
  MINIO_ACCESS_KEY    MinIO access key (default: minioadmin)
  MINIO_SECRET_KEY    MinIO secret key (default: minioadmin)
  MINIO_BUCKET        MinIO bucket (default: cc1c-artifacts)
  MINIO_SECURE        MinIO secure flag (default: false)
  MINIO_DATA_DIR      MinIO data dir (default: /var/lib/minio)
  MINIO_ADDRESS       MinIO bind address (default: :9000)
  MINIO_CONSOLE_ADDRESS MinIO console address (default: :9001)

Examples:
  ./scripts/setup/install-infra.sh                  # Полная установка
  ./scripts/setup/install-infra.sh --dry-run        # Показать план
  ./scripts/setup/install-infra.sh --only-postgres  # Только PostgreSQL
  ./scripts/setup/install-infra.sh --only-minio     # Только MinIO
  ./scripts/setup/install-infra.sh --skip-redis     # Без Redis
  ./scripts/setup/install-infra.sh --skip-minio     # Без MinIO
  ./scripts/setup/install-infra.sh --skip-pgadmin   # Без pgAdmin
EOF
}

ensure_sudo() {
    if ! command -v sudo &>/dev/null; then
        log_error "sudo не найден. Установите sudo и повторите."
        exit 1
    fi

    if sudo -n true 2>/dev/null; then
        return 0
    fi

    log_warning "Требуется пароль sudo для установки/настройки."
    log_info "Выполните: sudo -v"
    exit 1
}

# Определяет, нужно ли устанавливать компонент
should_install() {
    local component=$1

    # Если указан --only-X, устанавливаем только его
    if [[ "$ONLY_POSTGRES" == "true" || "$ONLY_REDIS" == "true" || "$ONLY_MINIO" == "true" || "$ONLY_PGADMIN" == "true" ]]; then
        case $component in
            postgres) [[ "$ONLY_POSTGRES" == "true" ]] ;;
            redis)    [[ "$ONLY_REDIS" == "true" ]] ;;
            minio)    [[ "$ONLY_MINIO" == "true" ]] ;;
            pgadmin)  [[ "$ONLY_PGADMIN" == "true" ]] ;;
            *)        return 1 ;;
        esac
    else
        # Иначе проверяем --skip-X
        case $component in
            postgres) [[ "$SKIP_POSTGRES" != "true" ]] ;;
            redis)    [[ "$SKIP_REDIS" != "true" ]] ;;
            minio)    [[ "$SKIP_MINIO" != "true" ]] ;;
            pgadmin)  [[ "$SKIP_PGADMIN" != "true" ]] ;;
            *)        return 1 ;;
        esac
    fi
}

##############################################################################
# POSTGRESQL INSTALLATION
##############################################################################

install_postgresql() {
    log_step "Установка PostgreSQL..."

    # 1. Установка пакета
    if pkg_is_installed "postgresql"; then
        log_info "PostgreSQL уже установлен"
    else
        if $DRY_RUN; then
            log_info "[DRY-RUN] Будет установлен пакет: postgresql"
        else
            log_info "Установка пакета postgresql..."
            pkg_install "postgresql"
        fi
    fi

    # 2. Инициализация кластера
    if pg_cluster_exists; then
        log_info "PostgreSQL кластер уже инициализирован"
    else
        if $DRY_RUN; then
            log_info "[DRY-RUN] Будет инициализирован кластер PostgreSQL"
        else
            log_info "Инициализация кластера PostgreSQL..."
            pg_init_cluster
        fi
    fi

    # 3. Включение автозапуска
    if $DRY_RUN; then
        log_info "[DRY-RUN] Будет включен автозапуск PostgreSQL"
    else
        log_info "Включение автозапуска PostgreSQL..."
        pg_enable_autostart
    fi

    # 4. Запуск сервиса
    if pg_is_running; then
        log_info "PostgreSQL уже запущен"
    else
        if $DRY_RUN; then
            log_info "[DRY-RUN] Будет запущен PostgreSQL"
        else
            log_info "Запуск PostgreSQL..."
            pg_start
        fi
    fi

    # 5. Настройка pg_hba.conf
    if $DRY_RUN; then
        log_info "[DRY-RUN] Будет настроен pg_hba.conf для пользователя $DB_USER"
    else
        log_info "Настройка pg_hba.conf..."
        pg_configure_hba
        pg_reload_config
    fi

    # 6. Создание пользователя
    if $DRY_RUN; then
        log_info "[DRY-RUN] Будет создан пользователь PostgreSQL: $DB_USER"
    else
        log_info "Создание пользователя PostgreSQL: $DB_USER..."
        pg_create_user "$DB_USER" "$DB_PASSWORD"
    fi

    # 7. Создание базы данных
    if $DRY_RUN; then
        log_info "[DRY-RUN] Будет создана база данных: $DB_NAME (owner: $DB_USER)"
    else
        log_info "Создание базы данных: $DB_NAME..."
        pg_create_database "$DB_NAME" "$DB_USER"
    fi

    log_success "PostgreSQL установлен и настроен"
}

##############################################################################
# REDIS INSTALLATION
##############################################################################

install_redis() {
    log_step "Установка Redis..."

    # 1. Установка пакета
    if pkg_is_installed "redis"; then
        log_info "Redis уже установлен"
    else
        if $DRY_RUN; then
            log_info "[DRY-RUN] Будет установлен пакет: redis"
        else
            log_info "Установка пакета redis..."
            pkg_install "redis"
        fi
    fi

    # 2. Включение автозапуска
    if $DRY_RUN; then
        log_info "[DRY-RUN] Будет включен автозапуск Redis"
    else
        log_info "Включение автозапуска Redis..."
        if command -v systemctl &>/dev/null; then
            sudo systemctl enable redis
        else
            log_warning "systemctl недоступен, автозапуск не настроен"
        fi
    fi

    # 3. Запуск сервиса
    local redis_running=false
    if command -v systemctl &>/dev/null; then
        systemctl is-active --quiet redis 2>/dev/null && redis_running=true
    fi
    if ! $redis_running && pgrep -x "redis-server" &>/dev/null; then
        redis_running=true
    fi

    if $redis_running; then
        log_info "Redis уже запущен"
    else
        if $DRY_RUN; then
            log_info "[DRY-RUN] Будет запущен Redis"
        else
            log_info "Запуск Redis..."
            if command -v systemctl &>/dev/null; then
                sudo systemctl start redis
            else
                log_warning "systemctl недоступен, запустите Redis вручную"
            fi
        fi
    fi

    # 4. Проверка подключения
    if $DRY_RUN; then
        log_info "[DRY-RUN] Будет проверено подключение к Redis"
    else
        log_info "Проверка подключения к Redis..."
        local retries=5
        while [[ $retries -gt 0 ]]; do
            if redis-cli -h "$REDIS_HOST" -p "$REDIS_PORT" ping 2>/dev/null | grep -q "PONG"; then
                log_success "Redis отвечает на PING"
                break
            fi
            sleep 1
            ((retries--))
        done

        if [[ $retries -eq 0 ]]; then
            log_warning "Redis не отвечает на PING, но сервис может быть запущен"
        fi
    fi

    log_success "Redis установлен и настроен"
}

##############################################################################
# MINIO INSTALLATION
##############################################################################

get_minio_health_url() {
    local endpoint="${MINIO_ENDPOINT:-localhost:9000}"
    endpoint="${endpoint#*://}"
    local host="${endpoint%%:*}"
    local port="${endpoint##*:}"

    if [[ "$host" == "$port" ]]; then
        port="9000"
    fi

    echo "http://${host}:${port}/minio/health/ready"
}

get_minio_api_url() {
    local scheme="http"
    if is_true "$MINIO_SECURE"; then
        scheme="https"
    fi

    local endpoint="${MINIO_ENDPOINT:-localhost:9000}"
    endpoint="${endpoint#*://}"
    echo "${scheme}://${endpoint}"
}

ensure_minio_bucket() {
    if ! command -v mc &>/dev/null; then
        log_warning "MinIO client (mc) не установлен, пропускаем создание бакета"
        return 0
    fi

    local alias_name="cc1c-minio"
    local api_url
    api_url=$(get_minio_api_url)

    if ! mc alias set "$alias_name" "$api_url" "$MINIO_ACCESS_KEY" "$MINIO_SECRET_KEY" >/dev/null 2>&1; then
        log_warning "Не удалось настроить alias для MinIO ($api_url)"
        return 1
    fi

    if mc ls "${alias_name}/${MINIO_BUCKET}" >/dev/null 2>&1; then
        log_info "Бакет уже существует: ${MINIO_BUCKET}"
        return 0
    fi

    if mc mb --ignore-existing "${alias_name}/${MINIO_BUCKET}" >/dev/null 2>&1; then
        log_success "Бакет создан: ${MINIO_BUCKET}"
        return 0
    fi

    log_warning "Не удалось создать бакет: ${MINIO_BUCKET}"
    return 1
}

install_minio() {
    log_step "Установка MinIO..."

    local minio_pkg
    minio_pkg=$(pkg_map_name "minio") || true
    if [[ -n "$minio_pkg" ]] && pkg_is_installed "$minio_pkg"; then
        log_info "MinIO уже установлен ($minio_pkg)"
    else
        if $DRY_RUN; then
            log_info "[DRY-RUN] Будет установлен пакет: minio (AUR: minio)"
        else
            log_info "Установка MinIO (AUR: minio)..."
            pkg_install "minio"
        fi
    fi

    if $DRY_RUN; then
        log_info "[DRY-RUN] Будет создан каталог данных MinIO: $MINIO_DATA_DIR"
    else
        sudo mkdir -p "$MINIO_DATA_DIR"
        sudo chown -R "$USER:$USER" "$MINIO_DATA_DIR"
        sudo chmod 750 "$MINIO_DATA_DIR"
    fi

    if $DRY_RUN; then
        log_info "[DRY-RUN] Будет установлен systemd unit: minio.service"
    else
        local unit_src="$PROJECT_ROOT/infrastructure/systemd/minio.service"
        if [[ -f "$unit_src" ]]; then
            sudo cp "$unit_src" /etc/systemd/system/minio.service
        else
            log_warning "unit file не найден: $unit_src"
        fi
    fi

    if $DRY_RUN; then
        log_info "[DRY-RUN] Будет создан env файл MinIO: /etc/commandcenter1c/minio.env"
    else
        sudo mkdir -p /etc/commandcenter1c
        if [[ ! -f /etc/commandcenter1c/minio.env ]]; then
            sudo tee /etc/commandcenter1c/minio.env >/dev/null <<EOF
MINIO_DATA_DIR=${MINIO_DATA_DIR}
MINIO_ADDRESS=${MINIO_ADDRESS}
MINIO_CONSOLE_ADDRESS=${MINIO_CONSOLE_ADDRESS}
MINIO_ROOT_USER=${MINIO_ROOT_USER}
MINIO_ROOT_PASSWORD=${MINIO_ROOT_PASSWORD}
MINIO_PROMETHEUS_AUTH_TYPE=${MINIO_PROMETHEUS_AUTH_TYPE}
EOF
            log_success "Создан /etc/commandcenter1c/minio.env"
        else
            log_info "/etc/commandcenter1c/minio.env уже существует, пропускаем"
        fi
    fi

    if $DRY_RUN; then
        log_info "[DRY-RUN] Будет создан symlink /usr/bin/minio -> /usr/sbin/minio (если нужно)"
    else
        if [[ ! -x "/usr/bin/minio" ]] && [[ -x "/usr/sbin/minio" ]]; then
            sudo ln -sf /usr/sbin/minio /usr/bin/minio
        fi
    fi

    if $DRY_RUN; then
        log_info "[DRY-RUN] Будет включен и запущен сервис MinIO"
    else
        sudo systemctl daemon-reload
        sudo systemctl enable minio
        sudo systemctl start minio
    fi

    if ! $DRY_RUN; then
        local health_url
        health_url=$(get_minio_health_url)
        if check_health_endpoint "$health_url" 2; then
            log_success "MinIO отвечает (${health_url})"
        else
            log_warning "MinIO не отвечает (${health_url})"
        fi
    fi

    if ! $DRY_RUN; then
        if ! command -v mc &>/dev/null; then
            log_info "Установка minio client (mc) для создания бакета..."
            pkg_install "minio_client" || log_warning "Не удалось установить minio client"
        fi
        ensure_minio_bucket || true
    fi

    log_success "MinIO установлен и настроен"
}

##############################################################################
# PGADMIN INSTALLATION
##############################################################################

install_pgadmin() {
    log_step "Установка pgAdmin 4..."

    # 1. Установка пакета
    if pkg_is_installed "pgadmin4"; then
        log_info "pgAdmin 4 уже установлен"
    else
        if $DRY_RUN; then
            log_info "[DRY-RUN] Будет установлен пакет: pgadmin4"
        else
            log_info "Установка пакета pgadmin4..."
            pkg_install "pgadmin"
        fi
    fi

    # 2. Вывод информации о запуске
    if ! $DRY_RUN; then
        log_info "pgAdmin 4 установлен"
        log_info "Для запуска выполните: pgadmin4"
        log_info "Web-интерфейс будет доступен по адресу: http://127.0.0.1:5050"
    fi

    log_success "pgAdmin 4 установлен"
}

##############################################################################
# PRINT PLAN (dry-run mode)
##############################################################################

print_plan() {
    echo ""
    echo -e "${BOLD}Plan:${NC}"
    echo ""

    if should_install "postgres"; then
        echo "PostgreSQL:"
        echo "  - Install package: postgresql"
        echo "  - Initialize cluster (if needed)"
        echo "  - Configure pg_hba.conf"
        echo "  - Create user: $DB_USER"
        echo "  - Create database: $DB_NAME"
        echo "  - Enable autostart (systemd)"
        echo "  - Start service"
        echo ""
    fi

    if should_install "redis"; then
        echo "Redis:"
        echo "  - Install package: redis"
        echo "  - Enable autostart (systemd)"
        echo "  - Start service"
        echo "  - Verify connection (redis-cli ping)"
        echo ""
    fi

    if should_install "minio"; then
        echo "MinIO:"
        echo "  - Install package: minio (AUR: minio)"
        echo "  - Create data dir: $MINIO_DATA_DIR"
        echo "  - Install systemd unit (minio.service)"
        echo "  - Create /etc/commandcenter1c/minio.env (if missing)"
        echo "  - Enable autostart (systemd)"
        echo "  - Start service"
        echo ""
    fi

    if should_install "pgadmin"; then
        echo "pgAdmin 4:"
        echo "  - Install package: pgadmin4"
        echo "  - Web UI: http://127.0.0.1:5050"
        echo ""
    fi

    echo "Configuration (from .env.local or defaults):"
    echo "  DB_HOST=$DB_HOST"
    echo "  DB_PORT=$DB_PORT"
    echo "  DB_USER=$DB_USER"
    echo "  DB_NAME=$DB_NAME"
    echo "  REDIS_HOST=$REDIS_HOST"
    echo "  REDIS_PORT=$REDIS_PORT"
    echo "  MINIO_ENDPOINT=$MINIO_ENDPOINT"
    echo "  MINIO_ACCESS_KEY=$MINIO_ACCESS_KEY"
    echo "  MINIO_SECRET_KEY=$MINIO_SECRET_KEY"
    echo "  MINIO_BUCKET=$MINIO_BUCKET"
    echo "  MINIO_SECURE=$MINIO_SECURE"
    echo "  MINIO_DATA_DIR=$MINIO_DATA_DIR"
    echo ""
}

##############################################################################
# FINAL REPORT
##############################################################################

print_report() {
    echo ""
    echo -e "${BOLD}======================================${NC}"
    echo -e "${BOLD}  Установка инфраструктуры завершена${NC}"
    echo -e "${BOLD}======================================${NC}"
    echo ""

    if should_install "postgres"; then
        echo "PostgreSQL:"
        if pg_is_running; then
            print_status "success" "Сервис запущен"
        else
            print_status "warning" "Сервис не запущен"
        fi
        echo "  Host: $DB_HOST:$DB_PORT"
        echo "  User: $DB_USER"
        echo "  Database: $DB_NAME"
        echo ""
    fi

    if should_install "redis"; then
        echo "Redis:"
        local redis_status="warning"
        if redis-cli -h "$REDIS_HOST" -p "$REDIS_PORT" ping 2>/dev/null | grep -q "PONG"; then
            redis_status="success"
            print_status "success" "Сервис запущен"
        else
            print_status "warning" "Сервис не отвечает"
        fi
        echo "  Host: $REDIS_HOST:$REDIS_PORT"
        echo ""
    fi

    if should_install "minio"; then
        echo "MinIO:"
        if check_health_endpoint "$(get_minio_health_url)" 2; then
            print_status "success" "Сервис запущен"
        else
            print_status "warning" "Сервис не отвечает"
        fi
        echo "  Endpoint: $MINIO_ENDPOINT"
        echo "  Data dir: $MINIO_DATA_DIR"
        echo ""
    fi

    if should_install "pgadmin"; then
        echo "pgAdmin 4:"
        if command -v pgadmin4 &>/dev/null; then
            print_status "success" "Установлен"
        else
            print_status "warning" "Не установлен"
        fi
        echo "  Запуск: pgadmin4"
        echo "  Web UI: http://127.0.0.1:5050"
        echo ""
    fi

    echo "Следующие шаги:"
    echo ""
    echo "  1. Проверьте подключение:"
    echo "     psql -h $DB_HOST -U $DB_USER -d $DB_NAME"
    echo "     redis-cli -h $REDIS_HOST -p $REDIS_PORT ping"
    echo "     curl $(get_minio_health_url)"
    echo ""
    echo "  2. Примените миграции Django:"
    echo "     ./scripts/dev/run-migrations.sh"
    echo ""
    echo "  3. Запустите сервисы:"
    echo "     ./scripts/dev/start-all.sh"
    echo ""
}

##############################################################################
# MAIN
##############################################################################

main() {
    parse_args "$@"

    echo ""
    echo -e "${BOLD}======================================${NC}"
    echo -e "${BOLD}  CommandCenter1C - Infrastructure${NC}"
    echo -e "${BOLD}======================================${NC}"
    echo ""

    local platform
    platform=$(detect_platform)
    log_info "Платформа: $platform"
    log_info "Проект: $PROJECT_ROOT"
    echo ""

    # Проверка: нечего устанавливать?
    if ! should_install "postgres" && ! should_install "redis" && ! should_install "minio" && ! should_install "pgadmin"; then
        log_warning "Нечего устанавливать (все компоненты пропущены)"
        exit 0
    fi

    if $DRY_RUN; then
        log_warning "Режим DRY-RUN: изменения НЕ будут применены"
        print_plan
        exit 0
    fi

    ensure_sudo

    # PostgreSQL
    if should_install "postgres"; then
        install_postgresql
        echo ""
    fi

    # Redis
    if should_install "redis"; then
        install_redis
        echo ""
    fi

    # MinIO
    if should_install "minio"; then
        install_minio
        echo ""
    fi

    # pgAdmin
    if should_install "pgadmin"; then
        install_pgadmin
        echo ""
    fi

    # Финальный отчет
    print_report
}

main "$@"
