#!/bin/bash

##############################################################################
# CommandCenter1C - Platform Detection Library
##############################################################################
#
# Определение операционной системы, платформы и окружения.
#
# Usage:
#   source scripts/lib/platform.sh
#
# Dependencies:
#   - scripts/lib/core.sh (должен быть загружен первым)
#
# Exports:
#   Detection: detect_os, detect_platform, get_distro_id, get_distro_codename
#   Checks: is_wsl, is_macos, is_linux, is_windows
#   Environment: init_os_environment, OS_TYPE, BIN_EXT, VENV_BIN_DIR
#
# Version: 1.0.0
##############################################################################

# Проверка зависимостей
if [[ -z "${CC1C_LIB_CORE_LOADED:-}" ]]; then
    echo "ERROR: platform.sh requires core.sh to be loaded first" >&2
    return 1
fi

# Предотвращение повторного sourcing
if [[ -n "${CC1C_LIB_PLATFORM_LOADED:-}" ]]; then
    return 0
fi
CC1C_LIB_PLATFORM_LOADED=true

##############################################################################
# OS DETECTION
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

# detect_platform - определение платформы с учетом пакетного менеджера
# Usage: platform=$(detect_platform)
# Returns: wsl-pacman | wsl-apt | wsl-dnf | wsl | linux-pacman | linux-apt | linux-dnf | linux-apk | macos | unknown
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

##############################################################################
# DISTRO DETECTION
##############################################################################

# get_distro_id - получение ID дистрибутива из /etc/os-release
# Usage: distro=$(get_distro_id)
# Returns: ubuntu | debian | arch | fedora | alpine | etc.
get_distro_id() {
    local distro=""
    if [[ -f /etc/os-release ]]; then
        distro=$(grep -E "^ID=" /etc/os-release 2>/dev/null | cut -d= -f2 | tr -d '"' | head -1)
    fi
    echo "$distro"
}

# get_distro_codename - получение VERSION_CODENAME из /etc/os-release
# Usage: codename=$(get_distro_codename)
# Returns: jammy | bookworm | etc.
get_distro_codename() {
    local codename=""
    if [[ -f /etc/os-release ]]; then
        codename=$(grep -E "^VERSION_CODENAME=" /etc/os-release 2>/dev/null | cut -d= -f2 | tr -d '"' | head -1)
    fi
    echo "$codename"
}

# get_distro_version - получение VERSION_ID из /etc/os-release
# Usage: version=$(get_distro_version)
# Returns: 22.04 | 12 | etc.
get_distro_version() {
    local version=""
    if [[ -f /etc/os-release ]]; then
        version=$(grep -E "^VERSION_ID=" /etc/os-release 2>/dev/null | cut -d= -f2 | tr -d '"' | head -1)
    fi
    echo "$version"
}

##############################################################################
# BOOLEAN CHECKS
##############################################################################

# is_wsl - проверка запуска в WSL
# Usage: if is_wsl; then ...
is_wsl() {
    [[ "$(detect_platform)" == wsl* ]]
}

# is_macos - проверка запуска на macOS
# Usage: if is_macos; then ...
is_macos() {
    [[ "$(detect_platform)" == "macos" ]]
}

# is_linux - проверка запуска на Linux (не WSL)
# Usage: if is_linux; then ...
is_linux() {
    [[ "$(detect_platform)" == linux-* ]]
}

# is_windows - проверка запуска на Windows (Git Bash, MSYS, Cygwin)
# Usage: if is_windows; then ...
is_windows() {
    [[ "$(detect_os)" == "windows" ]]
}

# is_arch - проверка Arch Linux
# Usage: if is_arch; then ...
is_arch() {
    local platform
    platform=$(detect_platform)
    [[ "$platform" == "linux-pacman" || "$platform" == "wsl-pacman" ]]
}

# is_debian_based - проверка Debian/Ubuntu
# Usage: if is_debian_based; then ...
is_debian_based() {
    local platform
    platform=$(detect_platform)
    [[ "$platform" == "linux-apt" || "$platform" == "wsl-apt" ]]
}

# is_fedora_based - проверка Fedora/RHEL
# Usage: if is_fedora_based; then ...
is_fedora_based() {
    local platform
    platform=$(detect_platform)
    [[ "$platform" == "linux-dnf" || "$platform" == "wsl-dnf" ]]
}

##############################################################################
# SHELL CONFIGURATION
##############################################################################

# get_shell_config - получение пути к конфигу текущего shell
# Usage: config=$(get_shell_config)
# Returns: ~/.bashrc | ~/.zshrc | ~/.config/fish/config.fish | ~/.profile
get_shell_config() {
    local shell_name
    shell_name=$(basename "$SHELL")

    case "$shell_name" in
        bash) echo "$HOME/.bashrc" ;;
        zsh)  echo "$HOME/.zshrc" ;;
        fish) echo "$HOME/.config/fish/config.fish" ;;
        *)    echo "$HOME/.profile" ;;
    esac
}

# has_in_shell_config - проверка наличия строки в shell конфиге
# Usage: if has_in_shell_config "mise activate"; then ...
has_in_shell_config() {
    local pattern=$1
    local config
    config=$(get_shell_config)

    [[ -f "$config" ]] && grep -q "$pattern" "$config" 2>/dev/null
}

##############################################################################
# ENVIRONMENT INITIALIZATION
##############################################################################

# init_os_environment - инициализация ОС-специфичных переменных
# Устанавливает: OS_TYPE, BIN_EXT, VENV_BIN_DIR
# Usage: init_os_environment
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

    log_debug "OS_TYPE=$OS_TYPE, BIN_EXT=$BIN_EXT, VENV_BIN_DIR=$VENV_BIN_DIR"
}

##############################################################################
# PACKAGE MANAGER HELPERS
##############################################################################

# get_package_manager - получение команды пакетного менеджера
# Usage: pm=$(get_package_manager)
# Returns: pacman | apt | dnf | apk | brew | ""
get_package_manager() {
    local platform
    platform=$(detect_platform)

    case "$platform" in
        *-pacman) echo "pacman" ;;
        *-apt)    echo "apt" ;;
        *-dnf)    echo "dnf" ;;
        *-apk)    echo "apk" ;;
        macos)    echo "brew" ;;
        *)        echo "" ;;
    esac
}

# install_package - установка пакета через системный менеджер
# Usage: install_package "git" "curl" "wget"
# Note: требует sudo для Linux
install_package() {
    local pm
    pm=$(get_package_manager)

    if [[ -z "$pm" ]]; then
        log_error "Пакетный менеджер не найден"
        return 1
    fi

    case "$pm" in
        pacman)
            sudo pacman -S --noconfirm --needed "$@"
            ;;
        apt)
            sudo apt-get install -y "$@"
            ;;
        dnf)
            sudo dnf install -y "$@"
            ;;
        apk)
            sudo apk add "$@"
            ;;
        brew)
            brew install "$@"
            ;;
    esac
}

##############################################################################
# SUDO UTILITIES
##############################################################################

# check_sudo_available - проверка возможности использовать sudo
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
# AUTO-INITIALIZATION
##############################################################################

# Автоматическая инициализация при source
init_os_environment

##############################################################################
# End of platform.sh
##############################################################################
