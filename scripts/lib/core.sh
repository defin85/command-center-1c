#!/bin/bash

##############################################################################
# CommandCenter1C - Core Library
##############################################################################
#
# Базовые функции: цвета, логирование, guards.
# Должна быть подключена первой из всех библиотек.
#
# Usage:
#   source scripts/lib/core.sh
#
# Exports:
#   Colors: RED, GREEN, YELLOW, BLUE, CYAN, BOLD, NC
#   Logging: log_info, log_success, log_warning, log_error, log_step, log_verbose
#   Guards: require_bash_version, require_var, prevent_double_source
#
# Version: 1.0.0
##############################################################################

# Версия библиотеки
CC1C_LIB_VERSION="1.0.0"
export CC1C_LIB_VERSION

# Предотвращение повторного sourcing (совместимо с set -u)
if [[ -n "${CC1C_LIB_CORE_LOADED:-}" ]]; then
    return 0
fi
CC1C_LIB_CORE_LOADED=true

##############################################################################
# BASH VERSION CHECK
##############################################################################

# Проверка минимальной версии bash
# Вызывается автоматически при sourcing
_check_bash_version() {
    if [[ "${BASH_VERSINFO[0]}" -lt 4 ]]; then
        echo "FATAL: Требуется bash 4.0 или выше (текущая: ${BASH_VERSION})" >&2
        exit 1
    fi
}

_check_bash_version

##############################################################################
# COLORS
##############################################################################

# Определяем цвета только если терминал поддерживает
if [[ -t 1 ]] && [[ -n "${TERM:-}" ]] && [[ "$TERM" != "dumb" ]]; then
    RED='\033[0;31m'
    GREEN='\033[0;32m'
    YELLOW='\033[1;33m'
    BLUE='\033[0;34m'
    CYAN='\033[0;36m'
    MAGENTA='\033[0;35m'
    BOLD='\033[1m'
    DIM='\033[2m'
    NC='\033[0m'
else
    RED=''
    GREEN=''
    YELLOW=''
    BLUE=''
    CYAN=''
    MAGENTA=''
    BOLD=''
    DIM=''
    NC=''
fi

##############################################################################
# LOGGING FUNCTIONS
##############################################################################

# log_info - информационное сообщение
# Usage: log_info "Message"
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

# log_success - успешное завершение
# Usage: log_success "Message"
log_success() {
    echo -e "${GREEN}[OK]${NC} $1"
}

# log_warning - предупреждение
# Usage: log_warning "Message"
log_warning() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

# log_error - ошибка (выводится в stderr)
# Usage: log_error "Message"
log_error() {
    echo -e "${RED}[ERROR]${NC} $1" >&2
}

# log_step - шаг процесса
# Usage: log_step "Step description"
log_step() {
    echo -e "${CYAN}[STEP]${NC} $1"
}

# log_debug - отладочное сообщение (только если DEBUG=true)
# Usage: log_debug "Debug info"
log_debug() {
    if [[ "${DEBUG:-false}" == "true" ]]; then
        echo -e "${DIM}[DEBUG]${NC} $1" >&2
    fi
}

# log_verbose - verbose сообщение (только если VERBOSE=true)
# Usage: log_verbose "Verbose info"
log_verbose() {
    if [[ "${VERBOSE:-false}" == "true" ]]; then
        echo -e "${BLUE}[VERBOSE]${NC} $1"
    fi
}

##############################################################################
# PRINT HELPERS
##############################################################################

# print_header - печать заголовка секции
# Usage: print_header "Section Title"
print_header() {
    local message=$1
    echo ""
    echo -e "${BLUE}========================================${NC}"
    echo -e "${BLUE}  ${message}${NC}"
    echo -e "${BLUE}========================================${NC}"
    echo ""
}

# print_status - печать статуса с иконкой
# Usage: print_status "success|warning|error|info" "Message"
print_status() {
    local status=$1
    local message=$2

    case "$status" in
        success)
            echo -e "${GREEN}✓${NC} ${message}"
            ;;
        warning)
            echo -e "${YELLOW}⚠${NC} ${message}"
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

# print_separator - горизонтальная линия
# Usage: print_separator [char] [width]
print_separator() {
    local char="${1:--}"
    local width="${2:-60}"
    printf '%*s\n' "$width" '' | tr ' ' "$char"
}

##############################################################################
# GUARD FUNCTIONS
##############################################################################

# require_bash_version - проверка минимальной версии bash
# Usage: require_bash_version 4 3  # требует bash 4.3+
require_bash_version() {
    local major=${1:-4}
    local minor=${2:-0}

    if [[ "${BASH_VERSINFO[0]}" -lt "$major" ]] || \
       [[ "${BASH_VERSINFO[0]}" -eq "$major" && "${BASH_VERSINFO[1]}" -lt "$minor" ]]; then
        log_error "Требуется bash $major.$minor+ (текущая: ${BASH_VERSION})"
        return 1
    fi
    return 0
}

# require_var - проверка что переменная установлена
# Usage: require_var "PROJECT_ROOT" "Укажите корень проекта"
require_var() {
    local var_name=$1
    local error_msg=${2:-"Переменная $var_name не установлена"}

    if [[ -z "${!var_name:-}" ]]; then
        log_error "$error_msg"
        return 1
    fi
    return 0
}

# require_command - проверка что команда доступна
# Usage: require_command "docker" "Docker не установлен"
require_command() {
    local cmd=$1
    local error_msg=${2:-"Команда '$cmd' не найдена"}

    if ! command -v "$cmd" &>/dev/null; then
        log_error "$error_msg"
        return 1
    fi
    return 0
}

# require_file - проверка что файл существует
# Usage: require_file "/path/to/file" "Файл не найден"
require_file() {
    local file=$1
    local error_msg=${2:-"Файл не найден: $file"}

    if [[ ! -f "$file" ]]; then
        log_error "$error_msg"
        return 1
    fi
    return 0
}

# require_dir - проверка что директория существует
# Usage: require_dir "/path/to/dir" "Директория не найдена"
require_dir() {
    local dir=$1
    local error_msg=${2:-"Директория не найдена: $dir"}

    if [[ ! -d "$dir" ]]; then
        log_error "$error_msg"
        return 1
    fi
    return 0
}

##############################################################################
# UTILITY FUNCTIONS
##############################################################################

# is_true - проверка boolean значения
# Usage: if is_true "$FLAG"; then ...
is_true() {
    local val="${1:-}"
    [[ "$val" == "true" || "$val" == "1" || "$val" == "yes" || "$val" == "y" ]]
}

# is_false - проверка boolean значения
# Usage: if is_false "$FLAG"; then ...
is_false() {
    local val="${1:-}"
    [[ -z "$val" || "$val" == "false" || "$val" == "0" || "$val" == "no" || "$val" == "n" ]]
}

# trim - удаление пробелов в начале и конце строки
# Usage: result=$(trim "  text  ")
trim() {
    local var="$*"
    # Удалить пробелы в начале
    var="${var#"${var%%[![:space:]]*}"}"
    # Удалить пробелы в конце
    var="${var%"${var##*[![:space:]]}"}"
    echo "$var"
}

# join_array - объединение массива в строку
# Usage: result=$(join_array "," "${array[@]}")
join_array() {
    local delimiter=$1
    shift
    local first=$1
    shift
    printf '%s' "$first" "${@/#/$delimiter}"
}

##############################################################################
# VERSION UTILITIES
##############################################################################

# parse_version - извлечение версии из строки
# Usage: version=$(parse_version "mise 2024.1.0")
parse_version() {
    local input=$1
    echo "$input" | grep -oE '[0-9]+\.[0-9]+(\.[0-9]+)?' | head -1
}

# version_gte - сравнение версий (v1 >= v2)
# Usage: if version_gte "1.2.3" "1.2.0"; then ...
version_gte() {
    local v1=$1
    local v2=$2

    # Используем sort -V для сравнения версий
    local min
    min=$(printf '%s\n%s' "$v1" "$v2" | sort -V | head -1)
    [[ "$min" == "$v2" ]]
}

# version_gt - сравнение версий (v1 > v2)
# Usage: if version_gt "1.2.3" "1.2.0"; then ...
version_gt() {
    local v1=$1
    local v2=$2

    [[ "$v1" != "$v2" ]] && version_gte "$v1" "$v2"
}

##############################################################################
# End of core.sh
##############################################################################
