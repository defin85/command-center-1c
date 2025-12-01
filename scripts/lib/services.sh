#!/bin/bash

##############################################################################
# CommandCenter1C - Service Utilities Library
##############################################################################
#
# Утилиты для работы с сервисами: порты, процессы, health checks,
# Python venv, Go бинарники.
#
# Usage:
#   source scripts/lib/services.sh
#
# Dependencies:
#   - scripts/lib/core.sh
#   - scripts/lib/platform.sh
#
# Exports:
#   Ports: check_port_listening, get_pid_on_port, kill_process_on_port
#   Python: activate_venv, is_venv_active
#   Go: get_binary_path, detect_go_service_changes
#   Health: check_health_endpoint, wait_for_service
#   Process: is_process_running, get_process_by_name
#
# Version: 1.0.0
##############################################################################

# Проверка зависимостей
if [[ -z "${CC1C_LIB_CORE_LOADED:-}" ]]; then
    echo "ERROR: services.sh requires core.sh to be loaded first" >&2
    return 1
fi

if [[ -z "${CC1C_LIB_PLATFORM_LOADED:-}" ]]; then
    echo "ERROR: services.sh requires platform.sh to be loaded first" >&2
    return 1
fi

# Предотвращение повторного sourcing
if [[ -n "${CC1C_LIB_SERVICES_LOADED:-}" ]]; then
    return 0
fi
CC1C_LIB_SERVICES_LOADED=true

##############################################################################
# PORT UTILITIES
##############################################################################

# check_port_listening - проверка занятости порта
# Usage: if check_port_listening 8080; then echo "Port is in use"; fi
# Returns: 0 if port is listening, 1 otherwise
# Note: В WSL проверяет оба окружения (Linux и Windows) для полной картины
check_port_listening() {
    local port=$1

    case "$OS_TYPE" in
        windows)
            netstat -ano 2>/dev/null | grep -q ":${port}.*LISTENING"
            ;;
        wsl)
            # WSL: проверяем И Linux порты (ss) И Windows порты (netstat.exe)
            # Это важно для сервисов типа ragent/ras которые работают на Windows
            if command -v ss &>/dev/null; then
                ss -tlnp 2>/dev/null | grep -q ":${port} " && return 0
            else
                netstat -tlnp 2>/dev/null | grep -q ":${port} " && return 0
            fi
            # Fallback: проверить Windows порты через netstat.exe
            netstat.exe -an 2>/dev/null | grep -q ":${port}.*LISTENING" && return 0
            return 1
            ;;
        linux)
            # Native Linux
            if command -v ss &>/dev/null; then
                ss -tlnp 2>/dev/null | grep -q ":${port} "
            else
                netstat -tlnp 2>/dev/null | grep -q ":${port} "
            fi
            ;;
        macos)
            lsof -iTCP:"${port}" -sTCP:LISTEN -n -P 2>/dev/null | grep -q LISTEN
            ;;
        *)
            # Fallback - пробуем lsof
            lsof -i ":${port}" 2>/dev/null | grep -q LISTEN
            ;;
    esac
}

# get_pid_on_port - получение PID процесса на порту
# Usage: pid=$(get_pid_on_port 8080)
# Returns: PID или пустая строка
get_pid_on_port() {
    local port=$1
    local pid=""

    case "$OS_TYPE" in
        windows)
            pid=$(netstat -ano 2>/dev/null | grep ":${port}.*LISTENING" | awk '{print $5}' | head -1)
            ;;
        wsl|linux)
            if command -v ss &>/dev/null; then
                pid=$(ss -tlnp 2>/dev/null | grep ":${port} " | sed -E 's/.*pid=([0-9]+).*/\1/' | head -1)
            else
                pid=$(netstat -tlnp 2>/dev/null | grep ":${port} " | awk '{print $7}' | cut -d'/' -f1 | head -1)
            fi
            ;;
        macos)
            pid=$(lsof -iTCP:"${port}" -sTCP:LISTEN -n -P 2>/dev/null | awk 'NR==2{print $2}')
            ;;
        *)
            pid=$(lsof -i ":${port}" 2>/dev/null | awk 'NR==2{print $2}')
            ;;
    esac

    echo "$pid"
}

# kill_process_on_port - принудительное завершение процесса на порту
# Usage: kill_process_on_port 8080 "api-gateway"
# Returns: 0 on success, 1 if no process found
kill_process_on_port() {
    local port=$1
    local service_name=${2:-"unknown"}

    local pid
    pid=$(get_pid_on_port "$port")

    if [[ -n "$pid" ]] && [[ "$pid" != "0" ]]; then
        log_warning "Найден процесс на порту $port ($service_name), PID: $pid"

        case "$OS_TYPE" in
            windows)
                # Windows: taskkill требует // для флагов в GitBash
                taskkill //PID "$pid" //F 2>/dev/null || kill -9 "$pid" 2>/dev/null || true
                ;;
            *)
                # Unix-like: стандартный kill
                kill -9 "$pid" 2>/dev/null || true
                ;;
        esac

        log_success "Процесс на порту $port остановлен"
        return 0
    fi

    return 1
}

# wait_for_port - ожидание освобождения или занятия порта
# Usage:
#   wait_for_port 8080 "free" 10   # ждать освобождения порта 10 сек
#   wait_for_port 8080 "used" 30   # ждать когда порт будет занят 30 сек
wait_for_port() {
    local port=$1
    local state=${2:-"used"}  # "used" или "free"
    local timeout=${3:-30}
    local interval=1
    local elapsed=0

    while [[ $elapsed -lt $timeout ]]; do
        if [[ "$state" == "used" ]]; then
            if check_port_listening "$port"; then
                return 0
            fi
        else
            if ! check_port_listening "$port"; then
                return 0
            fi
        fi

        sleep "$interval"
        ((elapsed+=interval))
    done

    return 1
}

##############################################################################
# PROCESS UTILITIES
##############################################################################

# is_process_running - проверка что процесс запущен
# Usage: if is_process_running 12345; then ...
is_process_running() {
    local pid=$1
    kill -0 "$pid" 2>/dev/null
}

# get_process_by_name - получение PID процесса по имени
# Usage: pid=$(get_process_by_name "api-gateway")
# Returns: PID или пустая строка
get_process_by_name() {
    local name=$1

    if command -v pgrep &>/dev/null; then
        pgrep -f "$name" | head -1
    else
        ps aux | grep -v grep | grep "$name" | awk '{print $2}' | head -1
    fi
}

# stop_process - остановка процесса (сначала SIGTERM, потом SIGKILL)
# Usage: stop_process 12345 "api-gateway" 10
stop_process() {
    local pid=$1
    local name=${2:-"process"}
    local timeout=${3:-10}

    if ! is_process_running "$pid"; then
        log_verbose "Процесс $name (PID: $pid) уже не запущен"
        return 0
    fi

    log_info "Останавливаем $name (PID: $pid)..."

    # Сначала SIGTERM
    kill -TERM "$pid" 2>/dev/null || true

    # Ждем завершения
    local elapsed=0
    while [[ $elapsed -lt $timeout ]]; do
        if ! is_process_running "$pid"; then
            log_success "$name остановлен"
            return 0
        fi
        sleep 1
        ((elapsed++))
    done

    # Принудительно SIGKILL
    log_warning "$name не завершился, отправляем SIGKILL..."
    kill -KILL "$pid" 2>/dev/null || true
    sleep 1

    if is_process_running "$pid"; then
        log_error "Не удалось остановить $name"
        return 1
    fi

    log_success "$name остановлен принудительно"
    return 0
}

##############################################################################
# PYTHON VENV UTILITIES
##############################################################################

# activate_venv - активация Python виртуального окружения
# Usage: activate_venv "/path/to/venv"
activate_venv() {
    local venv_path=$1
    local activate_script="$venv_path/$VENV_BIN_DIR/activate"

    if [[ -f "$activate_script" ]]; then
        # shellcheck source=/dev/null
        source "$activate_script"
        return 0
    else
        log_warning "venv activate не найден: $activate_script"
        return 1
    fi
}

# is_venv_active - проверка что venv активирован
# Usage: if is_venv_active; then ...
is_venv_active() {
    [[ -n "${VIRTUAL_ENV:-}" ]]
}

# get_python_version - получение версии Python
# Usage: version=$(get_python_version)
get_python_version() {
    if command -v python3 &>/dev/null; then
        python3 --version 2>/dev/null | grep -oE '[0-9]+\.[0-9]+(\.[0-9]+)?'
    elif command -v python &>/dev/null; then
        python --version 2>/dev/null | grep -oE '[0-9]+\.[0-9]+(\.[0-9]+)?'
    else
        echo ""
    fi
}

##############################################################################
# GO SERVICE UTILITIES
##############################################################################

# get_binary_path - получение пути к Go бинарнику
# Usage: path=$(get_binary_path "api-gateway")
# Requires: BIN_DIR, BIN_EXT должны быть установлены
get_binary_path() {
    local service=$1
    echo "${BIN_DIR:-bin}/cc1c-${service}${BIN_EXT}"
}

# detect_go_service_changes - определение необходимости пересборки
# Usage: status=$(detect_go_service_changes "api-gateway")
# Returns: REBUILD_NEEDED | UP_TO_DATE | NO_SOURCES
# Requires: GO_SERVICES_DIR, get_binary_path, find_newest_file, is_file_newer
detect_go_service_changes() {
    local service=$1
    local service_dir="${GO_SERVICES_DIR:-go-services}/$service"
    local binary_path
    binary_path=$(get_binary_path "$service")

    log_verbose "Проверка изменений для сервиса: $service"

    # Шаг 1: Проверка существования бинарника
    if [[ ! -f "$binary_path" ]]; then
        log_verbose "  Бинарник не найден -> REBUILD_NEEDED"
        echo "REBUILD_NEEDED"
        return
    fi

    # Шаг 2: Найти самый новый .go файл
    local newest_source
    newest_source=$(find_newest_file "$service_dir" "*.go")

    if [[ -z "$newest_source" ]]; then
        log_verbose "  Исходные файлы .go не найдены -> NO_SOURCES"
        echo "NO_SOURCES"
        return
    fi

    log_verbose "  Самый новый .go файл: $newest_source"

    # Шаг 3: Сравнить timestamps
    if is_file_newer "$newest_source" "$binary_path"; then
        log_verbose "  Исходники новее бинарника -> REBUILD_NEEDED"
        echo "REBUILD_NEEDED"
        return
    fi

    # Шаг 4: Проверить shared/ зависимости
    local shared_dir="${GO_SERVICES_DIR:-go-services}/shared"
    if [[ -d "$shared_dir" ]]; then
        local newest_shared
        newest_shared=$(find_newest_file "$shared_dir" "*.go")

        if [[ -n "$newest_shared" ]] && is_file_newer "$newest_shared" "$binary_path"; then
            log_verbose "  shared/ новее бинарника -> REBUILD_NEEDED"
            echo "REBUILD_NEEDED"
            return
        fi
    fi

    log_verbose "  Бинарник актуален -> UP_TO_DATE"
    echo "UP_TO_DATE"
}

##############################################################################
# HEALTH CHECK UTILITIES
##############################################################################

# check_health_endpoint - проверка health endpoint сервиса
# Usage:
#   if check_health_endpoint "http://localhost:8080/health"; then
#       echo "Service is healthy"
#   fi
# Returns: 0 if healthy, 1 otherwise
check_health_endpoint() {
    local url=$1
    local timeout=${2:-5}

    if command -v curl &>/dev/null; then
        # --noproxy '*' важен для WSL где может быть настроен proxy для localhost
        curl --noproxy '*' -sf --max-time "$timeout" "$url" >/dev/null 2>&1
    elif command -v wget &>/dev/null; then
        wget -q --timeout="$timeout" -O /dev/null "$url" 2>/dev/null
    else
        log_error "Ни curl, ни wget не найдены"
        return 1
    fi
}

# wait_for_service - ожидание готовности сервиса
# Usage:
#   wait_for_service "http://localhost:8080/health" 30 "api-gateway"
# Returns: 0 if service is ready, 1 on timeout
wait_for_service() {
    local url=$1
    local timeout=${2:-30}
    local name=${3:-"service"}
    local interval=2
    local elapsed=0

    log_info "Ожидание готовности $name..."

    while [[ $elapsed -lt $timeout ]]; do
        if check_health_endpoint "$url" 2; then
            log_success "$name готов"
            return 0
        fi

        sleep "$interval"
        ((elapsed+=interval))
        log_verbose "  Прошло ${elapsed}с из ${timeout}с..."
    done

    log_error "$name не ответил за ${timeout}с"
    return 1
}

# check_service_status - проверка статуса сервиса по порту и health endpoint
# Usage:
#   status=$(check_service_status 8080 "http://localhost:8080/health" "api-gateway")
#   echo "Status: $status"
# Returns: running | unhealthy | stopped
check_service_status() {
    local port=$1
    local health_url=$2
    local name=${3:-"service"}

    if ! check_port_listening "$port"; then
        echo "stopped"
        return
    fi

    if check_health_endpoint "$health_url" 2; then
        echo "running"
    else
        echo "unhealthy"
    fi
}

##############################################################################
# DOCKER UTILITIES
##############################################################################

# is_docker_installed - проверка установки Docker
# Usage: if is_docker_installed; then ...
is_docker_installed() {
    command -v docker &>/dev/null
}

# is_docker_running - проверка запущен ли Docker daemon
# Usage: if is_docker_running; then ...
is_docker_running() {
    docker info &>/dev/null 2>&1
}

# wait_for_docker - ожидание запуска Docker daemon
# Usage: wait_for_docker 60
wait_for_docker() {
    local timeout=${1:-60}
    local elapsed=0

    log_info "Ожидание запуска Docker daemon..."

    while [[ $elapsed -lt $timeout ]]; do
        if is_docker_running; then
            log_success "Docker daemon запущен"
            return 0
        fi

        sleep 2
        ((elapsed+=2))
    done

    log_error "Docker daemon не запустился за ${timeout}с"
    return 1
}

# is_container_running - проверка запущен ли контейнер
# Usage: if is_container_running "postgres"; then ...
is_container_running() {
    local name=$1
    docker ps --format '{{.Names}}' 2>/dev/null | grep -q "^${name}$"
}

# wait_for_container - ожидание запуска контейнера
# Usage: wait_for_container "postgres" 30
wait_for_container() {
    local name=$1
    local timeout=${2:-30}
    local elapsed=0

    log_info "Ожидание контейнера $name..."

    while [[ $elapsed -lt $timeout ]]; do
        if is_container_running "$name"; then
            log_success "Контейнер $name запущен"
            return 0
        fi

        sleep 2
        ((elapsed+=2))
    done

    log_error "Контейнер $name не запустился за ${timeout}с"
    return 1
}

##############################################################################
# PROJECT DEPENDENCIES CHECK
##############################################################################

# has_python_venv - проверка существования Python venv проекта
# Usage: if has_python_venv; then ...
# Note: требует PROJECT_ROOT
has_python_venv() {
    [[ -d "${PROJECT_ROOT:-}/orchestrator/venv" ]]
}

# has_node_modules - проверка существования node_modules проекта
# Usage: if has_node_modules; then ...
# Note: требует PROJECT_ROOT
has_node_modules() {
    [[ -d "${PROJECT_ROOT:-}/frontend/node_modules" ]]
}

# has_go_modules - проверка скачены ли Go модули
# Usage: if has_go_modules; then ...
has_go_modules() {
    local go_mod_cache="$HOME/go/pkg/mod"
    [[ -d "$go_mod_cache" ]] && [[ -n "$(ls -A "$go_mod_cache" 2>/dev/null)" ]]
}

##############################################################################
# MISE UTILITIES
##############################################################################

# is_mise_installed - проверка установки mise
# Usage: if is_mise_installed; then ...
is_mise_installed() {
    command -v mise &>/dev/null || [[ -x "$HOME/.local/bin/mise" ]]
}

# get_mise_data_dir - получение директории данных mise
# Usage: dir=$(get_mise_data_dir)
get_mise_data_dir() {
    if [[ -n "${MISE_DATA_DIR:-}" ]]; then
        echo "$MISE_DATA_DIR"
    elif [[ -d "$HOME/.local/share/mise" ]]; then
        echo "$HOME/.local/share/mise"
    elif [[ -d "$HOME/.mise" ]]; then
        echo "$HOME/.mise"
    else
        echo ""
    fi
}

# get_mise_config_dir - получение директории конфигурации mise
# Usage: dir=$(get_mise_config_dir)
get_mise_config_dir() {
    if [[ -n "${MISE_CONFIG_DIR:-}" ]]; then
        echo "$MISE_CONFIG_DIR"
    elif [[ -d "$HOME/.config/mise" ]]; then
        echo "$HOME/.config/mise"
    else
        echo ""
    fi
}

##############################################################################
# End of services.sh
##############################################################################
