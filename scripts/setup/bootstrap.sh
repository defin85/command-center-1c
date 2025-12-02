#!/bin/bash

##############################################################################
# CommandCenter1C - Bootstrap Setup
##############################################################################
#
# Единая точка входа для полной установки окружения разработки.
# Последовательно выполняет фазы установки с проверкой и отчетом.
#
# Usage:
#   ./scripts/setup/bootstrap.sh [OPTIONS]
#
# Options:
#   --full                Полная установка (по умолчанию)
#   --minimal             Без мониторинга
#   --system-only         Только системные пакеты
#   --infra-only          Только PostgreSQL/Redis
#   --project-only        Только mise + зависимости проекта
#   --monitoring-only     Только мониторинг
#   --skip-system         Пропустить системные пакеты
#   --skip-infra          Пропустить инфраструктуру
#   --skip-project        Пропустить mise/deps
#   --skip-monitoring     Пропустить мониторинг
#   --non-interactive     Без подтверждений (для CI)
#   --dry-run             Показать план без выполнения
#   -v, --verbose         Подробный вывод
#   -h, --help            Показать справку
#
# Phases:
#   1. System Packages    (install-system.sh)
#   2. Infrastructure     (install-infra.sh) - PostgreSQL, Redis
#   3. Project            (install.sh) - mise, Go, Python, Node.js, deps
#   4. Monitoring         (install-monitoring.sh) - Prometheus, Grafana
#   5. Verification       (verify installation)
#
# Examples:
#   ./scripts/setup/bootstrap.sh                     # Полная установка
#   ./scripts/setup/bootstrap.sh --minimal           # Без мониторинга
#   ./scripts/setup/bootstrap.sh --dry-run           # Показать план
#   ./scripts/setup/bootstrap.sh --non-interactive   # Для CI/CD
#
# Version: 1.0.0
##############################################################################

set -e

# Версия скрипта
SCRIPT_VERSION="1.0.0"

# Директории
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

##############################################################################
# LIBRARY LOADING
##############################################################################

if [[ -f "$PROJECT_ROOT/scripts/lib/init.sh" ]]; then
    source "$PROJECT_ROOT/scripts/lib/init.sh"
else
    echo "FATAL: scripts/lib/init.sh not found in $PROJECT_ROOT" >&2
    exit 1
fi

##############################################################################
# PHASE TRACKING
##############################################################################

# Статусы фаз: pending, running, success, failed, skipped
declare -A PHASE_STATUS
declare -A PHASE_NAMES
declare -A PHASE_SCRIPTS
declare -a PHASE_ORDER

PHASE_ORDER=("system" "infra" "project" "monitoring" "verify")

PHASE_NAMES["system"]="Системные пакеты"
PHASE_NAMES["infra"]="Инфраструктура (PostgreSQL + Redis)"
PHASE_NAMES["project"]="Проект (mise + Go/Python/Node.js)"
PHASE_NAMES["monitoring"]="Мониторинг (Prometheus, Grafana)"
PHASE_NAMES["verify"]="Проверка установки"

PHASE_SCRIPTS["system"]="$SCRIPT_DIR/install-system.sh"
PHASE_SCRIPTS["infra"]="$SCRIPT_DIR/install-infra.sh"
PHASE_SCRIPTS["project"]="$SCRIPT_DIR/install.sh"
PHASE_SCRIPTS["monitoring"]="$SCRIPT_DIR/install-monitoring.sh"
PHASE_SCRIPTS["verify"]=""  # Встроенная верификация

# Инициализация статусов
for phase in "${PHASE_ORDER[@]}"; do
    PHASE_STATUS["$phase"]="pending"
done

##############################################################################
# CLI ARGUMENTS
##############################################################################

DRY_RUN=false
VERBOSE=false
NON_INTERACTIVE=false

# Режимы установки
MODE="full"  # full, minimal, system-only, infra-only, project-only, monitoring-only

# Skip флаги
SKIP_SYSTEM=false
SKIP_INFRA=false
SKIP_PROJECT=false
SKIP_MONITORING=false

parse_args() {
    while [[ $# -gt 0 ]]; do
        case $1 in
            --full)
                MODE="full"
                shift
                ;;
            --minimal)
                MODE="minimal"
                SKIP_MONITORING=true
                shift
                ;;
            --system-only)
                MODE="system-only"
                SKIP_INFRA=true
                SKIP_PROJECT=true
                SKIP_MONITORING=true
                shift
                ;;
            --infra-only)
                MODE="infra-only"
                SKIP_SYSTEM=true
                SKIP_PROJECT=true
                SKIP_MONITORING=true
                shift
                ;;
            --project-only)
                MODE="project-only"
                SKIP_SYSTEM=true
                SKIP_INFRA=true
                SKIP_MONITORING=true
                shift
                ;;
            --monitoring-only)
                MODE="monitoring-only"
                SKIP_SYSTEM=true
                SKIP_INFRA=true
                SKIP_PROJECT=true
                shift
                ;;
            --skip-system)
                SKIP_SYSTEM=true
                shift
                ;;
            --skip-infra)
                SKIP_INFRA=true
                shift
                ;;
            --skip-project)
                SKIP_PROJECT=true
                shift
                ;;
            --skip-monitoring)
                SKIP_MONITORING=true
                shift
                ;;
            --non-interactive)
                NON_INTERACTIVE=true
                shift
                ;;
            --dry-run)
                DRY_RUN=true
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
CommandCenter1C - Bootstrap Setup

Единая точка входа для полной установки окружения разработки.

Usage:
  ./scripts/setup/bootstrap.sh [OPTIONS]

Mode Options:
  --full                Полная установка (по умолчанию)
  --minimal             Без мониторинга
  --system-only         Только системные пакеты
  --infra-only          Только PostgreSQL/Redis
  --project-only        Только mise + зависимости проекта
  --monitoring-only     Только мониторинг

Skip Options:
  --skip-system         Пропустить системные пакеты
  --skip-infra          Пропустить инфраструктуру
  --skip-project        Пропустить mise/deps
  --skip-monitoring     Пропустить мониторинг

Other Options:
  --non-interactive     Без подтверждений (для CI)
  --dry-run             Показать план без выполнения
  -v, --verbose         Подробный вывод
  -h, --help            Показать справку

Phases:
  1. System Packages    git, curl, jq, ripgrep, fd, htop, etc.
  2. Infrastructure     PostgreSQL 15 + Redis 7
  3. Project            mise (Go 1.24, Python 3.11, Node.js 20) + deps
  4. Monitoring         Prometheus, Grafana, exporters (optional)
  5. Verification       Проверка всех компонентов

Examples:
  ./scripts/setup/bootstrap.sh                     # Полная установка
  ./scripts/setup/bootstrap.sh --minimal           # Без мониторинга
  ./scripts/setup/bootstrap.sh --dry-run           # Показать план
  ./scripts/setup/bootstrap.sh --non-interactive   # Для CI/CD
  ./scripts/setup/bootstrap.sh --skip-system --skip-monitoring
EOF
}

##############################################################################
# PLATFORM DETECTION
##############################################################################

get_platform_info() {
    local platform
    platform=$(detect_platform)

    case "$platform" in
        wsl-pacman|linux-pacman)
            echo "Arch Linux (WSL)" ;;
        wsl-apt|linux-apt)
            echo "Debian/Ubuntu (WSL)" ;;
        linux-dnf)
            echo "Fedora/RHEL" ;;
        macos)
            echo "macOS" ;;
        *)
            echo "$platform" ;;
    esac
}

##############################################################################
# PHASE CHECKS
##############################################################################

should_run_phase() {
    local phase=$1

    case "$phase" in
        system)
            ! $SKIP_SYSTEM
            ;;
        infra)
            ! $SKIP_INFRA
            ;;
        project)
            ! $SKIP_PROJECT
            ;;
        monitoring)
            ! $SKIP_MONITORING
            ;;
        verify)
            # Verify всегда выполняется если не dry-run
            ! $DRY_RUN
            ;;
        *)
            return 1
            ;;
    esac
}

##############################################################################
# DISPLAY FUNCTIONS
##############################################################################

print_banner() {
    echo ""
    echo -e "${BOLD}================================================================${NC}"
    echo -e "${BOLD}           CommandCenter1C Setup${NC}"
    echo -e "${BOLD}================================================================${NC}"
    echo ""
}

print_platform_info() {
    local platform_name
    platform_name=$(get_platform_info)

    echo -e "${CYAN}Platform:${NC} $platform_name"
    echo -e "${CYAN}Project:${NC}  $PROJECT_ROOT"
    echo -e "${CYAN}Mode:${NC}     $MODE"
    echo ""
}

print_installation_plan() {
    echo -e "${BOLD}Installation Plan:${NC}"
    echo ""

    local idx=1
    for phase in "${PHASE_ORDER[@]}"; do
        local name="${PHASE_NAMES[$phase]}"
        local checkbox

        if should_run_phase "$phase"; then
            checkbox="${GREEN}[x]${NC}"
        else
            checkbox="${DIM}[ ]${NC}"
        fi

        if [[ "$phase" == "monitoring" ]]; then
            echo -e "  $checkbox Phase $idx: $name ${DIM}(optional)${NC}"
        else
            echo -e "  $checkbox Phase $idx: $name"
        fi

        ((idx++))
    done
    echo ""
}

print_phase_header() {
    local phase=$1
    local idx=$2
    local name="${PHASE_NAMES[$phase]}"

    echo ""
    echo -e "${CYAN}================================================================${NC}"
    echo -e "${CYAN}  Phase $idx: $name${NC}"
    echo -e "${CYAN}================================================================${NC}"
    echo ""
}

print_phase_status() {
    local phase=$1
    local status="${PHASE_STATUS[$phase]}"
    local name="${PHASE_NAMES[$phase]}"

    case "$status" in
        success)
            print_status "success" "$name"
            ;;
        failed)
            print_status "error" "$name (FAILED)"
            ;;
        skipped)
            print_status "info" "$name (skipped)"
            ;;
        pending)
            echo -e "  ${DIM}- $name (pending)${NC}"
            ;;
        *)
            echo "  - $name ($status)"
            ;;
    esac
}

##############################################################################
# CONFIRMATION
##############################################################################

confirm_installation() {
    if $NON_INTERACTIVE; then
        log_info "Non-interactive mode: proceeding with installation"
        return 0
    fi

    if $DRY_RUN; then
        log_warning "DRY-RUN mode: no changes will be made"
        return 0
    fi

    echo -e -n "Proceed with installation? [Y/n] "
    read -r response

    case "$response" in
        [nN]|[nN][oO])
            log_info "Installation cancelled by user"
            exit 0
            ;;
        *)
            return 0
            ;;
    esac
}

##############################################################################
# PHASE EXECUTION
##############################################################################

run_phase() {
    local phase=$1
    local idx=$2

    # Проверка нужно ли выполнять фазу
    if ! should_run_phase "$phase"; then
        PHASE_STATUS["$phase"]="skipped"
        return 0
    fi

    PHASE_STATUS["$phase"]="running"
    print_phase_header "$phase" "$idx"

    # Специальная обработка verify фазы
    if [[ "$phase" == "verify" ]]; then
        run_verify_phase
        return $?
    fi

    local script="${PHASE_SCRIPTS[$phase]}"

    # Проверка существования скрипта
    if [[ ! -f "$script" ]]; then
        log_error "Script not found: $script"
        PHASE_STATUS["$phase"]="failed"
        return 1
    fi

    # Проверка исполняемости
    if [[ ! -x "$script" ]]; then
        chmod +x "$script"
    fi

    # Формирование аргументов
    local args=()
    $VERBOSE && args+=("--verbose")
    $DRY_RUN && args+=("--dry-run")

    # Выполнение скрипта
    if "$script" "${args[@]}"; then
        PHASE_STATUS["$phase"]="success"
        return 0
    else
        PHASE_STATUS["$phase"]="failed"
        return 1
    fi
}

##############################################################################
# VERIFICATION PHASE
##############################################################################

run_verify_phase() {
    log_step "Verifying installation..."
    echo ""

    local all_ok=true

    # System packages
    if should_run_phase "system" || [[ "${PHASE_STATUS[system]}" == "success" ]]; then
        verify_system_packages || all_ok=false
    fi

    # Infrastructure
    if should_run_phase "infra" || [[ "${PHASE_STATUS[infra]}" == "success" ]]; then
        verify_infrastructure || all_ok=false
    fi

    # Project tools
    if should_run_phase "project" || [[ "${PHASE_STATUS[project]}" == "success" ]]; then
        verify_project_tools || all_ok=false
    fi

    # Monitoring
    if should_run_phase "monitoring" || [[ "${PHASE_STATUS[monitoring]}" == "success" ]]; then
        verify_monitoring || all_ok=false
    fi

    echo ""

    if $all_ok; then
        PHASE_STATUS["verify"]="success"
        return 0
    else
        PHASE_STATUS["verify"]="failed"
        return 1
    fi
}

verify_system_packages() {
    local packages=("git" "curl" "jq")
    local all_ok=true

    echo -e "${BOLD}System Packages:${NC}"
    for pkg in "${packages[@]}"; do
        if command -v "$pkg" &>/dev/null; then
            local version
            version=$("$pkg" --version 2>/dev/null | head -1 || echo "installed")
            print_status "success" "$pkg: $version"
        else
            print_status "error" "$pkg: not found"
            all_ok=false
        fi
    done
    echo ""

    $all_ok
}

verify_infrastructure() {
    echo -e "${BOLD}Infrastructure:${NC}"
    local all_ok=true

    # PostgreSQL
    if command -v psql &>/dev/null; then
        local pg_version
        pg_version=$(psql --version 2>/dev/null | head -1 || echo "installed")

        if pg_isready -h localhost -p 5432 &>/dev/null; then
            print_status "success" "PostgreSQL: running (localhost:5432)"
        else
            print_status "warning" "PostgreSQL: installed but not running"
        fi
    else
        print_status "error" "PostgreSQL: not installed"
        all_ok=false
    fi

    # Redis
    if command -v redis-cli &>/dev/null; then
        if redis-cli -h localhost -p 6379 ping 2>/dev/null | grep -q "PONG"; then
            print_status "success" "Redis: running (localhost:6379)"
        else
            print_status "warning" "Redis: installed but not running"
        fi
    else
        print_status "error" "Redis: not installed"
        all_ok=false
    fi

    echo ""
    $all_ok
}

verify_project_tools() {
    echo -e "${BOLD}Project Tools:${NC}"
    local all_ok=true

    # mise
    if command -v mise &>/dev/null; then
        local mise_version
        mise_version=$(mise --version 2>/dev/null | head -1)
        print_status "success" "mise: $mise_version"
    else
        print_status "error" "mise: not installed"
        all_ok=false
    fi

    # Go
    if command -v go &>/dev/null; then
        local go_version
        go_version=$(go version 2>/dev/null | awk '{print $3}')
        print_status "success" "Go: $go_version"
    else
        print_status "warning" "Go: not in PATH (run: source ~/.bashrc)"
    fi

    # Python
    if command -v python3 &>/dev/null; then
        local py_version
        py_version=$(python3 --version 2>/dev/null)
        print_status "success" "Python: $py_version"
    else
        print_status "warning" "Python: not in PATH (run: source ~/.bashrc)"
    fi

    # Node.js
    if command -v node &>/dev/null; then
        local node_version
        node_version=$(node --version 2>/dev/null)
        print_status "success" "Node.js: $node_version"
    else
        print_status "warning" "Node.js: not in PATH (run: source ~/.bashrc)"
    fi

    echo ""
    $all_ok
}

verify_monitoring() {
    echo -e "${BOLD}Monitoring:${NC}"
    local all_ok=true

    # Prometheus
    if command -v prometheus &>/dev/null || pacman -Qi prometheus &>/dev/null 2>&1; then
        if systemctl is-active --quiet prometheus 2>/dev/null; then
            print_status "success" "Prometheus: running (localhost:9090)"
        else
            print_status "info" "Prometheus: installed (not running)"
        fi
    else
        print_status "info" "Prometheus: not installed"
    fi

    # Grafana
    if pacman -Qi grafana &>/dev/null 2>&1; then
        if systemctl is-active --quiet grafana 2>/dev/null; then
            print_status "success" "Grafana: running (localhost:3000)"
        else
            print_status "info" "Grafana: installed (not running)"
        fi
    else
        print_status "info" "Grafana: not installed"
    fi

    echo ""
    $all_ok
}

##############################################################################
# FINAL REPORT
##############################################################################

print_final_report() {
    echo ""
    echo -e "${BOLD}================================================================${NC}"
    echo -e "${BOLD}                 Installation Complete${NC}"
    echo -e "${BOLD}================================================================${NC}"
    echo ""

    echo -e "${BOLD}Summary:${NC}"
    echo ""

    for phase in "${PHASE_ORDER[@]}"; do
        print_phase_status "$phase"
    done

    echo ""

    # Проверка были ли ошибки
    local has_failures=false
    for phase in "${PHASE_ORDER[@]}"; do
        if [[ "${PHASE_STATUS[$phase]}" == "failed" ]]; then
            has_failures=true
            break
        fi
    done

    if $has_failures; then
        echo -e "${RED}Some phases failed. Please check the logs above.${NC}"
        echo ""
        return 1
    fi

    # Успешное завершение - показываем следующие шаги
    print_next_steps
}

print_next_steps() {
    echo -e "${BOLD}Next Steps:${NC}"
    echo ""

    echo "  1. Restart terminal or run:"
    echo "     source ~/.bashrc"
    echo ""

    if ! $SKIP_INFRA; then
        echo "  2. Start services:"
        echo "     ./scripts/dev/start-all.sh"
        echo ""

        echo "  3. Open in browser:"
        echo "     http://localhost:5173"
        echo ""
    fi

    if ! $SKIP_MONITORING; then
        echo "  Monitoring (optional):"
        echo "     sudo systemctl start prometheus grafana"
        echo "     http://localhost:9090  # Prometheus"
        echo "     http://localhost:3000  # Grafana (admin/admin)"
        echo ""
    fi
}

##############################################################################
# MAIN
##############################################################################

main() {
    parse_args "$@"

    print_banner
    print_platform_info
    print_installation_plan

    # Подтверждение
    confirm_installation

    # Dry-run: только показать план
    if $DRY_RUN; then
        echo ""
        log_warning "DRY-RUN: No changes were made"
        echo ""
        echo "To proceed with installation, run without --dry-run flag"
        exit 0
    fi

    # Выполнение фаз
    local phase_idx=1
    local has_errors=false

    for phase in "${PHASE_ORDER[@]}"; do
        if ! run_phase "$phase" "$phase_idx"; then
            has_errors=true

            # Остановка при ошибке (кроме verify)
            if [[ "$phase" != "verify" ]]; then
                echo ""
                log_error "Installation stopped at Phase $phase_idx: ${PHASE_NAMES[$phase]}"
                echo ""
                break
            fi
        fi

        ((phase_idx++))
    done

    # Финальный отчет
    print_final_report

    if $has_errors; then
        exit 1
    fi

    exit 0
}

main "$@"
