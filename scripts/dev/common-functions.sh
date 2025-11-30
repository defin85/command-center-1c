#!/bin/bash

##############################################################################
# CommandCenter1C - Common Functions Library
##############################################################################
# Общая библиотека функций для DevOps скриптов
#
# Usage:
#   source scripts/dev/common-functions.sh
#
# Functions:
#   - Utility: print_status, verbose_log, print_header
#   - Change Detection: detect_go_service_changes
#   - Smart Rebuild: smart_rebuild_services, rebuild_go_services
##############################################################################

# Предотвращение повторного sourcing
if [ -n "$COMMON_FUNCTIONS_LOADED" ]; then
    return 0
fi
COMMON_FUNCTIONS_LOADED=true

##############################################################################
# [СЕКЦИЯ 0: OS DETECTION]
##############################################################################
# Определение операционной среды и экспорт ОС-специфичных переменных
# ДОЛЖНА быть первой секцией после guard clause
##############################################################################

# detect_os - определение типа операционной системы
# Usage: os=$(detect_os)
# Returns: windows | wsl | linux | macos | unknown
detect_os() {
    local os_type=""

    case "$(uname -s)" in
        MINGW*|MSYS*|CYGWIN*)
            os_type="windows"
            ;;
        Linux)
            # Проверка WSL через /proc/version
            if grep -qiE "(microsoft|wsl)" /proc/version 2>/dev/null; then
                os_type="wsl"
            else
                os_type="linux"
            fi
            ;;
        Darwin)
            os_type="macos"
            ;;
        *)
            # Fallback - попытка через $OSTYPE
            case "$OSTYPE" in
                msys*|cygwin*|mingw*)
                    os_type="windows"
                    ;;
                linux*)
                    os_type="linux"
                    ;;
                darwin*)
                    os_type="macos"
                    ;;
                *)
                    os_type="unknown"
                    ;;
            esac
            ;;
    esac

    echo "$os_type"
}

# init_os_environment - инициализация ОС-специфичных переменных
# Вызывается автоматически при source common-functions.sh
init_os_environment() {
    # Определить тип ОС
    OS_TYPE=$(detect_os)
    export OS_TYPE

    # Расширение бинарных файлов
    case "$OS_TYPE" in
        windows)
            BIN_EXT=".exe"
            ;;
        *)
            BIN_EXT=""
            ;;
    esac
    export BIN_EXT

    # Путь к venv activate (относительно venv/)
    case "$OS_TYPE" in
        windows)
            VENV_BIN_DIR="Scripts"
            ;;
        *)
            VENV_BIN_DIR="bin"
            ;;
    esac
    export VENV_BIN_DIR
}

# check_port_listening - кросс-платформенная проверка занятости порта
# Usage: check_port_listening PORT
# Returns: 0 if port is listening, 1 otherwise
check_port_listening() {
    local port=$1

    case "$OS_TYPE" in
        windows)
            netstat -ano 2>/dev/null | grep -q ":${port}.*LISTENING"
            ;;
        wsl|linux)
            # ss более современная альтернатива netstat
            if command -v ss &>/dev/null; then
                ss -tlnp 2>/dev/null | grep -q ":${port} "
            else
                netstat -tlnp 2>/dev/null | grep -q ":${port} "
            fi
            ;;
        macos)
            lsof -iTCP:${port} -sTCP:LISTEN -n -P 2>/dev/null | grep -q LISTEN
            ;;
        *)
            # Fallback - пробуем lsof
            lsof -i ":${port}" 2>/dev/null | grep -q LISTEN
            ;;
    esac
}

# get_pid_on_port - получение PID процесса на порту
# Usage: pid=$(get_pid_on_port PORT)
# Returns: PID or empty string
get_pid_on_port() {
    local port=$1
    local pid=""

    case "$OS_TYPE" in
        windows)
            pid=$(netstat -ano 2>/dev/null | grep ":${port}.*LISTENING" | awk '{print $5}' | head -1)
            ;;
        wsl|linux)
            # ss -tlnp показывает PID в формате "users:(("name",pid=123,fd=4))"
            if command -v ss &>/dev/null; then
                pid=$(ss -tlnp 2>/dev/null | grep ":${port} " | sed -E 's/.*pid=([0-9]+).*/\1/' | head -1)
            else
                pid=$(netstat -tlnp 2>/dev/null | grep ":${port} " | awk '{print $7}' | cut -d'/' -f1 | head -1)
            fi
            ;;
        macos)
            pid=$(lsof -iTCP:${port} -sTCP:LISTEN -n -P 2>/dev/null | awk 'NR==2{print $2}')
            ;;
        *)
            pid=$(lsof -i ":${port}" 2>/dev/null | awk 'NR==2{print $2}')
            ;;
    esac

    echo "$pid"
}

# kill_process_on_port - принудительное завершение процесса на порту
# Usage: kill_process_on_port PORT SERVICE_NAME
# Returns: 0 on success, 1 if no process found
kill_process_on_port() {
    local port=$1
    local service_name=$2

    local pid=$(get_pid_on_port "$port")

    if [ -n "$pid" ] && [ "$pid" != "0" ]; then
        echo -e "${YELLOW}⚠️  Найден процесс на порту $port ($service_name), PID: $pid${NC}"

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

        echo -e "${GREEN}✓ Процесс на порту $port остановлен${NC}"
        return 0
    fi

    return 1
}

# activate_venv - кросс-платформенная активация Python venv
# Usage: activate_venv VENV_PATH
# Example: activate_venv "$PROJECT_ROOT/orchestrator/venv"
activate_venv() {
    local venv_path=$1
    local activate_script="$venv_path/$VENV_BIN_DIR/activate"

    if [ -f "$activate_script" ]; then
        source "$activate_script"
        return 0
    else
        echo -e "${YELLOW}⚠️  Warning: venv activate не найден: $activate_script${NC}"
        return 1
    fi
}

# get_binary_path - получение пути к бинарнику Go сервиса
# Usage: path=$(get_binary_path SERVICE_NAME)
# Returns: полный путь к бинарнику с правильным расширением
get_binary_path() {
    local service=$1
    echo "$BIN_DIR/cc1c-${service}${BIN_EXT}"
}

# get_file_mtime - кросс-платформенное получение mtime файла (Unix timestamp)
# Usage: mtime=$(get_file_mtime "/path/to/file")
# Returns: Unix timestamp или пустую строку при ошибке
get_file_mtime() {
    local file_path=$1

    if [ ! -f "$file_path" ]; then
        echo ""
        return 1
    fi

    case "$OS_TYPE" in
        macos)
            # BSD stat: -f %m returns modification time as Unix timestamp
            stat -f %m "$file_path" 2>/dev/null
            ;;
        *)
            # GNU stat (Linux, WSL, Windows/MSYS): -c %Y
            stat -c %Y "$file_path" 2>/dev/null
            ;;
    esac
}

# find_newest_file - кросс-платформенный поиск самого нового файла
# Usage: newest=$(find_newest_file "/path/to/dir" "*.go")
# Returns: путь к самому новому файлу или пустую строку
find_newest_file() {
    local search_dir=$1
    local pattern=$2
    local newest_file=""
    local newest_time=0

    # Используем find + while read для кросс-платформенности
    # Избегаем -printf (GNU specific)
    while IFS= read -r -d '' file; do
        local file_time=$(get_file_mtime "$file")
        if [ -n "$file_time" ] && [ "$file_time" -gt "$newest_time" ]; then
            newest_time="$file_time"
            newest_file="$file"
        fi
    done < <(find "$search_dir" -name "$pattern" -type f -print0 2>/dev/null)

    echo "$newest_file"
}

# is_file_newer - кросс-платформенная проверка "файл A новее файла B"
# Usage: if is_file_newer "/path/a" "/path/b"; then ...
# Returns: 0 if file_a is newer than file_b, 1 otherwise
is_file_newer() {
    local file_a=$1
    local file_b=$2

    # Используем встроенную проверку bash -nt (newer than)
    # Это работает на всех платформах
    if [ "$file_a" -nt "$file_b" ]; then
        return 0
    else
        return 1
    fi
}

# Автоматическая инициализация при source
init_os_environment

##############################################################################
# [СЕКЦИЯ 1: CONSTANTS & CONFIGURATION]
##############################################################################

# Определить PROJECT_ROOT относительно скрипта
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

# Директории
GO_SERVICES_DIR="$PROJECT_ROOT/go-services"
BIN_DIR="$PROJECT_ROOT/bin"
PIDS_DIR="$PROJECT_ROOT/pids"
LOGS_DIR="$PROJECT_ROOT/logs"

# Список Go сервисов (в порядке приоритета)
# Week 4+: ras-adapter заменил cluster-service (архивирован)
GO_SERVICES=("api-gateway" "worker" "ras-adapter" "batch-service")

# Цвета для вывода
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

##############################################################################
# [СЕКЦИЯ 2: UTILITY FUNCTIONS]
##############################################################################

# print_header - печать заголовка секции
# Usage: print_header "Message"
print_header() {
    local message=$1
    echo -e "${BLUE}========================================${NC}"
    echo -e "${BLUE}  ${message}${NC}"
    echo -e "${BLUE}========================================${NC}"
    echo ""
}

# print_status - печать статуса с цветом и иконкой
# Usage: print_status "success|warning|error|info" "Message"
print_status() {
    local status=$1
    local message=$2

    case "$status" in
        success)
            echo -e "${GREEN}✓${NC} ${message}"
            ;;
        warning)
            echo -e "${YELLOW}⚠️${NC} ${message}"
            ;;
        error)
            echo -e "${RED}✗${NC} ${message}"
            ;;
        info)
            echo -e "${BLUE}ℹ${NC} ${message}"
            ;;
        *)
            echo "$message"
            ;;
    esac
}

# verbose_log - логирование в verbose режиме
# Usage: verbose_log "Message"
# Требует: VERBOSE переменная должна быть установлена
verbose_log() {
    if [ "$VERBOSE" = true ]; then
        echo -e "${YELLOW}[VERBOSE]${NC} $1" >&2
    fi
}

##############################################################################
# [СЕКЦИЯ 3: CHANGE DETECTION]
##############################################################################

# detect_go_service_changes - определение необходимости пересборки сервиса
# Usage: status=$(detect_go_service_changes "service-name")
# Returns: REBUILD_NEEDED | UP_TO_DATE | NO_SOURCES
detect_go_service_changes() {
    local service=$1
    local service_dir="$GO_SERVICES_DIR/$service"
    local binary_path=$(get_binary_path "$service")

    verbose_log "Проверка изменений для сервиса: $service"
    verbose_log "  Директория: $service_dir"
    verbose_log "  Бинарник: $binary_path"

    # Шаг 1: Проверка существования бинарника
    if [ ! -f "$binary_path" ]; then
        verbose_log "  Бинарник не найден -> REBUILD_NEEDED"
        echo "REBUILD_NEEDED"
        return
    fi

    # Шаг 2: Найти самый новый .go файл в директории сервиса
    # Используем кросс-платформенную функцию (работает на macOS, Linux, Windows)
    local newest_source=$(find_newest_file "$service_dir" "*.go")

    if [ -z "$newest_source" ]; then
        verbose_log "  Исходные файлы .go не найдены -> NO_SOURCES"
        echo "NO_SOURCES"
        return
    fi

    verbose_log "  Самый новый .go файл: $newest_source"

    # Шаг 3: Сравнить timestamps (используем -nt для "newer than")
    if is_file_newer "$newest_source" "$binary_path"; then
        verbose_log "  Исходники новее бинарника -> REBUILD_NEEDED"
        echo "REBUILD_NEEDED"
        return
    fi

    # Шаг 4: Проверить shared/ зависимости
    if [ -d "$GO_SERVICES_DIR/shared" ]; then
        local newest_shared=$(find_newest_file "$GO_SERVICES_DIR/shared" "*.go")

        if [ -n "$newest_shared" ]; then
            verbose_log "  Самый новый shared/ файл: $newest_shared"

            if is_file_newer "$newest_shared" "$binary_path"; then
                verbose_log "  shared/ новее бинарника -> REBUILD_NEEDED"
                echo "REBUILD_NEEDED"
                return
            fi
        fi
    fi

    verbose_log "  Бинарник актуален -> UP_TO_DATE"
    echo "UP_TO_DATE"
}

##############################################################################
# [СЕКЦИЯ 4: SMART REBUILD]
##############################################################################

# smart_rebuild_services - умная пересборка с определением изменений
# Usage: smart_rebuild_services
# Требует: FORCE_REBUILD, NO_REBUILD, PARALLEL_BUILD, REBUILD_SERVICES, SKIPPED_SERVICES
# Returns: 0 on success, 1 on error
smart_rebuild_services() {
    print_header "Проверка необходимости пересборки Go сервисов"

    # Если --no-rebuild, пропускаем
    if [ "$NO_REBUILD" = true ]; then
        print_status "info" "Пересборка отключена (--no-rebuild)"
        echo ""
        return 0
    fi

    # Если --force-rebuild, пересобрать все
    if [ "$FORCE_REBUILD" = true ]; then
        print_status "info" "Принудительная пересборка всех Go сервисов (--force-rebuild)"
        REBUILD_SERVICES=("${GO_SERVICES[@]}")

        rebuild_go_services
        return $?
    fi

    # Умное определение изменений
    print_status "info" "Определение изменений в Go коде..."
    echo ""

    local count=0
    for service in "${GO_SERVICES[@]}"; do
        ((count++))
        echo -e "${BLUE}[$count/${#GO_SERVICES[@]}]${NC} Проверка $service..."

        local status=$(detect_go_service_changes "$service")

        case "$status" in
            REBUILD_NEEDED)
                print_status "warning" "Обнаружены изменения → требуется пересборка"
                REBUILD_SERVICES+=("$service")
                ;;
            UP_TO_DATE)
                print_status "success" "Бинарник актуален → пересборка не требуется"
                SKIPPED_SERVICES+=("$service")
                ;;
            NO_SOURCES)
                print_status "warning" "Исходники не найдены → пересборка не требуется"
                SKIPPED_SERVICES+=("$service")
                ;;
            *)
                print_status "error" "Неизвестный статус: $status"
                ;;
        esac
        echo ""
    done

    # Проверка изменений в shared/ (для всех сервисов сразу)
    if [ -d "$GO_SERVICES_DIR/shared" ]; then
        echo -e "${BLUE}Проверка shared/ модулей...${NC}"

        # Используем кросс-платформенную функцию
        local newest_shared=$(find_newest_file "$GO_SERVICES_DIR/shared" "*.go")

        if [ -n "$newest_shared" ]; then
            # Найти самый старый бинарник
            local oldest_binary=""
            local oldest_time=""

            for service in "${GO_SERVICES[@]}"; do
                local binary_path=$(get_binary_path "$service")

                if [ -f "$binary_path" ]; then
                    # Используем кросс-платформенную функцию
                    local binary_time=$(get_file_mtime "$binary_path")
                    binary_time=${binary_time:-0}

                    if [ -z "$oldest_time" ] || [ "$binary_time" -lt "$oldest_time" ]; then
                        oldest_binary="$binary_path"
                        oldest_time="$binary_time"
                    fi
                fi
            done

            # Если есть бинарники И shared/ новее самого старого бинарника
            if [ -n "$oldest_binary" ] && is_file_newer "$newest_shared" "$oldest_binary"; then
                print_status "warning" "Обнаружены изменения в shared/ модулях"
                echo -e "${YELLOW}   Все Go сервисы будут пересобраны${NC}"

                # Добавить все сервисы для пересборки (уникально)
                REBUILD_SERVICES=()
                for service in "${GO_SERVICES[@]}"; do
                    REBUILD_SERVICES+=("$service")
                done

                # Очистить SKIPPED_SERVICES
                SKIPPED_SERVICES=()
                echo ""
            # Если бинарников нет вообще - не делать ничего (уже есть в REBUILD_SERVICES)
            elif [ -z "$oldest_binary" ]; then
                verbose_log "shared/ проверка пропущена - бинарники отсутствуют"
            else
                print_status "success" "shared/ модули актуальны"
                echo ""
            fi
        fi
    fi

    # Если есть что пересобирать
    if [ ${#REBUILD_SERVICES[@]} -gt 0 ]; then
        rebuild_go_services
        return $?
    else
        print_status "success" "Все Go сервисы актуальны, пересборка не требуется"
        echo ""
        return 0
    fi
}

# rebuild_go_services - пересборка Go сервисов через scripts/build.sh
# Usage: rebuild_go_services
# Требует: REBUILD_SERVICES, PARALLEL_BUILD
# Returns: 0 on success, 1 on error
rebuild_go_services() {
    echo -e "${BLUE}Пересборка Go сервисов...${NC}"
    echo ""

    # Проверить что build.sh существует
    if [ ! -f "$PROJECT_ROOT/scripts/build.sh" ]; then
        print_status "error" "Скрипт build.sh не найден: $PROJECT_ROOT/scripts/build.sh"
        return 1
    fi

    # Собрать параметры для build.sh
    local build_args=""

    # Если только один сервис, использовать --service=
    if [ ${#REBUILD_SERVICES[@]} -eq 1 ]; then
        build_args="--service=${REBUILD_SERVICES[0]}"

        print_status "info" "Пересборка сервиса: ${REBUILD_SERVICES[0]}"
        echo ""

        # Запустить build.sh
        if bash "$PROJECT_ROOT/scripts/build.sh" $build_args; then
            print_status "success" "Сервис ${REBUILD_SERVICES[0]} успешно пересобран"
            echo ""
            return 0
        else
            print_status "error" "Ошибка при пересборке сервиса ${REBUILD_SERVICES[0]}"
            return 1
        fi
    else
        # Несколько сервисов - собрать все (build.sh не поддерживает выборочную сборку нескольких)
        # Используем --parallel если флаг установлен
        if [ "$PARALLEL_BUILD" = true ]; then
            build_args="--parallel"
        fi

        print_status "info" "Пересборка сервисов: ${REBUILD_SERVICES[*]}"
        echo ""

        # Запустить build.sh
        if bash "$PROJECT_ROOT/scripts/build.sh" $build_args; then
            print_status "success" "Все сервисы успешно пересобраны"
            echo ""
            return 0
        else
            print_status "error" "Ошибка при пересборке сервисов"
            return 1
        fi
    fi
}

##############################################################################
# [СЕКЦИЯ 5: ENVIRONMENT LOADING]
##############################################################################

# load_env_file - загрузка переменных окружения из .env.local
# Usage: load_env_file
# Гарантирует что Go сервисы получают те же настройки что и Django
load_env_file() {
    local env_file="$PROJECT_ROOT/.env.local"

    if [ -f "$env_file" ]; then
        echo "📋 Загрузка переменных окружения из .env.local..."

        # Export variables from .env.local
        # - Skip comments (lines starting with #)
        # - Skip empty lines
        # - Remove Windows line endings (\r)
        # - Use set -a to automatically export all variables
        set -a
        source <(grep -v '^#' "$env_file" | grep -v '^[[:space:]]*$' | sed 's/\r$//')
        set +a

        echo "✓ Переменные окружения загружены (JWT_SECRET, DB credentials, и т.д.)"

        # Verify critical variables are set
        if [ -z "$JWT_SECRET" ]; then
            echo "⚠️  Warning: JWT_SECRET не найден в .env.local"
        fi
    else
        echo "⚠️  Warning: .env.local не найден по пути $env_file"
        echo "   Go сервисы будут использовать значения по умолчанию"
        echo "   Создайте .env.local из .env.local.example если необходимо"
    fi

    # Load generated service configuration (ports, URLs)
    local generated_env="$PROJECT_ROOT/generated/.env.services"
    if [ -f "$generated_env" ]; then
        set -a
        source <(grep -v '^#' "$generated_env" | grep -v '^[[:space:]]*$' | grep -v '^=' | sed 's/\r$//')
        set +a
        echo "✓ Сгенерированная конфигурация портов загружена"
    fi
}

##############################################################################
# End of common-functions.sh
##############################################################################
