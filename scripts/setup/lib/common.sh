#!/bin/bash

##############################################################################
# CommandCenter1C - Setup Common Functions
##############################################################################
# Общие функции для скриптов установки
#
# Usage:
#   source scripts/setup/lib/common.sh
##############################################################################

# Предотвращение повторного sourcing
if [ -n "$SETUP_COMMON_LOADED" ]; then
    return 0
fi
SETUP_COMMON_LOADED=true

# Определить директории (ДО загрузки dev/common-functions.sh)
SETUP_SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SETUP_DIR="$(cd "$SETUP_SCRIPT_DIR/.." && pwd)"
_SETUP_PROJECT_ROOT="$(cd "$SETUP_DIR/../.." && pwd)"

# Загрузить common-functions.sh из dev/ для переиспользования
# Он переопределит PROJECT_ROOT, но нам нужна только его функциональность
if [ -f "$_SETUP_PROJECT_ROOT/scripts/dev/common-functions.sh" ]; then
    source "$_SETUP_PROJECT_ROOT/scripts/dev/common-functions.sh"
fi

# Восстановить PROJECT_ROOT (dev/common-functions.sh может его переопределить)
PROJECT_ROOT="$_SETUP_PROJECT_ROOT"

##############################################################################
# ЦВЕТА И ФОРМАТИРОВАНИЕ
##############################################################################

# Цвета (если не определены)
RED="${RED:-\033[0;31m}"
GREEN="${GREEN:-\033[0;32m}"
YELLOW="${YELLOW:-\033[1;33m}"
BLUE="${BLUE:-\033[0;34m}"
CYAN='\033[0;36m'
BOLD='\033[1m'
NC="${NC:-\033[0m}"

##############################################################################
# LOGGING FUNCTIONS
##############################################################################

# log_info - информационное сообщение
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

# log_success - успешное действие
log_success() {
    echo -e "${GREEN}[OK]${NC} $1"
}

# log_warning - предупреждение
log_warning() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

# log_error - ошибка
log_error() {
    echo -e "${RED}[ERROR]${NC} $1" >&2
}

# log_step - шаг процесса (с номером)
log_step() {
    local step=$1
    local total=$2
    local message=$3
    echo -e "${CYAN}[${step}/${total}]${NC} ${message}"
}

# log_section - заголовок секции
log_section() {
    local title=$1
    echo ""
    echo -e "${BOLD}${BLUE}════════════════════════════════════════════════════════════════${NC}"
    echo -e "${BOLD}${BLUE}  ${title}${NC}"
    echo -e "${BOLD}${BLUE}════════════════════════════════════════════════════════════════${NC}"
    echo ""
}

# log_subsection - подзаголовок
log_subsection() {
    local title=$1
    echo ""
    echo -e "${CYAN}── ${title} ──${NC}"
    echo ""
}

##############################################################################
# VERSION COMPARISON
##############################################################################

# version_compare - сравнение semver версий
# Usage: version_compare "1.2.3" "1.2.4"
# Returns: -1 (first < second), 0 (equal), 1 (first > second)
version_compare() {
    local v1=$1
    local v2=$2

    # Убрать префикс 'v' если есть
    v1="${v1#v}"
    v2="${v2#v}"

    # Разбить на части
    IFS='.' read -ra V1_PARTS <<< "$v1"
    IFS='.' read -ra V2_PARTS <<< "$v2"

    # Сравнить каждую часть
    local max_parts=${#V1_PARTS[@]}
    [ ${#V2_PARTS[@]} -gt $max_parts ] && max_parts=${#V2_PARTS[@]}

    for ((i=0; i<max_parts; i++)); do
        local part1=${V1_PARTS[$i]:-0}
        local part2=${V2_PARTS[$i]:-0}

        # Убрать нечисловые суффиксы (например, "1.24.0-rc1" -> "1.24.0")
        part1=$(echo "$part1" | grep -oE '^[0-9]+' || echo "0")
        part2=$(echo "$part2" | grep -oE '^[0-9]+' || echo "0")

        if [ "$part1" -lt "$part2" ]; then
            echo "-1"
            return
        elif [ "$part1" -gt "$part2" ]; then
            echo "1"
            return
        fi
    done

    echo "0"
}

# version_gte - проверка что v1 >= v2
# Usage: if version_gte "1.24.0" "1.21.0"; then ...
version_gte() {
    local result=$(version_compare "$1" "$2")
    [ "$result" -ge 0 ]
}

# version_gt - проверка что v1 > v2
version_gt() {
    local result=$(version_compare "$1" "$2")
    [ "$result" -gt 0 ]
}

##############################################################################
# PLATFORM DETECTION (расширение)
##############################################################################

# detect_distro - определение дистрибутива Linux
# Returns: ubuntu | debian | fedora | rhel | centos | arch | alpine | unknown
detect_distro() {
    if [ -f /etc/os-release ]; then
        source /etc/os-release
        case "$ID" in
            ubuntu)   echo "ubuntu" ;;
            debian)   echo "debian" ;;
            fedora)   echo "fedora" ;;
            rhel|rocky|almalinux) echo "rhel" ;;
            centos)   echo "centos" ;;
            arch|manjaro) echo "arch" ;;
            alpine)   echo "alpine" ;;
            *)        echo "unknown" ;;
        esac
    elif [ -f /etc/debian_version ]; then
        echo "debian"
    elif [ -f /etc/redhat-release ]; then
        echo "rhel"
    else
        echo "unknown"
    fi
}

# detect_package_manager - определение пакетного менеджера
# Returns: apt | dnf | yum | pacman | apk | brew | unknown
detect_package_manager() {
    local os=$(detect_os)

    case "$os" in
        macos)
            if command -v brew &>/dev/null; then
                echo "brew"
            else
                echo "unknown"
            fi
            ;;
        wsl|linux)
            if command -v apt &>/dev/null; then
                echo "apt"
            elif command -v dnf &>/dev/null; then
                echo "dnf"
            elif command -v yum &>/dev/null; then
                echo "yum"
            elif command -v pacman &>/dev/null; then
                echo "pacman"
            elif command -v apk &>/dev/null; then
                echo "apk"
            else
                echo "unknown"
            fi
            ;;
        windows)
            if command -v winget &>/dev/null; then
                echo "winget"
            elif command -v choco &>/dev/null; then
                echo "choco"
            else
                echo "unknown"
            fi
            ;;
        *)
            echo "unknown"
            ;;
    esac
}

# is_wsl - проверка что работаем в WSL
is_wsl() {
    [ "$(detect_os)" = "wsl" ]
}

# is_root - проверка root прав
is_root() {
    [ "$(id -u)" -eq 0 ]
}

# sudo_cmd - команда sudo если не root
sudo_cmd() {
    if is_root; then
        "$@"
    else
        sudo "$@"
    fi
}

##############################################################################
# COMMAND CHECKS
##############################################################################

# command_exists - проверка наличия команды
command_exists() {
    command -v "$1" &>/dev/null
}

# get_command_version - получение версии команды
# Usage: ver=$(get_command_version "go" "version")
get_command_version() {
    local cmd=$1
    local version_arg=${2:-"--version"}

    if ! command_exists "$cmd"; then
        echo ""
        return 1
    fi

    case "$cmd" in
        go)
            go version 2>/dev/null | grep -oE 'go[0-9]+\.[0-9]+(\.[0-9]+)?' | sed 's/go//'
            ;;
        python|python3)
            "$cmd" --version 2>/dev/null | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' | head -1
            ;;
        node)
            node --version 2>/dev/null | sed 's/v//'
            ;;
        npm)
            npm --version 2>/dev/null
            ;;
        docker)
            docker --version 2>/dev/null | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' | head -1
            ;;
        docker-compose|compose)
            docker compose version 2>/dev/null | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' | head -1 || \
            docker-compose --version 2>/dev/null | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' | head -1
            ;;
        *)
            "$cmd" $version_arg 2>/dev/null | grep -oE '[0-9]+\.[0-9]+(\.[0-9]+)?' | head -1
            ;;
    esac
}

##############################################################################
# TABLE FORMATTING
##############################################################################

# print_table_header - печать заголовка таблицы
print_table_header() {
    echo "┌────────────┬────────────┬────────────┬─────────────┐"
    echo "│ Runtime    │ Required   │ Current    │ Action      │"
    echo "├────────────┼────────────┼────────────┼─────────────┤"
}

# print_table_row - печать строки таблицы
# Usage: print_table_row "Go" "1.24.0" "1.22.5" "UPGRADE"
print_table_row() {
    local runtime=$1
    local required=$2
    local current=$3
    local action=$4

    # Цвет для action
    local action_color=""
    case "$action" in
        "OK"|"SKIP")     action_color="${GREEN}" ;;
        "INSTALL")       action_color="${YELLOW}" ;;
        "UPGRADE")       action_color="${YELLOW}" ;;
        "FIX"|"INCOMPLETE") action_color="${CYAN}" ;;
        "ERROR"|"FAIL")  action_color="${RED}" ;;
        *)               action_color="${NC}" ;;
    esac

    printf "│ %-10s │ %-10s │ %-10s │ ${action_color}%-11s${NC} │\n" \
        "$runtime" "$required" "${current:-not found}" "$action"
}

# print_table_footer - печать подвала таблицы
print_table_footer() {
    echo "└────────────┴────────────┴────────────┴─────────────┘"
}

##############################################################################
# DOWNLOAD HELPERS
##############################################################################

# download_file - скачивание файла с прогрессом
# Usage: download_file "https://example.com/file.tar.gz" "/tmp/file.tar.gz"
download_file() {
    local url=$1
    local output=$2

    if command_exists curl; then
        curl -fsSL --progress-bar -o "$output" "$url"
    elif command_exists wget; then
        wget -q --show-progress -O "$output" "$url"
    else
        log_error "Не найден curl или wget для скачивания"
        return 1
    fi
}

##############################################################################
# CONFIRMATION
##############################################################################

# confirm - запрос подтверждения
# Usage: if confirm "Продолжить?"; then ...
confirm() {
    local prompt=${1:-"Продолжить?"}
    local default=${2:-"y"}

    local yn
    if [ "$default" = "y" ]; then
        read -p "$prompt [Y/n] " yn
        yn=${yn:-y}
    else
        read -p "$prompt [y/N] " yn
        yn=${yn:-n}
    fi

    case "$yn" in
        [Yy]*) return 0 ;;
        *)     return 1 ;;
    esac
}

# Загрузить проверки полноты установки
if [ -f "$SETUP_SCRIPT_DIR/completeness-checks.sh" ]; then
    source "$SETUP_SCRIPT_DIR/completeness-checks.sh"
fi

##############################################################################
# End of common.sh
##############################################################################
