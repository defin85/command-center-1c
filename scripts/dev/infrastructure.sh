#!/bin/bash

##############################################################################
# CommandCenter1C - Infrastructure Management
##############################################################################
#
# Явное управление инфраструктурными сервисами (PostgreSQL, Redis, MinIO,
# Prometheus, Grafana, Jaeger).
#
# Usage:
#   ./infrastructure.sh status              # Показать статус всех сервисов
#   ./infrastructure.sh start               # Запустить сервисы
#   ./infrastructure.sh stop                # Остановить сервисы
#   ./infrastructure.sh restart             # Перезапустить
#   ./infrastructure.sh enable              # Включить автозапуск
#   ./infrastructure.sh disable             # Выключить автозапуск
#
# Options:
#   --infra                                 # Только PostgreSQL, Redis, MinIO
#   --monitoring                            # Только Prometheus, Grafana, Jaeger
#   --all                                   # Все (по умолчанию)
#
# Examples:
#   ./infrastructure.sh status              # Статус всех
#   ./infrastructure.sh start --infra       # Запустить только БД/хранилище
#   ./infrastructure.sh stop --monitoring   # Остановить мониторинг
#   ./infrastructure.sh enable --all        # Включить автозапуск всего
#
# Version: 1.0.0
##############################################################################

set -euo pipefail

# Определение путей
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

# Подключение библиотеки
source "$PROJECT_ROOT/scripts/lib/init.sh"

cd "$PROJECT_ROOT"

# Загрузить переменные окружения
if [ -f "$PROJECT_ROOT/.env.local" ]; then
    set -a
    source "$PROJECT_ROOT/.env.local"
    set +a
fi

##############################################################################
# CONSTANTS
##############################################################################

# Сервисы инфраструктуры
INFRA_SERVICES=("postgresql" "redis" "minio")

# Сервисы мониторинга
MONITORING_SERVICES=("prometheus" "grafana" "jaeger")

# Все сервисы
ALL_SERVICES=("${INFRA_SERVICES[@]}" "${MONITORING_SERVICES[@]}")

##############################################################################
# HELP
##############################################################################

show_help() {
    echo -e "${BLUE}CommandCenter1C - Infrastructure Management${NC}"
    echo ""
    echo "Управление инфраструктурными сервисами через systemd."
    echo ""
    echo -e "${CYAN}Usage:${NC}"
    echo "  $0 <command> [options]"
    echo ""
    echo -e "${CYAN}Commands:${NC}"
    echo "  status     Показать статус сервисов (автозапуск, состояние)"
    echo "  start      Запустить сервисы (даже если отключен автозапуск)"
    echo "  stop       Остановить сервисы (даже если включен автозапуск)"
    echo "  restart    Перезапустить сервисы"
    echo "  enable     Включить автозапуск сервисов"
    echo "  disable    Выключить автозапуск сервисов"
    echo ""
    echo -e "${CYAN}Options:${NC}"
    echo "  --infra       Только PostgreSQL, Redis, MinIO"
    echo "  --monitoring  Только Prometheus, Grafana, Jaeger"
    echo "  --all         Все сервисы (по умолчанию)"
    echo ""
    echo -e "${CYAN}Examples:${NC}"
    echo "  $0 status                    # Статус всех сервисов"
    echo "  $0 start --infra             # Запустить только БД/хранилище"
    echo "  $0 stop --monitoring         # Остановить мониторинг"
    echo "  $0 restart --all             # Перезапустить все"
    echo "  $0 enable --infra            # Автозапуск для БД"
    echo "  $0 disable --monitoring      # Отключить автозапуск мониторинга"
    echo ""
}

##############################################################################
# UTILITY FUNCTIONS
##############################################################################

# Получить статус автозапуска сервиса
# Returns: enabled | disabled | not-found
get_service_enabled_status() {
    local service=$1

    if ! systemctl list-unit-files "${service}.service" &>/dev/null 2>&1; then
        echo "not-found"
        return
    fi

    if systemctl is-enabled --quiet "$service" 2>/dev/null; then
        echo "enabled"
    else
        echo "disabled"
    fi
}

# Получить статус работы сервиса
# Returns: running | stopped | not-found
get_service_running_status() {
    local service=$1

    if ! systemctl list-unit-files "${service}.service" &>/dev/null 2>&1; then
        echo "not-found"
        return
    fi

    if systemctl is-active --quiet "$service" 2>/dev/null; then
        echo "running"
    else
        echo "stopped"
    fi
}

# Получить порт MinIO из MINIO_ENDPOINT
get_minio_port() {
    local endpoint="${MINIO_ENDPOINT:-localhost:9000}"
    endpoint="${endpoint#*://}"
    local host="${endpoint%%:*}"
    local port="${endpoint##*:}"

    if [[ "$host" == "$port" ]]; then
        port="9000"
    fi

    echo "$port"
}

# Получить URL для проверки здоровья сервиса
get_service_health_url() {
    local service=$1

    case "$service" in
        postgresql)
            echo ""  # Проверяем через pg_isready
            ;;
        redis)
            echo ""  # Проверяем через redis-cli
            ;;
        minio)
            echo "http://localhost:$(get_minio_port)/minio/health/ready"
            ;;
        prometheus)
            echo "http://localhost:9090/-/healthy"
            ;;
        grafana)
            echo "http://localhost:3000/api/health"
            ;;
        jaeger)
            echo "http://localhost:16686/"
            ;;
        *)
            echo ""
            ;;
    esac
}

# Проверка здоровья сервиса
check_service_health() {
    local service=$1

    case "$service" in
        postgresql)
            pg_isready -h localhost -p "${DB_PORT:-5432}" &>/dev/null
            ;;
        redis)
            redis-cli -h localhost -p "${REDIS_PORT:-6379}" ping 2>/dev/null | grep -q "PONG"
            ;;
        minio)
            check_health_endpoint "http://localhost:$(get_minio_port)/minio/health/ready" 2
            ;;
        prometheus)
            check_health_endpoint "http://localhost:9090/-/healthy" 2
            ;;
        grafana)
            check_health_endpoint "http://localhost:3000/api/health" 2
            ;;
        jaeger)
            check_health_endpoint "http://localhost:16686/" 2
            ;;
        *)
            return 1
            ;;
    esac
}

# Получить порт сервиса
get_service_port() {
    local service=$1

    case "$service" in
        postgresql) echo "${DB_PORT:-5432}" ;;
        redis) echo "${REDIS_PORT:-6379}" ;;
        minio) echo "$(get_minio_port)" ;;
        prometheus) echo "9090" ;;
        grafana) echo "3000" ;;
        jaeger) echo "16686" ;;
        *) echo "" ;;
    esac
}

# Получить описание сервиса
get_service_description() {
    local service=$1

    case "$service" in
        postgresql) echo "PostgreSQL (Database)" ;;
        redis) echo "Redis (Cache/Queue)" ;;
        minio) echo "MinIO (Artifact Storage)" ;;
        prometheus) echo "Prometheus (Metrics)" ;;
        grafana) echo "Grafana (Dashboards)" ;;
        jaeger) echo "Jaeger (Tracing)" ;;
        *) echo "$service" ;;
    esac
}

# Получить команду установки для Arch Linux
get_install_command() {
    local service=$1

    case "$service" in
        postgresql) echo "pacman -S postgresql" ;;
        redis) echo "pacman -S redis" ;;
        minio) echo "pacman -S minio" ;;
        prometheus) echo "pacman -S prometheus" ;;
        grafana) echo "pacman -S grafana" ;;
        jaeger) echo "yay -S jaeger (из AUR)" ;;
        *) echo "" ;;
    esac
}

##############################################################################
# COMMAND FUNCTIONS
##############################################################################

# Показать статус сервисов
cmd_status() {
    local services=("$@")

    print_header "Infrastructure Status"

    # Таблица статусов
    printf "${CYAN}%-20s %-12s %-12s %-10s %-30s${NC}\n" "SERVICE" "ENABLED" "STATUS" "PORT" "HEALTH"
    print_separator "-" 84

    for service in "${services[@]}"; do
        local enabled_status
        local running_status
        local port
        local health_status
        local description

        enabled_status=$(get_service_enabled_status "$service")
        running_status=$(get_service_running_status "$service")
        port=$(get_service_port "$service")
        description=$(get_service_description "$service")

        # Цвета для статусов
        local enabled_color running_color health_color

        case "$enabled_status" in
            enabled) enabled_color="${GREEN}enabled${NC}" ;;
            disabled) enabled_color="${YELLOW}disabled${NC}" ;;
            not-found) enabled_color="${RED}not-found${NC}" ;;
        esac

        case "$running_status" in
            running) running_color="${GREEN}running${NC}" ;;
            stopped) running_color="${RED}stopped${NC}" ;;
            not-found) running_color="${RED}not-found${NC}" ;;
        esac

        # Проверка здоровья (только если запущен)
        if [[ "$running_status" == "running" ]]; then
            if check_service_health "$service"; then
                health_status="${GREEN}healthy${NC}"
            else
                health_status="${YELLOW}unhealthy${NC}"
            fi
        else
            health_status="${DIM}n/a${NC}"
        fi

        printf "%-20s ${enabled_color}  ${running_color}  %-10s ${health_status}\n" \
            "$description" "$port"
    done

    echo ""

    # Показать команды для управления
    echo -e "${CYAN}Manual Commands:${NC}"
    echo ""
    echo -e "  ${DIM}# Проверить статус конкретного сервиса${NC}"
    echo -e "  systemctl status <service>"
    echo ""
    echo -e "  ${DIM}# Запустить/остановить${NC}"
    echo -e "  sudo systemctl start|stop <service>"
    echo ""
    echo -e "  ${DIM}# Включить/выключить автозапуск${NC}"
    echo -e "  sudo systemctl enable|disable <service>"
    echo ""
    echo -e "  ${DIM}# Просмотр логов${NC}"
    echo -e "  journalctl -u <service> -f"
    echo ""
}

# Запустить сервисы
cmd_start() {
    local services=("$@")

    print_header "Starting Services"

    local success=true

    for service in "${services[@]}"; do
        local running_status
        running_status=$(get_service_running_status "$service")

        if [[ "$running_status" == "not-found" ]]; then
            local install_cmd
            install_cmd=$(get_install_command "$service")
            print_status "warning" "$(get_service_description "$service"): не установлен"
            echo -e "           ${DIM}Установка: ${install_cmd}${NC}"
            continue
        fi

        if [[ "$running_status" == "running" ]]; then
            print_status "info" "$(get_service_description "$service"): уже запущен"
            continue
        fi

        log_info "Запуск $(get_service_description "$service")..."
        if sudo systemctl start "$service" 2>/dev/null; then
            # Ждем готовности
            sleep 1
            if check_service_health "$service"; then
                print_status "success" "$(get_service_description "$service"): запущен и готов"
            else
                print_status "warning" "$(get_service_description "$service"): запущен, но не отвечает"
            fi
        else
            print_status "error" "$(get_service_description "$service"): ошибка запуска"
            success=false
        fi
    done

    echo ""

    if [[ "$success" == "true" ]]; then
        log_success "Все сервисы запущены"
    else
        log_warning "Некоторые сервисы не запустились"
    fi
}

# Остановить сервисы
cmd_stop() {
    local services=("$@")

    print_header "Stopping Services"

    local success=true

    for service in "${services[@]}"; do
        local running_status
        running_status=$(get_service_running_status "$service")

        if [[ "$running_status" == "not-found" ]]; then
            print_status "info" "$(get_service_description "$service"): не установлен"
            continue
        fi

        if [[ "$running_status" == "stopped" ]]; then
            print_status "info" "$(get_service_description "$service"): уже остановлен"
            continue
        fi

        log_info "Остановка $(get_service_description "$service")..."
        if sudo systemctl stop "$service" 2>/dev/null; then
            print_status "success" "$(get_service_description "$service"): остановлен"
        else
            print_status "error" "$(get_service_description "$service"): ошибка остановки"
            success=false
        fi
    done

    echo ""

    if [[ "$success" == "true" ]]; then
        log_success "Все сервисы остановлены"
    else
        log_warning "Некоторые сервисы не остановились"
    fi
}

# Перезапустить сервисы
cmd_restart() {
    local services=("$@")

    print_header "Restarting Services"

    local success=true

    for service in "${services[@]}"; do
        local running_status
        running_status=$(get_service_running_status "$service")

        if [[ "$running_status" == "not-found" ]]; then
            local install_cmd
            install_cmd=$(get_install_command "$service")
            print_status "warning" "$(get_service_description "$service"): не установлен"
            echo -e "           ${DIM}Установка: ${install_cmd}${NC}"
            continue
        fi

        log_info "Перезапуск $(get_service_description "$service")..."
        if sudo systemctl restart "$service" 2>/dev/null; then
            sleep 1
            if check_service_health "$service"; then
                print_status "success" "$(get_service_description "$service"): перезапущен и готов"
            else
                print_status "warning" "$(get_service_description "$service"): перезапущен, но не отвечает"
            fi
        else
            print_status "error" "$(get_service_description "$service"): ошибка перезапуска"
            success=false
        fi
    done

    echo ""

    if [[ "$success" == "true" ]]; then
        log_success "Все сервисы перезапущены"
    else
        log_warning "Некоторые сервисы не перезапустились"
    fi
}

# Включить автозапуск
cmd_enable() {
    local services=("$@")

    print_header "Enabling Autostart"

    local success=true

    for service in "${services[@]}"; do
        local enabled_status
        enabled_status=$(get_service_enabled_status "$service")

        if [[ "$enabled_status" == "not-found" ]]; then
            local install_cmd
            install_cmd=$(get_install_command "$service")
            print_status "warning" "$(get_service_description "$service"): не установлен"
            echo -e "           ${DIM}Установка: ${install_cmd}${NC}"
            continue
        fi

        if [[ "$enabled_status" == "enabled" ]]; then
            print_status "info" "$(get_service_description "$service"): автозапуск уже включен"
            continue
        fi

        log_info "Включение автозапуска $(get_service_description "$service")..."
        if sudo systemctl enable "$service" 2>/dev/null; then
            print_status "success" "$(get_service_description "$service"): автозапуск включен"
        else
            print_status "error" "$(get_service_description "$service"): ошибка включения автозапуска"
            success=false
        fi
    done

    echo ""

    if [[ "$success" == "true" ]]; then
        log_success "Автозапуск включен для всех сервисов"
    else
        log_warning "Для некоторых сервисов не удалось включить автозапуск"
    fi
}

# Выключить автозапуск
cmd_disable() {
    local services=("$@")

    print_header "Disabling Autostart"

    local success=true

    for service in "${services[@]}"; do
        local enabled_status
        enabled_status=$(get_service_enabled_status "$service")

        if [[ "$enabled_status" == "not-found" ]]; then
            print_status "info" "$(get_service_description "$service"): не установлен"
            continue
        fi

        if [[ "$enabled_status" == "disabled" ]]; then
            print_status "info" "$(get_service_description "$service"): автозапуск уже выключен"
            continue
        fi

        log_info "Выключение автозапуска $(get_service_description "$service")..."
        if sudo systemctl disable "$service" 2>/dev/null; then
            print_status "success" "$(get_service_description "$service"): автозапуск выключен"
        else
            print_status "error" "$(get_service_description "$service"): ошибка выключения автозапуска"
            success=false
        fi
    done

    echo ""

    if [[ "$success" == "true" ]]; then
        log_success "Автозапуск выключен для всех сервисов"
    else
        log_warning "Для некоторых сервисов не удалось выключить автозапуск"
    fi
}

##############################################################################
# MAIN
##############################################################################

# Проверка Docker режима
if is_docker_mode; then
    log_warning "Обнаружен Docker режим (USE_DOCKER=true в .env.local)"
    log_info "Этот скрипт предназначен для Native режима (systemd)"
    echo ""
    echo -e "Для работы с Docker используйте:"
    echo -e "  ${GREEN}docker compose -f docker-compose.local.yml up -d${NC}      # Запуск"
    echo -e "  ${GREEN}docker compose -f docker-compose.local.yml down${NC}        # Остановка"
    echo -e "  ${GREEN}docker compose -f docker-compose.local.yml ps${NC}          # Статус"
    echo ""
    echo -e "Или переключитесь на Native режим:"
    echo -e "  ${CYAN}USE_DOCKER=false${NC} в .env.local"
    echo ""
    exit 0
fi

# Парсинг аргументов
COMMAND=""
SCOPE="all"

while [[ $# -gt 0 ]]; do
    case $1 in
        status|start|stop|restart|enable|disable)
            COMMAND="$1"
            shift
            ;;
        --infra)
            SCOPE="infra"
            shift
            ;;
        --monitoring)
            SCOPE="monitoring"
            shift
            ;;
        --all)
            SCOPE="all"
            shift
            ;;
        --help|-h)
            show_help
            exit 0
            ;;
        *)
            log_error "Неизвестный аргумент: $1"
            echo ""
            show_help
            exit 1
            ;;
    esac
done

# Проверка команды
if [[ -z "$COMMAND" ]]; then
    log_error "Не указана команда"
    echo ""
    show_help
    exit 1
fi

# Определить список сервисов
case "$SCOPE" in
    infra)
        SERVICES=("${INFRA_SERVICES[@]}")
        ;;
    monitoring)
        SERVICES=("${MONITORING_SERVICES[@]}")
        ;;
    all)
        SERVICES=("${ALL_SERVICES[@]}")
        ;;
esac

# Выполнить команду
case "$COMMAND" in
    status)
        cmd_status "${SERVICES[@]}"
        ;;
    start)
        cmd_start "${SERVICES[@]}"
        ;;
    stop)
        cmd_stop "${SERVICES[@]}"
        ;;
    restart)
        cmd_restart "${SERVICES[@]}"
        ;;
    enable)
        cmd_enable "${SERVICES[@]}"
        ;;
    disable)
        cmd_disable "${SERVICES[@]}"
        ;;
esac
