#!/bin/bash

##############################################################################
# CommandCenter1C - Bootstrap Script
##############################################################################
#
# Полная инициализация окружения разработки от нуля до работающей системы.
#
# Этапы:
#   1. Prerequisites  - mise + Go/Python/Node/Docker через install.sh
#   2. Dependencies   - pip + npm + go mod
#   3. Build          - Go бинарники (smart rebuild)
#   4. Docker         - PostgreSQL + Redis containers
#   5. Migrations     - Django migrate
#   6. Services       - start-all.sh --no-rebuild
#
# Состояние хранится в .bootstrap/ (маркеры завершенных этапов).
#
# Usage:
#   ./scripts/dev/bootstrap.sh [OPTIONS]
#
# Options:
#   --skip-prerequisites    Пропустить проверку инструментов
#   --skip-deps             Пропустить pip/npm/go mod
#   --skip-build            Пропустить сборку Go
#   --skip-docker           Пропустить Docker
#   --skip-migrations       Пропустить миграции
#   --only-check            Только проверить, не запускать сервисы
#   --force                 Принудительно всё переделать
#   --force-rebuild         Только пересобрать Go
#   --reset                 Сбросить состояние (.bootstrap/)
#   --verbose, -v           Подробный вывод
#   --help, -h              Справка
#
# Version: 1.0.0
##############################################################################

set -e

##############################################################################
# DIRECTORIES
##############################################################################

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
BOOTSTRAP_DIR="$PROJECT_ROOT/.bootstrap"

##############################################################################
# SOURCE LIBRARIES
##############################################################################

# Единая библиотека (core, platform, files, services, build)
if [[ -f "$PROJECT_ROOT/scripts/lib/init.sh" ]]; then
    source "$PROJECT_ROOT/scripts/lib/init.sh"
else
    echo "FATAL: scripts/lib/init.sh not found" >&2
    exit 1
fi

# Bootstrap-специфичная логика (parse_bootstrap_args, функции bootstrap)
if [[ -f "$SCRIPT_DIR/lib/bootstrap-lib.sh" ]]; then
    source "$SCRIPT_DIR/lib/bootstrap-lib.sh"
else
    log_error "bootstrap-lib.sh не найден: $SCRIPT_DIR/lib/bootstrap-lib.sh"
    exit 1
fi

##############################################################################
# PROJECT CONFIGURATION (для smart_rebuild_services)
##############################################################################

GO_SERVICES_DIR="$PROJECT_ROOT/go-services"
BIN_DIR="$PROJECT_ROOT/bin"

# Список Go сервисов (в порядке приоритета)
GO_SERVICES=("api-gateway" "worker" "ras-adapter" "batch-service")

##############################################################################
# ERROR HANDLING
##############################################################################

CURRENT_STAGE=""

trap_handler() {
    local exit_code=$?

    # Убить спиннер если запущен (из prompts.sh)
    if [[ -n "${_SPINNER_PID:-}" ]]; then
        kill "$_SPINNER_PID" 2>/dev/null || true
        wait "$_SPINNER_PID" 2>/dev/null || true
        printf "\r%*s\r" 80 ""  # Очистить строку
    fi

    if [[ $exit_code -ne 0 ]]; then
        echo ""
        log_error "Bootstrap прерван на этапе: ${CURRENT_STAGE:-unknown}"
        log_error "Код выхода: $exit_code"
        echo ""
        echo "Для отладки используйте: --verbose"
        echo "Для повторной попытки: ./scripts/dev/bootstrap.sh"
        echo "Для сброса состояния: ./scripts/dev/bootstrap.sh --reset"
    fi
    exit $exit_code
}

trap trap_handler EXIT INT TERM

##############################################################################
# MAIN EXECUTION
##############################################################################

main() {
    # Парсинг аргументов
    parse_bootstrap_args "$@"

    # Handle --reset
    if [[ "$RESET_STATE" == "true" ]]; then
        log_info "Сброс состояния bootstrap..."
        if [[ -d "$BOOTSTRAP_DIR" ]]; then
            safe_rm "$BOOTSTRAP_DIR" "true"
            log_success "Директория $BOOTSTRAP_DIR удалена"
        else
            log_info "Директория $BOOTSTRAP_DIR не существует"
        fi
        exit 0
    fi

    # Header
    echo ""
    echo -e "${BOLD}================================================================${NC}"
    echo -e "${BOLD}  CommandCenter1C - Bootstrap${NC}"
    echo -e "${BOLD}================================================================${NC}"
    echo ""
    log_info "Проект: $PROJECT_ROOT"
    log_info "Платформа: $(detect_platform 2>/dev/null || echo "unknown")"
    echo ""

    # Создать директорию .bootstrap/
    init_bootstrap_dir

    ##########################################################################
    # Stage 0: Environment (.env.local)
    ##########################################################################
    CURRENT_STAGE="environment"
    log_info "Проверка .env.local..."

    if ! ensure_env_local; then
        log_error "Ошибка настройки .env.local"
        exit 1
    fi
    echo ""

    ##########################################################################
    # Stage 1: Prerequisites
    ##########################################################################
    CURRENT_STAGE="prerequisites"
    echo -e "${BLUE}[1/6] Prerequisites (mise, Go, Python, Node, Docker)${NC}"

    if should_skip "prerequisites"; then
        log_info "Пропущено (--skip-prerequisites или уже выполнено)"
    else
        # Сначала проверим текущее состояние
        if verify_prerequisites; then
            log_success "Все инструменты уже установлены"
            mark_stage_done "prerequisites"
        else
            log_info "Запуск install.sh --skip-deps..."

            if [[ -f "$PROJECT_ROOT/scripts/setup/install.sh" ]]; then
                local install_args="--skip-deps"
                [[ "$VERBOSE" == "true" ]] && install_args="$install_args --verbose"

                if ! bash "$PROJECT_ROOT/scripts/setup/install.sh" $install_args; then
                    log_error "install.sh завершился с ошибкой"
                    exit 1
                fi

                # Активировать mise для текущей сессии
                eval "$(mise activate bash 2>/dev/null)" || true

                mark_stage_done "prerequisites"
                log_success "Prerequisites установлены"
            else
                log_error "install.sh не найден: $PROJECT_ROOT/scripts/setup/install.sh"
                exit 1
            fi
        fi

        # Настроить глобальные симлинки для python/go
        # (для Claude Code субагентов и скриптов без доступа к mise shims)
        setup_global_symlinks
    fi
    echo ""

    ##########################################################################
    # Stage 2: Dependencies
    ##########################################################################
    CURRENT_STAGE="deps"
    echo -e "${BLUE}[2/6] Dependencies (pip, npm, go mod)${NC}"

    if should_skip "deps"; then
        log_info "Пропущено (--skip-deps или уже выполнено)"
    else
        # Умная проверка актуальности
        if [[ "$FORCE" != "true" ]] && deps_up_to_date; then
            log_info "Зависимости актуальны"
        else
            install_python_deps
            install_node_deps
            install_go_deps
            mark_stage_done "deps"
        fi
    fi
    echo ""

    ##########################################################################
    # Stage 3: Build Go Services
    ##########################################################################
    CURRENT_STAGE="build"
    echo -e "${BLUE}[3/6] Build (Go services)${NC}"

    if should_skip "build"; then
        log_info "Пропущено (--skip-build или уже выполнено)"
    else
        # Инициализация массивов для smart_rebuild_services
        REBUILD_SERVICES=()
        SKIPPED_SERVICES=()

        # Установить флаги для smart_rebuild_services
        NO_REBUILD=false
        PARALLEL_BUILD=false

        # Вызов smart_rebuild_services из scripts/lib/build.sh
        if smart_rebuild_services; then
            mark_stage_done "build"
        else
            log_error "Ошибка при сборке Go сервисов"
            exit 1
        fi
    fi
    echo ""

    ##########################################################################
    # Stage 4: Docker Infrastructure
    ##########################################################################
    CURRENT_STAGE="docker"
    echo -e "${BLUE}[4/6] Docker (PostgreSQL, Redis)${NC}"

    if should_skip "docker"; then
        log_info "Пропущено (--skip-docker или уже выполнено)"
    else
        if start_docker_infrastructure; then
            mark_stage_done "docker"
        else
            log_error "Ошибка при запуске Docker инфраструктуры"
            exit 1
        fi
    fi
    echo ""

    ##########################################################################
    # Stage 5: Django Migrations
    ##########################################################################
    CURRENT_STAGE="migrations"
    echo -e "${BLUE}[5/6] Migrations (Django)${NC}"

    if should_skip "migrations"; then
        log_info "Пропущено (--skip-migrations или уже выполнено)"
    else
        # Загрузить переменные окружения
        if [[ -f "$PROJECT_ROOT/.env.local" ]]; then
            set -a
            source "$PROJECT_ROOT/.env.local"
            set +a
        fi

        if run_django_migrations; then
            mark_stage_done "migrations"
        else
            log_error "Ошибка при применении миграций"
            exit 1
        fi
    fi
    echo ""

    ##########################################################################
    # Stage 6: Start Services
    ##########################################################################
    CURRENT_STAGE="services"
    echo -e "${BLUE}[6/6] Services${NC}"

    if [[ "$ONLY_CHECK" == "true" ]]; then
        log_info "Пропущено (--only-check)"
    else
        log_info "Запуск сервисов через start-all.sh --no-rebuild..."

        if [[ -f "$SCRIPT_DIR/start-all.sh" ]]; then
            if ! bash "$SCRIPT_DIR/start-all.sh" --no-rebuild; then
                log_error "start-all.sh завершился с ошибкой"
                exit 1
            fi
        else
            log_error "start-all.sh не найден: $SCRIPT_DIR/start-all.sh"
            exit 1
        fi
    fi
    echo ""

    ##########################################################################
    # Final Report
    ##########################################################################
    CURRENT_STAGE="report"
    print_bootstrap_report
}

# Entry point
main "$@"
