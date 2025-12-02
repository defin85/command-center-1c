#!/bin/bash

##############################################################################
# CommandCenter1C - System Packages Installation
##############################################################################
#
# Установка базовых системных пакетов для разработки.
# Использует кросс-платформенную библиотеку packages.sh.
#
# Usage:
#   ./scripts/setup/install-system.sh [OPTIONS]
#
# Options:
#   --dry-run           Показать план без установки
#   --skip-update       Не обновлять индекс пакетов
#   -v, --verbose       Подробный вывод
#   -h, --help          Показать справку
#
# Examples:
#   ./scripts/setup/install-system.sh                # Полная установка
#   ./scripts/setup/install-system.sh --dry-run      # Показать план
#   ./scripts/setup/install-system.sh --skip-update  # Без обновления индекса
#
# Version: 1.0.0
##############################################################################

set -e

# Версия скрипта
SCRIPT_VERSION="1.0.0"

# Директории
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

# Подключение библиотеки
if [[ -f "$PROJECT_ROOT/scripts/lib/init.sh" ]]; then
    source "$PROJECT_ROOT/scripts/lib/init.sh"
else
    echo "FATAL: scripts/lib/init.sh не найден в $PROJECT_ROOT" >&2
    exit 1
fi

##############################################################################
# PACKAGE LIST
##############################################################################

# Список пакетов для установки (canonical names из packages.sh)
SYSTEM_PACKAGES=(
    # Базовые утилиты
    "git"
    "curl"
    "wget"

    # JSON парсинг
    "jq"

    # Быстрый поиск
    "ripgrep"
    "fd"

    # Мониторинг и утилиты
    "htop"
    "tree"

    # Архивация
    "unzip"
    "zip"

    # SSH
    "openssh"

    # Build tools
    "base_devel"
)

##############################################################################
# CLI ARGUMENTS
##############################################################################

DRY_RUN=false
SKIP_UPDATE=false
VERBOSE=false

parse_args() {
    while [[ $# -gt 0 ]]; do
        case $1 in
            --dry-run)
                DRY_RUN=true
                shift
                ;;
            --skip-update)
                SKIP_UPDATE=true
                shift
                ;;
            -v|--verbose)
                VERBOSE=true
                export VERBOSE
                shift
                ;;
            -h|--help)
                show_help
                exit 0
                ;;
            *)
                log_error "Неизвестный параметр: $1"
                show_help
                exit 1
                ;;
        esac
    done
}

show_help() {
    cat << 'EOF'
CommandCenter1C - System Packages Installation

Usage:
  ./scripts/setup/install-system.sh [OPTIONS]

Options:
  --dry-run           Показать план без установки
  --skip-update       Не обновлять индекс пакетов
  -v, --verbose       Подробный вывод
  -h, --help          Показать эту справку

Устанавливаемые пакеты:
  git, curl, wget     Базовые утилиты
  jq                  JSON парсинг
  ripgrep             Быстрый grep
  fd                  Быстрый find
  htop                Мониторинг процессов
  tree                Дерево каталогов
  unzip, zip          Архивация
  openssh             SSH клиент
  base_devel          Build tools (gcc, make, etc.)

Examples:
  ./scripts/setup/install-system.sh                # Полная установка
  ./scripts/setup/install-system.sh --dry-run      # Показать план
  ./scripts/setup/install-system.sh --skip-update  # Без обновления индекса
EOF
}

##############################################################################
# PACKAGE ANALYSIS
##############################################################################

# Определить какие пакеты уже установлены
analyze_packages() {
    local -n installed_ref=$1
    local -n missing_ref=$2

    installed_ref=()
    missing_ref=()

    for pkg in "${SYSTEM_PACKAGES[@]}"; do
        # Получить имя пакета для текущего дистрибутива
        local mapped_name
        mapped_name=$(pkg_map_name "$pkg")
        local map_result=$?

        # Пропустить недоступные пакеты
        if [[ $map_result -eq 1 ]] || [[ -z "$mapped_name" ]]; then
            $VERBOSE && log_warning "Пакет '$pkg' недоступен для этого дистрибутива"
            continue
        fi

        # Проверить установлен ли
        if pkg_is_installed "$mapped_name"; then
            installed_ref+=("$pkg")
        else
            missing_ref+=("$pkg")
        fi
    done
}

##############################################################################
# INSTALLATION
##############################################################################

install_packages() {
    local -a installed_packages
    local -a missing_packages

    log_step "Анализ установленных пакетов..."
    analyze_packages installed_packages missing_packages

    # Показать статус
    echo ""
    log_info "Всего пакетов: ${#SYSTEM_PACKAGES[@]}"
    log_success "Уже установлено: ${#installed_packages[@]}"

    if [[ ${#installed_packages[@]} -gt 0 ]]; then
        $VERBOSE && log_info "  Установлены: ${installed_packages[*]}"
    fi

    # Проверить нужна ли установка
    if [[ ${#missing_packages[@]} -eq 0 ]]; then
        echo ""
        log_success "Все системные пакеты уже установлены!"
        return 0
    fi

    log_warning "Требуется установка: ${#missing_packages[@]}"
    log_info "  Пакеты: ${missing_packages[*]}"
    echo ""

    # Dry-run режим
    if $DRY_RUN; then
        log_info "[DRY-RUN] План установки:"
        echo ""

        if ! $SKIP_UPDATE; then
            log_info "  1. Обновление индекса пакетов (pkg_update)"
        fi

        log_info "  2. Установка пакетов:"
        for pkg in "${missing_packages[@]}"; do
            local mapped_name
            mapped_name=$(pkg_map_name "$pkg")
            log_info "     - $pkg -> $mapped_name"
        done
        echo ""
        log_info "[DRY-RUN] Изменения НЕ применены"
        return 0
    fi

    # Обновление индекса пакетов
    if ! $SKIP_UPDATE; then
        log_step "Обновление индекса пакетов..."
        pkg_update
        echo ""
    fi

    # Установка пакетов
    log_step "Установка недостающих пакетов..."
    if pkg_install "${missing_packages[@]}"; then
        echo ""
        log_success "Все пакеты успешно установлены!"
    else
        echo ""
        log_warning "Некоторые пакеты не были установлены"
        return 1
    fi
}

##############################################################################
# VERIFICATION
##############################################################################

verify_installation() {
    log_step "Проверка установки..."
    echo ""

    local failed=0

    for pkg in "${SYSTEM_PACKAGES[@]}"; do
        local mapped_name
        mapped_name=$(pkg_map_name "$pkg")
        local map_result=$?

        # Пропустить недоступные
        if [[ $map_result -eq 1 ]] || [[ -z "$mapped_name" ]]; then
            continue
        fi

        if pkg_is_installed "$mapped_name"; then
            local version
            version=$(pkg_version "$mapped_name")
            print_status "success" "$pkg ($mapped_name): $version"
        else
            print_status "error" "$pkg ($mapped_name): не установлен"
            ((failed++))
        fi
    done

    echo ""

    if [[ $failed -gt 0 ]]; then
        log_warning "Не установлено пакетов: $failed"
        return 1
    else
        log_success "Все пакеты установлены корректно"
        return 0
    fi
}

##############################################################################
# MAIN
##############################################################################

main() {
    parse_args "$@"

    echo ""
    echo -e "${BOLD}========================================${NC}"
    echo -e "${BOLD}  System Packages Installation${NC}"
    echo -e "${BOLD}========================================${NC}"
    echo ""

    # Информация о платформе
    local platform
    platform=$(detect_platform)
    local pm
    pm=$(get_package_manager)

    log_info "Платформа: $platform"
    log_info "Пакетный менеджер: $pm"
    echo ""

    if $DRY_RUN; then
        log_warning "Режим DRY-RUN: изменения НЕ будут применены"
        echo ""
    fi

    # Установка
    install_packages
    local install_result=$?

    # Верификация (только если не dry-run и установка прошла)
    if ! $DRY_RUN && [[ $install_result -eq 0 ]]; then
        echo ""
        verify_installation
    fi

    return $install_result
}

main "$@"
