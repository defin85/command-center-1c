#!/bin/bash

##############################################################################
# CommandCenter1C - Service Lifecycle Management Library
##############################################################################
#
# Унифицированные функции управления жизненным циклом сервисов:
# запуск, остановка, перезапуск с учетом категорий (Python, Go, Frontend).
#
# Usage:
#   source scripts/lib/lifecycle.sh
#
# Dependencies:
#   - scripts/lib/core.sh
#   - scripts/lib/platform.sh
#   - scripts/lib/files.sh
#   - scripts/lib/services.sh
#
# Exports:
#   Lifecycle: start_service, stop_service, restart_service
#   Batch: start_services, stop_services, restart_services
#   Category starters: _start_python_service, _start_go_service, _start_frontend_service
#
# Required Variables (set before calling functions):
#   PROJECT_ROOT       - корень проекта
#   PIDS_DIR           - директория для PID файлов
#   LOGS_DIR           - директория для логов
#   BIN_DIR            - директория с Go бинарниками
#
# Version: 1.0.0
##############################################################################

# Проверка зависимостей
if [[ -z "${CC1C_LIB_CORE_LOADED:-}" ]]; then
    echo "ERROR: lifecycle.sh requires core.sh to be loaded first" >&2
    return 1
fi

if [[ -z "${CC1C_LIB_SERVICES_LOADED:-}" ]]; then
    echo "ERROR: lifecycle.sh requires services.sh to be loaded first" >&2
    return 1
fi

# Предотвращение повторного sourcing
if [[ -n "${CC1C_LIB_LIFECYCLE_LOADED:-}" ]]; then
    return 0
fi
CC1C_LIB_LIFECYCLE_LOADED=true

##############################################################################
# SERVICE CONFIGURATION
##############################################################################

# Категории сервисов: python, go, frontend, external
declare -gA SERVICE_CATEGORIES=(
    ["orchestrator"]="python"
    ["event-subscriber"]="python"
    ["api-gateway"]="go"
    ["worker"]="go"
    ["frontend"]="frontend"
    ["ras"]="external"
)

# Порядок запуска (сначала backend, потом frontend)
declare -ga SERVICE_START_ORDER=(
    orchestrator
    event-subscriber
    api-gateway
    worker
    frontend
)

# Порядок остановки (обратный запуску)
declare -ga SERVICE_STOP_ORDER=(
    frontend
    worker
    api-gateway
    event-subscriber
    orchestrator
)

# Порты сервисов для health check
declare -gA SERVICE_PORTS=(
    ["orchestrator"]="${ORCHESTRATOR_PORT:-8200}"
    ["api-gateway"]="${API_GATEWAY_PORT:-8180}"
    ["frontend"]="${FRONTEND_PORT:-5173}"
)

# Таймаут остановки для сервисов (секунды)
declare -gA SERVICE_STOP_TIMEOUT=(
    ["orchestrator"]=15
    ["event-subscriber"]=10
    ["api-gateway"]=10
    ["worker"]=15
    ["frontend"]=5
    ["ras"]=10
)

##############################################################################
# STOP SERVICE
##############################################################################

# stop_service - остановка сервиса по имени
# Usage: stop_service "orchestrator"
# Returns: 0 если успешно, 1 при ошибке
stop_service() {
    local service_name=$1
    local pid_file="${PIDS_DIR:-pids}/${service_name}.pid"
    local timeout="${SERVICE_STOP_TIMEOUT[$service_name]:-10}"

    # Проверка что PID файл существует
    if [[ ! -f "$pid_file" ]]; then
        log_verbose "$service_name: PID файл не найден"
        return 0
    fi

    local pid
    pid=$(cat "$pid_file" 2>/dev/null)

    # Проверка что PID не пустой
    if [[ -z "$pid" ]]; then
        log_verbose "$service_name: PID файл пуст"
        rm -f "$pid_file"
        return 0
    fi

    # Проверка что процесс запущен
    if ! is_process_running "$pid"; then
        log_verbose "$service_name: процесс уже остановлен (PID: $pid)"
        rm -f "$pid_file"
        return 0
    fi

    log_info "Остановка $service_name (PID: $pid)..."

    # Graceful shutdown (SIGTERM)
    kill -TERM "$pid" 2>/dev/null || true

    # Ожидание завершения
    local elapsed=0
    while is_process_running "$pid" && [[ $elapsed -lt $timeout ]]; do
        sleep 1
        ((elapsed++))
    done

    # Если не завершился - SIGKILL
    if is_process_running "$pid"; then
        log_warning "$service_name не завершился gracefully, принудительная остановка..."
        kill -KILL "$pid" 2>/dev/null || true
        sleep 1
    fi

    # Финальная проверка
    if is_process_running "$pid"; then
        log_error "Не удалось остановить $service_name"
        return 1
    fi

    log_success "$service_name остановлен"
    rm -f "$pid_file"
    return 0
}

##############################################################################
# START SERVICE
##############################################################################

# start_service - запуск сервиса по имени
# Usage: start_service "orchestrator"
# Returns: 0 если успешно, 1 при ошибке
start_service() {
    local service_name=$1

    # Проверка что сервис известен
    local category="${SERVICE_CATEGORIES[$service_name]:-}"
    if [[ -z "$category" ]]; then
        log_error "Неизвестный сервис: $service_name"
        return 1
    fi

    log_info "Запуск $service_name (категория: $category)..."

    # Создание директорий если нужно
    ensure_dir "${PIDS_DIR:-pids}"
    ensure_dir "${LOGS_DIR:-logs}"

    # Очистка старого лог файла
    local log_file="${LOGS_DIR:-logs}/${service_name}.log"
    > "$log_file"

    # Запуск в зависимости от категории
    case "$category" in
        python)
            if ! _start_python_service "$service_name"; then
                log_error "Не удалось запустить $service_name"
                return 1
            fi
            ;;
        go)
            if ! _start_go_service "$service_name"; then
                log_error "Не удалось запустить $service_name"
                return 1
            fi
            ;;
        frontend)
            if ! _start_frontend_service; then
                log_error "Не удалось запустить $service_name"
                return 1
            fi
            ;;
        external)
            if ! _start_external_service "$service_name"; then
                log_error "Не удалось запустить $service_name"
                return 1
            fi
            ;;
        *)
            log_error "Неизвестная категория сервиса: $category"
            return 1
            ;;
    esac

    # Сохраняем PID
    local pid_file="${PIDS_DIR:-pids}/${service_name}.pid"
    echo "$LAST_SERVICE_PID" > "$pid_file"

    # Проверка что процесс запустился
    sleep 2
    if is_process_running "$LAST_SERVICE_PID"; then
        log_success "$service_name запущен (PID: $LAST_SERVICE_PID)"
        return 0
    else
        log_error "$service_name не удалось запустить"
        log_warning "Проверьте логи: $log_file"
        rm -f "$pid_file"
        return 1
    fi
}

# Глобальная переменная для хранения PID последнего запущенного процесса
LAST_SERVICE_PID=""

##############################################################################
# PYTHON SERVICE STARTERS
##############################################################################

# _start_python_service - запуск Python сервиса (Django/Celery)
# Usage: _start_python_service "orchestrator"
# Sets: LAST_SERVICE_PID
# Returns: 0 если успешно, 1 при ошибке (UNIX конвенция)
_start_python_service() {
    local service_name=$1
    local log_file="${LOGS_DIR:-logs}/${service_name}.log"
    local orchestrator_dir="${PROJECT_ROOT:-}/orchestrator"

    # Проверка и активация venv
    if [[ ! -d "$orchestrator_dir/venv" ]]; then
        log_error "Python venv не найден: $orchestrator_dir/venv"
        return 1
    fi

    # Переходим в директорию и активируем venv
    cd "$orchestrator_dir" || return 1
    activate_venv "$orchestrator_dir/venv"

    case "$service_name" in
        orchestrator)
            local port="${ORCHESTRATOR_PORT:-8200}"
            nohup daphne -b 0.0.0.0 -p "$port" config.asgi:application > "$log_file" 2>&1 &
            LAST_SERVICE_PID=$!
            ;;
        event-subscriber)
            nohup python manage.py run_event_subscriber > "$log_file" 2>&1 &
            LAST_SERVICE_PID=$!
            ;;
        *)
            log_error "Неизвестный Python сервис: $service_name"
            cd "$PROJECT_ROOT" || true
            return 1
            ;;
    esac

    cd "$PROJECT_ROOT" || true
    return 0
}

##############################################################################
# GO SERVICE STARTERS
##############################################################################

# _start_go_service - запуск Go сервиса с опциональным smart rebuild
# Usage: _start_go_service "api-gateway"
# Environment:
#   SKIP_GO_REBUILD=true  - пропустить проверку/пересборку (если уже сделано в Phase 1)
# Sets: LAST_SERVICE_PID
# Returns: 0 если успешно, 1 при ошибке (UNIX конвенция)
_start_go_service() {
    local service_name=$1
    local log_file="${LOGS_DIR:-logs}/${service_name}.log"
    local binary_path
    binary_path=$(get_binary_path "$service_name")

    # Smart rebuild: проверяем нужна ли пересборка (если не отключено)
    if [[ "${SKIP_GO_REBUILD:-false}" != "true" ]]; then
        local rebuild_status
        rebuild_status=$(detect_go_service_changes "$service_name")

        case "$rebuild_status" in
            REBUILD_NEEDED)
                log_info "Обнаружены изменения в $service_name, пересборка..."
                if ! _rebuild_go_service "$service_name"; then
                    log_error "Ошибка сборки $service_name"
                    return 1
                fi
                log_success "Пересборка $service_name завершена"
                ;;
            NO_SOURCES)
                if [[ ! -f "$binary_path" ]]; then
                    log_warning "Бинарник не найден и исходники отсутствуют: $service_name"
                    return 1
                fi
                ;;
            UP_TO_DATE)
                log_verbose "$service_name: бинарник актуален"
                ;;
        esac
    fi

    # Проверка что бинарник существует
    if [[ ! -f "$binary_path" ]]; then
        log_error "Бинарник не найден: $binary_path"
        return 1
    fi

    # Запуск
    nohup "$binary_path" > "$log_file" 2>&1 &
    LAST_SERVICE_PID=$!
    return 0
}

# _rebuild_go_service - пересборка Go сервиса
# Usage: _rebuild_go_service "api-gateway"
# Returns: 0 если успешно, 1 при ошибке
_rebuild_go_service() {
    local service_name=$1
    local binary_path
    binary_path=$(get_binary_path "$service_name")
    local service_dir="${PROJECT_ROOT:-}/go-services/$service_name"

    if [[ ! -d "$service_dir" ]]; then
        log_error "Директория сервиса не найдена: $service_dir"
        return 1
    fi

    # Создание директории bin если нужно
    ensure_dir "$(dirname "$binary_path")"

    cd "$service_dir" || return 1

    if go build -o "$binary_path" ./cmd/main.go 2>&1; then
        cd "$PROJECT_ROOT" || true
        return 0
    else
        cd "$PROJECT_ROOT" || true
        return 1
    fi
}

##############################################################################
# FRONTEND SERVICE STARTERS
##############################################################################

# _start_frontend_service - запуск React frontend
# Usage: _start_frontend_service
# Sets: LAST_SERVICE_PID
# Returns: 0 если успешно, 1 при ошибке (UNIX конвенция)
_start_frontend_service() {
    local log_file="${LOGS_DIR:-logs}/frontend.log"
    local frontend_dir="${PROJECT_ROOT:-}/frontend"

    if [[ ! -d "$frontend_dir" ]]; then
        log_error "Frontend директория не найдена: $frontend_dir"
        return 1
    fi

    cd "$frontend_dir" || return 1

    # Проверка node_modules
    if [[ ! -d "node_modules" ]]; then
        log_warning "node_modules не найден, запуск npm install..."
        npm install || {
            log_error "npm install завершился с ошибкой"
            cd "$PROJECT_ROOT" || true
            return 1
        }
    fi

    nohup npm run dev > "$log_file" 2>&1 &
    LAST_SERVICE_PID=$!

    cd "$PROJECT_ROOT" || true
    return 0
}

##############################################################################
# EXTERNAL SERVICE STARTERS
##############################################################################

# _start_external_service - запуск внешних сервисов (RAS и т.д.)
# Usage: _start_external_service "ras"
# Sets: LAST_SERVICE_PID
# Returns: 0 если успешно, 1 при ошибке (UNIX конвенция)
_start_external_service() {
    local service_name=$1
    local log_file="${LOGS_DIR:-logs}/${service_name}.log"

    case "$service_name" in
        ras)
            # RAS может работать как Windows служба
            if [[ "${RAS_SKIP_START:-false}" == "true" ]]; then
                log_info "RAS: пропущен (работает как Windows служба)"
                LAST_SERVICE_PID=1  # Фиктивный PID
                return 0
            fi

            if [[ -z "${PLATFORM_1C_BIN_PATH:-}" ]]; then
                log_error "PLATFORM_1C_BIN_PATH не задан в .env.local"
                return 1
            fi

            local ras_exe="$PLATFORM_1C_BIN_PATH/ras.exe"
            if [[ ! -f "$ras_exe" ]]; then
                log_error "ras.exe не найден: $ras_exe"
                return 1
            fi

            local port="${RAS_PORT:-1545}"
            nohup "$ras_exe" cluster --port="$port" > "$log_file" 2>&1 &
            LAST_SERVICE_PID=$!
            ;;
        *)
            log_error "Неизвестный внешний сервис: $service_name"
            return 1
            ;;
    esac

    return 0
}

##############################################################################
# RESTART SERVICE
##############################################################################

# restart_service - перезапуск сервиса
# Usage: restart_service "orchestrator"
# Returns: 0 если успешно, 1 при ошибке
restart_service() {
    local service_name=$1

    log_step "Перезапуск сервиса: $service_name"

    # Остановка
    if ! stop_service "$service_name"; then
        log_warning "Не удалось корректно остановить $service_name"
    fi

    # Небольшая пауза для освобождения ресурсов
    sleep 1

    # Запуск
    if start_service "$service_name"; then
        log_success "$service_name успешно перезапущен"
        return 0
    else
        log_error "Не удалось перезапустить $service_name"
        return 1
    fi
}

##############################################################################
# BATCH OPERATIONS
##############################################################################

# start_services - запуск нескольких сервисов
# Usage: start_services "orchestrator" "api-gateway" "frontend"
# Usage: start_services  # без аргументов - все по SERVICE_START_ORDER
# Returns: 0 если все успешно, 1 если хотя бы один не запустился
start_services() {
    local services=("$@")
    local failed=0

    # Если нет аргументов - использовать SERVICE_START_ORDER
    if [[ ${#services[@]} -eq 0 ]]; then
        services=("${SERVICE_START_ORDER[@]}")
    fi

    for service in "${services[@]}"; do
        if ! start_service "$service"; then
            ((failed++))
        fi
    done

    return $((failed > 0 ? 1 : 0))
}

# stop_services - остановка нескольких сервисов
# Usage: stop_services "frontend" "api-gateway" "orchestrator"
# Usage: stop_services  # без аргументов - все по SERVICE_STOP_ORDER
# Returns: 0 если все успешно, 1 если хотя бы один не остановился
stop_services() {
    local services=("$@")
    local failed=0

    # Если нет аргументов - использовать SERVICE_STOP_ORDER
    if [[ ${#services[@]} -eq 0 ]]; then
        services=("${SERVICE_STOP_ORDER[@]}")
    fi

    for service in "${services[@]}"; do
        if ! stop_service "$service"; then
            ((failed++))
        fi
    done

    return $((failed > 0 ? 1 : 0))
}

# restart_services - перезапуск нескольких сервисов
# Usage: restart_services "orchestrator" "api-gateway"
# Returns: 0 если все успешно, 1 если хотя бы один не перезапустился
restart_services() {
    local services=("$@")
    local failed=0

    for service in "${services[@]}"; do
        if ! restart_service "$service"; then
            ((failed++))
        fi
    done

    return $((failed > 0 ? 1 : 0))
}

##############################################################################
# SERVICE STATUS
##############################################################################

# get_service_status - получение статуса сервиса
# Usage: status=$(get_service_status "orchestrator")
# Returns: running | stopped | unknown
get_service_status() {
    local service_name=$1
    local pid_file="${PIDS_DIR:-pids}/${service_name}.pid"

    if [[ ! -f "$pid_file" ]]; then
        echo "stopped"
        return
    fi

    local pid
    pid=$(cat "$pid_file" 2>/dev/null)

    if [[ -z "$pid" ]]; then
        echo "stopped"
        return
    fi

    if is_process_running "$pid"; then
        echo "running"
    else
        echo "stopped"
    fi
}

# is_service_running - проверка запущен ли сервис
# Usage: if is_service_running "orchestrator"; then ...
is_service_running() {
    local service_name=$1
    [[ "$(get_service_status "$service_name")" == "running" ]]
}

# get_service_pid - получение PID сервиса
# Usage: pid=$(get_service_pid "orchestrator")
get_service_pid() {
    local service_name=$1
    local pid_file="${PIDS_DIR:-pids}/${service_name}.pid"

    if [[ -f "$pid_file" ]]; then
        cat "$pid_file" 2>/dev/null
    fi
}

##############################################################################
# UTILITY FUNCTIONS
##############################################################################

# get_service_category - получение категории сервиса
# Usage: category=$(get_service_category "orchestrator")
get_service_category() {
    local service_name=$1
    echo "${SERVICE_CATEGORIES[$service_name]:-unknown}"
}

# get_service_port - получение порта сервиса
# Usage: port=$(get_service_port "orchestrator")
get_service_port() {
    local service_name=$1
    echo "${SERVICE_PORTS[$service_name]:-}"
}

# list_services - вывод списка всех известных сервисов
# Usage: list_services
list_services() {
    echo "Available services:"
    for service in "${SERVICE_START_ORDER[@]}"; do
        local category="${SERVICE_CATEGORIES[$service]:-unknown}"
        local port="${SERVICE_PORTS[$service]:-N/A}"
        printf "  %-20s [%s] port: %s\n" "$service" "$category" "$port"
    done
}

##############################################################################
# End of lifecycle.sh
##############################################################################
