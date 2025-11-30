#!/bin/bash

##############################################################################
# CommandCenter1C - Setup Common Functions
##############################################################################
#
# Общие функции для install.sh, uninstall.sh и offline.sh
# Используется через source.
#
# Требования:
#   SCRIPT_DIR и PROJECT_ROOT должны быть установлены ДО source common.sh
#
# Version: 1.0.0
##############################################################################

# Проверка версии bash
if [[ "${BASH_VERSINFO[0]}" -lt 4 ]]; then
    echo "FATAL: Требуется bash 4.0 или выше (текущая: ${BASH_VERSION})" >&2
    exit 1
fi

# Предотвращение повторного sourcing
if [[ -n "$SETUP_COMMON_LOADED" ]]; then
    return 0
fi
SETUP_COMMON_LOADED=true

##############################################################################
# COLORS
##############################################################################

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

##############################################################################
# LOGGING FUNCTIONS
##############################################################################

log_info()    { echo -e "${BLUE}[INFO]${NC} $1"; }
log_success() { echo -e "${GREEN}[OK]${NC} $1"; }
log_warning() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error()   { echo -e "${RED}[ERROR]${NC} $1" >&2; }
log_step()    { echo -e "${CYAN}[STEP]${NC} $1"; }

# Verbose logging (только если VERBOSE=true)
log_verbose() {
    if [[ "${VERBOSE:-false}" == "true" ]]; then
        echo -e "${BLUE}[VERBOSE]${NC} $1"
    fi
}

##############################################################################
# PLATFORM DETECTION
##############################################################################

detect_platform() {
    # WSL detection
    if [[ -f /proc/version ]] && grep -qi microsoft /proc/version 2>/dev/null; then
        # Определяем дистрибутив внутри WSL
        if command -v pacman &>/dev/null; then
            echo "wsl-pacman"
        elif command -v apt &>/dev/null; then
            echo "wsl-apt"
        elif command -v dnf &>/dev/null; then
            echo "wsl-dnf"
        else
            echo "wsl"
        fi
        return
    fi

    # macOS
    if [[ "$OSTYPE" == "darwin"* ]]; then
        echo "macos"
        return
    fi

    # Linux - по пакетному менеджеру
    if command -v pacman &>/dev/null; then
        echo "linux-pacman"
    elif command -v apt &>/dev/null; then
        echo "linux-apt"
    elif command -v dnf &>/dev/null; then
        echo "linux-dnf"
    elif command -v apk &>/dev/null; then
        echo "linux-apk"
    else
        echo "unknown"
    fi
}

is_wsl() {
    [[ "$(detect_platform)" == wsl* ]]
}

is_macos() {
    [[ "$(detect_platform)" == "macos" ]]
}

##############################################################################
# USER INTERACTION
##############################################################################

# Confirmation prompt
# Usage: confirm_action "Удалить все файлы?" "n"  # default: no
#        confirm_action "Продолжить?" "y"         # default: yes
confirm_action() {
    local message=$1
    local default=${2:-n}  # default: no

    # Пропуск в режиме --force
    if [[ "${FORCE:-false}" == "true" ]]; then
        return 0
    fi

    local prompt
    if [[ "$default" == "y" ]]; then
        prompt="[Y/n]"
    else
        prompt="[y/N]"
    fi

    echo ""
    read -p "$(echo -e "${YELLOW}$message${NC} $prompt: ")" response
    response=${response:-$default}
    [[ "$response" =~ ^[Yy]$ ]]
}

# Multi-choice prompt
# Usage: choice=$(select_option "Выберите действие:" "Удалить" "Сохранить" "Отмена")
select_option() {
    local prompt=$1
    shift
    local options=("$@")

    echo ""
    echo -e "${YELLOW}$prompt${NC}"
    local i=1
    for opt in "${options[@]}"; do
        echo "  $i) $opt"
        ((i++))
    done

    while true; do
        read -p "Выбор [1-${#options[@]}]: " choice
        if [[ "$choice" =~ ^[0-9]+$ ]] && (( choice >= 1 && choice <= ${#options[@]} )); then
            echo "${options[$((choice-1))]}"
            return 0
        fi
        echo "Неверный выбор. Попробуйте снова."
    done
}

##############################################################################
# FILE SIZE UTILITIES
##############################################################################

# Human-readable size
# Usage: format_size 1073741824  # Output: "1 GB"
format_size() {
    local bytes=$1
    if [[ $bytes -gt 1073741824 ]]; then
        echo "$(( bytes / 1073741824 )) GB"
    elif [[ $bytes -gt 1048576 ]]; then
        echo "$(( bytes / 1048576 )) MB"
    elif [[ $bytes -gt 1024 ]]; then
        echo "$(( bytes / 1024 )) KB"
    else
        echo "$bytes B"
    fi
}

# Get directory size in bytes
# Usage: size=$(get_dir_size "/path/to/dir")
get_dir_size() {
    local dir=$1
    if [[ -d "$dir" ]]; then
        # macOS du не поддерживает -b, используем -k и умножаем на 1024
        if [[ "$OSTYPE" == "darwin"* ]]; then
            local kb
            kb=$(du -sk "$dir" 2>/dev/null | cut -f1)
            echo $((kb * 1024))
        else
            du -sb "$dir" 2>/dev/null | cut -f1
        fi
    else
        echo "0"
    fi
}

# Get directory size formatted
# Usage: get_dir_size_human "/path/to/dir"  # Output: "125 MB"
get_dir_size_human() {
    local dir=$1
    local bytes=$(get_dir_size "$dir")
    format_size "$bytes"
}

##############################################################################
# SHELL CONFIGURATION
##############################################################################

# Detect user's shell config file
get_shell_config() {
    local shell_name=$(basename "$SHELL")

    case "$shell_name" in
        bash) echo "$HOME/.bashrc" ;;
        zsh)  echo "$HOME/.zshrc" ;;
        fish) echo "$HOME/.config/fish/config.fish" ;;
        *)    echo "$HOME/.profile" ;;
    esac
}

# Check if string exists in shell config
has_in_shell_config() {
    local pattern=$1
    local config=$(get_shell_config)

    [[ -f "$config" ]] && grep -q "$pattern" "$config" 2>/dev/null
}

##############################################################################
# BACKUP UTILITIES
##############################################################################

# Create timestamped backup of a file
# Usage: backup_file "/path/to/file"
# Returns: path to backup file
backup_file() {
    local file=$1
    local timestamp=$(date +%Y%m%d_%H%M%S)
    local backup="${file}.backup_${timestamp}"

    if [[ -f "$file" ]]; then
        cp "$file" "$backup"
        echo "$backup"
    fi
}

# Create backup directory with timestamp
# Usage: backup_dir=$(create_backup_dir "cc1c-setup")
create_backup_dir() {
    local prefix=${1:-"backup"}
    local timestamp=$(date +%Y%m%d_%H%M%S)
    local backup_dir="$HOME/.cc1c-backups/${prefix}_${timestamp}"

    mkdir -p "$backup_dir"
    echo "$backup_dir"
}

##############################################################################
# COMPONENT DETECTION
##############################################################################

# Check if mise is installed
is_mise_installed() {
    command -v mise &>/dev/null || [[ -x "$HOME/.local/bin/mise" ]]
}

# Check if Docker is installed
is_docker_installed() {
    command -v docker &>/dev/null
}

# Check if Docker daemon is running
is_docker_running() {
    docker info &>/dev/null 2>&1
}

# Check if project venv exists
has_python_venv() {
    [[ -d "${PROJECT_ROOT:-}/orchestrator/venv" ]]
}

# Check if node_modules exists
has_node_modules() {
    [[ -d "${PROJECT_ROOT:-}/frontend/node_modules" ]]
}

# Check if Go modules are downloaded
has_go_modules() {
    local go_mod_cache="$HOME/go/pkg/mod"
    [[ -d "$go_mod_cache" ]] && [[ -n "$(ls -A "$go_mod_cache" 2>/dev/null)" ]]
}

##############################################################################
# MISE UTILITIES
##############################################################################

# Get mise data directory
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

# Get mise config directory
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
# VERSION PARSING
##############################################################################

# Parse version from string (e.g., "mise 2024.1.0" -> "2024.1.0")
parse_version() {
    local input=$1
    echo "$input" | grep -oE '[0-9]+\.[0-9]+(\.[0-9]+)?' | head -1
}

# Compare versions (returns 0 if v1 >= v2)
version_gte() {
    local v1=$1
    local v2=$2

    # Use sort -V for version comparison
    local min=$(printf '%s\n%s' "$v1" "$v2" | sort -V | head -1)
    [[ "$min" == "$v2" ]]
}

##############################################################################
# SAFE FILE OPERATIONS
##############################################################################

# Безопасное удаление с проверкой пути
# Usage: safe_rm "/path/to/dir" [force]
# Returns: 0 on success, 1 on error
safe_rm() {
    local path="$1"
    local force="${2:-false}"

    # Проверка что путь не пустой
    if [[ -z "$path" ]]; then
        log_error "safe_rm: пустой путь"
        return 1
    fi

    # Проверка что путь не содержит только пробелы (ДО нормализации)
    if [[ "$path" =~ ^[[:space:]]*$ ]]; then
        log_error "safe_rm: путь содержит только пробелы"
        return 1
    fi

    # Запрещенные пути (защита от случайного удаления) - проверяем ДО нормализации
    local -a forbidden_paths=(
        "/"
        "/home"
        "/root"
        "/etc"
        "/usr"
        "/var"
        "/bin"
        "/sbin"
        "/lib"
        "/lib64"
        "/boot"
        "/dev"
        "/proc"
        "/sys"
        "/tmp"
        "$HOME"
    )

    for forbidden in "${forbidden_paths[@]}"; do
        # Сравниваем и с оригинальным путем, и с нормализованным
        if [[ "$path" == "$forbidden" ]] || [[ "${path%/}" == "$forbidden" ]]; then
            log_error "safe_rm: отказ в удалении защищенного пути: $path"
            return 1
        fi
    done

    # Нормализация пути (убираем trailing slashes) ПОСЛЕ проверки forbidden
    path="${path%/}"

    # Проверка что путь существует
    if [[ ! -e "$path" ]]; then
        log_verbose "safe_rm: путь не существует: $path"
        return 0
    fi

    # Удаление
    if [[ "$force" == "true" ]]; then
        rm -rf "$path"
    else
        rm -r "$path"
    fi
}

# Портабельный sed -i (работает на Linux и macOS)
# Usage: sed_inplace "s/old/new/g" "/path/to/file"
sed_inplace() {
    local expression="$1"
    local file="$2"

    if [[ ! -f "$file" ]]; then
        log_error "sed_inplace: файл не найден: $file"
        return 1
    fi

    if [[ "$OSTYPE" == "darwin"* ]]; then
        sed -i '' "$expression" "$file"
    else
        sed -i "$expression" "$file"
    fi
}

##############################################################################
# SUDO UTILITIES
##############################################################################

# Проверка возможности sudo
# Usage: if check_sudo_available; then sudo cmd; fi
check_sudo_available() {
    if ! command -v sudo &>/dev/null; then
        return 1
    fi

    # Проверка без пароля
    if sudo -n true 2>/dev/null; then
        return 0
    fi

    # Попытка получить sudo с паролем
    log_info "Для некоторых операций требуется sudo"
    if sudo -v 2>/dev/null; then
        return 0
    fi

    return 1
}

##############################################################################
# DISTRO DETECTION (safe parsing without source)
##############################################################################

# Безопасное получение ID дистрибутива
# Usage: distro=$(get_distro_id)
get_distro_id() {
    local distro=""
    if [[ -f /etc/os-release ]]; then
        distro=$(grep -E "^ID=" /etc/os-release 2>/dev/null | cut -d= -f2 | tr -d '"' | head -1)
    fi
    echo "$distro"
}

# Безопасное получение VERSION_CODENAME
# Usage: codename=$(get_distro_codename)
get_distro_codename() {
    local codename=""
    if [[ -f /etc/os-release ]]; then
        codename=$(grep -E "^VERSION_CODENAME=" /etc/os-release 2>/dev/null | cut -d= -f2 | tr -d '"' | head -1)
    fi
    echo "$codename"
}
