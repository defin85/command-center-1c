#!/bin/bash

##############################################################################
# CommandCenter1C - Package Management Library
##############################################################################
#
# Кросс-платформенная абстракция пакетного менеджера.
# Поддерживает Arch Linux, Ubuntu/Debian, Fedora.
#
# Usage:
#   source scripts/lib/packages.sh
#
# Dependencies:
#   - scripts/lib/core.sh (должен быть загружен первым)
#   - scripts/lib/platform.sh (должен быть загружен вторым)
#
# Exports:
#   Installation: pkg_install, pkg_update, aur_install
#   Queries: pkg_is_installed, pkg_version, pkg_map_name
#   AUR: has_aur_helper, get_aur_helper
#
# Version: 1.0.0
##############################################################################

# Проверка зависимостей
if [[ -z "${CC1C_LIB_CORE_LOADED:-}" ]]; then
    echo "ERROR: packages.sh requires core.sh to be loaded first" >&2
    return 1
fi

if [[ -z "${CC1C_LIB_PLATFORM_LOADED:-}" ]]; then
    echo "ERROR: packages.sh requires platform.sh to be loaded first" >&2
    return 1
fi

# Предотвращение повторного sourcing
if [[ -n "${_CC1C_PACKAGES_LOADED:-}" ]]; then
    return 0
fi
_CC1C_PACKAGES_LOADED=true

##############################################################################
# PACKAGE NAME MAPPING
##############################################################################

# Ассоциативный массив для маппинга имен пакетов
# Формат: [canonical_name]="arch|ubuntu|fedora"
# Значение "-" означает "пакет недоступен"
# Значение "AUR:name" означает "доступен только через AUR"
declare -gA _PKG_MAP=(
    # Базовые утилиты
    ["git"]="git|git|git"
    ["curl"]="curl|curl|curl"
    ["wget"]="wget|wget|wget"
    ["jq"]="jq|jq|jq"
    ["ripgrep"]="ripgrep|ripgrep|ripgrep"
    ["fd"]="fd|fd-find|fd-find"
    ["htop"]="htop|htop|htop"
    ["base_devel"]="base-devel|build-essential|@development-tools"

    # Базы данных
    ["postgresql"]="postgresql|postgresql|postgresql"
    ["redis"]="redis|redis|redis"
    ["pgadmin"]="pgadmin4|pgadmin4|pgadmin4"
    ["minio"]="AUR:minio|-|-"
    ["minio_client"]="minio-client|minio-client|minio-client"

    # Мониторинг
    ["prometheus"]="prometheus|prometheus|prometheus2"
    ["grafana"]="grafana|grafana|grafana"
    ["node_exporter"]="prometheus-node-exporter|prometheus-node-exporter|node_exporter"
    ["postgres_exporter"]="AUR:prometheus-postgres-exporter|prometheus-postgres-exporter|-"
    ["redis_exporter"]="AUR:prometheus-redis-exporter|prometheus-redis-exporter|-"
    ["blackbox_exporter"]="prometheus-blackbox-exporter|prometheus-blackbox-exporter|prometheus-blackbox-exporter"

    # Языки и рантаймы
    ["python"]="python|python3|python3"
    ["nodejs"]="nodejs|nodejs|nodejs"
    ["go"]="go|golang-go|golang"
    ["rust"]="rust|rustc|rust"

    # Дополнительные утилиты
    ["tree"]="tree|tree|tree"
    ["unzip"]="unzip|unzip|unzip"
    ["zip"]="zip|zip|zip"
    ["openssh"]="openssh|openssh-client|openssh-clients"
)

##############################################################################
# PACKAGE NAME RESOLUTION
##############################################################################

# pkg_map_name - маппинг канонического имени в имя пакета для текущего дистрибутива
# Usage: pkg_name=$(pkg_map_name "postgresql")
# Returns: имя пакета для текущего дистрибутива или canonical name если маппинг не найден
# Exit code: 0 - успех, 1 - пакет недоступен (-), 2 - требуется AUR
pkg_map_name() {
    local canonical_name=$1
    local mapping=""
    local pkg_name=""

    # Получить маппинг
    mapping="${_PKG_MAP[$canonical_name]:-}"

    # Если маппинг не найден, вернуть оригинальное имя
    if [[ -z "$mapping" ]]; then
        echo "$canonical_name"
        return 0
    fi

    # Распарсить маппинг по текущему дистрибутиву
    local arch_pkg ubuntu_pkg fedora_pkg
    IFS='|' read -r arch_pkg ubuntu_pkg fedora_pkg <<< "$mapping"

    if is_arch; then
        pkg_name="$arch_pkg"
    elif is_debian_based; then
        pkg_name="$ubuntu_pkg"
    elif is_fedora_based; then
        pkg_name="$fedora_pkg"
    else
        # Неизвестный дистрибутив - вернуть оригинальное имя
        echo "$canonical_name"
        return 0
    fi

    # Проверить специальные значения
    if [[ "$pkg_name" == "-" ]]; then
        log_warning "Пакет '$canonical_name' недоступен для этого дистрибутива"
        echo ""
        return 1
    fi

    if [[ "$pkg_name" == AUR:* ]]; then
        # Убрать префикс AUR:
        echo "${pkg_name#AUR:}"
        return 2
    fi

    echo "$pkg_name"
    return 0
}

##############################################################################
# AUR HELPERS (Arch Linux)
##############################################################################

# has_aur_helper - проверка наличия AUR helper
# Usage: if has_aur_helper; then ...
has_aur_helper() {
    command -v yay &>/dev/null || command -v paru &>/dev/null
}

# get_aur_helper - получение имени AUR helper
# Usage: helper=$(get_aur_helper)
# Returns: yay | paru | none
get_aur_helper() {
    if command -v yay &>/dev/null; then
        echo "yay"
    elif command -v paru &>/dev/null; then
        echo "paru"
    else
        echo "none"
    fi
}

# aur_install - установка пакета из AUR (только Arch Linux)
# Usage: aur_install "package-name"
# Note: Требует AUR helper (yay или paru)
# Returns: 0 - успех, 1 - ошибка
aur_install() {
    local pkg=$1

    if ! is_arch; then
        log_error "aur_install доступен только на Arch Linux"
        return 1
    fi

    local helper
    helper=$(get_aur_helper)

    if [[ "$helper" == "none" ]]; then
        log_error "AUR helper не найден. Установите yay или paru:"
        log_info "  git clone https://aur.archlinux.org/yay.git && cd yay && makepkg -si"
        return 1
    fi

    # Проверить установлен ли уже
    if pkg_is_installed "$pkg"; then
        log_info "Пакет '$pkg' уже установлен"
        return 0
    fi

    log_info "Установка '$pkg' из AUR через $helper..."
    "$helper" -S --noconfirm --needed "$pkg"
}

##############################################################################
# PACKAGE QUERIES
##############################################################################

# pkg_is_installed - проверка установлен ли пакет
# Usage: if pkg_is_installed "postgresql"; then ...
# Returns: 0 - установлен, 1 - не установлен
pkg_is_installed() {
    local pkg=$1
    local pm
    pm=$(get_package_manager)

    case "$pm" in
        pacman)
            pacman -Qi "$pkg" &>/dev/null
            ;;
        apt)
            dpkg -l "$pkg" 2>/dev/null | grep -q "^ii"
            ;;
        dnf)
            rpm -q "$pkg" &>/dev/null
            ;;
        brew)
            brew list "$pkg" &>/dev/null
            ;;
        *)
            # Fallback: проверка через command если пакет является командой
            command -v "$pkg" &>/dev/null
            ;;
    esac
}

# pkg_version - получение версии установленного пакета
# Usage: version=$(pkg_version "postgresql")
# Returns: версия пакета или пустая строка если не установлен
pkg_version() {
    local pkg=$1
    local pm
    pm=$(get_package_manager)

    case "$pm" in
        pacman)
            pacman -Qi "$pkg" 2>/dev/null | grep "^Version" | awk '{print $3}'
            ;;
        apt)
            dpkg -l "$pkg" 2>/dev/null | grep "^ii" | awk '{print $3}'
            ;;
        dnf)
            rpm -q --qf '%{VERSION}-%{RELEASE}' "$pkg" 2>/dev/null
            ;;
        brew)
            brew info "$pkg" 2>/dev/null | head -1 | awk '{print $3}'
            ;;
        *)
            echo ""
            ;;
    esac
}

##############################################################################
# PACKAGE INSTALLATION
##############################################################################

# pkg_update - обновление индекса пакетов
# Usage: pkg_update
# Note: Выводит команду которую нужно выполнить с sudo
pkg_update() {
    local pm
    pm=$(get_package_manager)

    case "$pm" in
        pacman)
            log_info "Обновление индекса пакетов (pacman)..."
            sudo pacman -Sy
            ;;
        apt)
            log_info "Обновление индекса пакетов (apt)..."
            sudo apt-get update
            ;;
        dnf)
            log_info "Обновление индекса пакетов (dnf)..."
            sudo dnf check-update || true  # dnf возвращает 100 если есть обновления
            ;;
        brew)
            log_info "Обновление индекса пакетов (brew)..."
            brew update
            ;;
        *)
            log_error "Пакетный менеджер не найден"
            return 1
            ;;
    esac
}

# pkg_install - установка пакетов (кросс-платформенно)
# Usage: pkg_install "postgresql" "redis" "git"
# Принимает canonical имена - автоматически маппит в имена для текущего дистрибутива
# Note: Использует sudo для Linux
# Returns: 0 - все пакеты установлены, 1 - ошибка
pkg_install() {
    local packages=("$@")
    local pm
    local mapped_packages=()
    local aur_packages=()
    local failed=0

    pm=$(get_package_manager)

    if [[ -z "$pm" ]]; then
        log_error "Пакетный менеджер не найден"
        return 1
    fi

    # Маппинг имен пакетов
    for pkg in "${packages[@]}"; do
        local mapped_name
        local map_result

        local errexit_was_set=false
        [[ $- == *e* ]] && errexit_was_set=true
        set +e
        mapped_name=$(pkg_map_name "$pkg")
        map_result=$?
        $errexit_was_set && set -e

        case $map_result in
            0)
                # Обычный пакет
                if [[ -n "$mapped_name" ]]; then
                    # Проверить установлен ли уже
                    if pkg_is_installed "$mapped_name"; then
                        log_debug "Пакет '$mapped_name' уже установлен, пропускаем"
                    else
                        mapped_packages+=("$mapped_name")
                    fi
                fi
                ;;
            1)
                # Пакет недоступен
                log_warning "Пакет '$pkg' недоступен для этого дистрибутива, пропускаем"
                ((failed++))
                ;;
            2)
                # Требуется AUR
                if is_arch; then
                    if pkg_is_installed "$mapped_name"; then
                        log_debug "AUR пакет '$mapped_name' уже установлен, пропускаем"
                    else
                        aur_packages+=("$mapped_name")
                    fi
                else
                    # Для не-Arch использовать маппированное имя напрямую
                    if pkg_is_installed "$mapped_name"; then
                        log_debug "Пакет '$mapped_name' уже установлен, пропускаем"
                    else
                        mapped_packages+=("$mapped_name")
                    fi
                fi
                ;;
        esac
    done

    # Установка обычных пакетов
    if [[ ${#mapped_packages[@]} -gt 0 ]]; then
        log_info "Установка пакетов: ${mapped_packages[*]}"

        case "$pm" in
            pacman)
                sudo pacman -S --noconfirm --needed "${mapped_packages[@]}" || ((failed++))
                ;;
            apt)
                sudo apt-get install -y "${mapped_packages[@]}" || ((failed++))
                ;;
            dnf)
                sudo dnf install -y "${mapped_packages[@]}" || ((failed++))
                ;;
            brew)
                brew install "${mapped_packages[@]}" || ((failed++))
                ;;
        esac
    fi

    # Установка AUR пакетов (только Arch)
    if [[ ${#aur_packages[@]} -gt 0 ]]; then
        if has_aur_helper; then
            local helper
            helper=$(get_aur_helper)
            log_info "Установка AUR пакетов через $helper: ${aur_packages[*]}"
            "$helper" -S --noconfirm --needed "${aur_packages[@]}" || ((failed++))
        else
            log_error "AUR пакеты требуют yay или paru: ${aur_packages[*]}"
            log_info "Установите AUR helper:"
            log_info "  git clone https://aur.archlinux.org/yay.git && cd yay && makepkg -si"
            ((failed++))
        fi
    fi

    if [[ $failed -gt 0 ]]; then
        log_warning "Некоторые пакеты не были установлены"
        return 1
    fi

    return 0
}

##############################################################################
# CONVENIENCE FUNCTIONS
##############################################################################

# pkg_ensure - гарантировать что пакеты установлены (идемпотентно)
# Usage: pkg_ensure "git" "curl" "jq"
# Alias для pkg_install с более понятным именем
pkg_ensure() {
    pkg_install "$@"
}

# pkg_list_available - вывести список всех canonical имен пакетов
# Usage: pkg_list_available
pkg_list_available() {
    log_info "Доступные canonical имена пакетов:"
    for key in "${!_PKG_MAP[@]}"; do
        echo "  $key"
    done | sort
}

# pkg_show_mapping - показать маппинг для пакета
# Usage: pkg_show_mapping "postgresql"
pkg_show_mapping() {
    local canonical_name=$1
    local mapping=""

    mapping="${_PKG_MAP[$canonical_name]:-}"

    if [[ -z "$mapping" ]]; then
        log_info "Маппинг для '$canonical_name' не найден (будет использовано как есть)"
        return 1
    fi

    local arch_pkg ubuntu_pkg fedora_pkg
    IFS='|' read -r arch_pkg ubuntu_pkg fedora_pkg <<< "$mapping"

    echo "Маппинг для '$canonical_name':"
    echo "  Arch Linux: $arch_pkg"
    echo "  Ubuntu/Debian: $ubuntu_pkg"
    echo "  Fedora: $fedora_pkg"
}

##############################################################################
# End of packages.sh
##############################################################################
