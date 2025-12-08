#!/bin/bash

##############################################################################
# CommandCenter1C - Restart All Services with Smart Rebuild
##############################################################################
# Умный перезапуск всех сервисов с автоматическим определением изменений
# и выборочной пересборкой Go сервисов
#
# Usage:
#   ./scripts/dev/restart-all.sh                    # Smart restart
#   ./scripts/dev/restart-all.sh --force-rebuild    # Force rebuild all Go
#   ./scripts/dev/restart-all.sh --no-rebuild       # Skip rebuild
#   ./scripts/dev/restart-all.sh --service=worker   # Single service
#   ./scripts/dev/restart-all.sh --parallel-build   # Parallel rebuild
#   ./scripts/dev/restart-all.sh --verbose          # Detailed output
#   ./scripts/dev/restart-all.sh --help             # Show help
##############################################################################

set -e

##############################################################################
# [СЕКЦИЯ 1: INITIALIZATION]
##############################################################################

# Source library
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/../lib/init.sh"

# Project-specific constants
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
GO_SERVICES_DIR="$PROJECT_ROOT/go-services"
BIN_DIR="$PROJECT_ROOT/bin"
PIDS_DIR="$PROJECT_ROOT/pids"
LOGS_DIR="$PROJECT_ROOT/logs"
SCRIPTS_DIR="$PROJECT_ROOT/scripts/dev"

# Список Go сервисов (в порядке приоритета)
GO_SERVICES=("api-gateway" "worker" "ras-adapter" "batch-service")

# Изменить рабочую директорию на PROJECT_ROOT
cd "$PROJECT_ROOT"

# Load environment variables from .env.local
load_env_file

# Флаги по умолчанию
FORCE_REBUILD=false
NO_REBUILD=false
PARALLEL_BUILD=false
SINGLE_SERVICE=""
VERBOSE=false

# Массивы для отчетности
declare -a REBUILD_SERVICES=()
declare -a SKIPPED_SERVICES=()

##############################################################################
# [СЕКЦИЯ 2: HELP FUNCTION]
##############################################################################

show_help() {
    echo -e "${BLUE}CommandCenter1C - Restart All Services with Smart Rebuild${NC}"
    echo ""
    echo "Умный перезапуск всех сервисов с автоматическим определением изменений"
    echo "и выборочной пересборкой Go сервисов."
    echo ""
    echo "Usage: $0 [OPTIONS]"
    echo ""
    echo "Options:"
    echo "  --help                   Показать эту справку"
    echo "  --force-rebuild          Принудительно пересобрать все Go сервисы"
    echo "  --no-rebuild             Только перезапуск, без проверки/пересборки"
    echo "  --parallel-build         Параллельная пересборка (через build.sh --parallel)"
    echo "  --service=<name>         Перезапустить только один сервис"
    echo "  --verbose                Детальный вывод для отладки"
    echo ""
    echo "Examples:"
    echo "  $0                           # Smart restart (обнаружение изменений)"
    echo "  $0 --force-rebuild           # Принудительная пересборка всех Go"
    echo "  $0 --no-rebuild              # Только перезапуск, без rebuild"
    echo "  $0 --service=api-gateway     # Перезапуск только API Gateway"
    echo "  $0 --parallel-build          # Параллельная пересборка"
    echo "  $0 --verbose                 # Детальный вывод"
    echo ""
    echo "Available services:"
    echo "  orchestrator, api-gateway, worker,"
    echo "  ras-adapter, batch-service, frontend"
    echo ""
}

##############################################################################
# [СЕКЦИЯ 3: RESTART LOGIC]
##############################################################################

restart_all_services() {
    print_header "Перезапуск всех сервисов"

    # Шаг 1: Остановка всех сервисов
    print_status "info" "Остановка всех сервисов..."
    echo ""

    if bash "$SCRIPTS_DIR/stop-all.sh"; then
        print_status "success" "Все сервисы остановлены"
        echo ""
    else
        print_status "error" "Ошибка при остановке сервисов"
        return 1
    fi

    # Небольшая задержка для корректного освобождения портов
    sleep 2

    # Шаг 2: Запуск всех сервисов
    print_status "info" "Запуск всех сервисов..."
    echo ""

    if bash "$SCRIPTS_DIR/start-all.sh"; then
        print_status "success" "Все сервисы запущены"
        echo ""
        return 0
    else
        print_status "error" "Ошибка при запуске сервисов"
        return 1
    fi
}

restart_single_service() {
    local service=$1

    print_header "Перезапуск сервиса: $service"

    # Если это Go сервис и он в списке для пересборки
    if [[ " ${GO_SERVICES[@]} " =~ " ${service} " ]] && [[ " ${REBUILD_SERVICES[@]} " =~ " ${service} " ]]; then
        print_status "info" "Пересборка $service перед перезапуском..."
        echo ""

        if bash "$PROJECT_ROOT/scripts/build.sh" --service="$service"; then
            print_status "success" "Сервис $service успешно пересобран"
            echo ""
        else
            print_status "error" "Ошибка при пересборке $service"
            return 1
        fi
    fi

    # Перезапуск через restart.sh
    print_status "info" "Перезапуск $service..."
    echo ""

    if bash "$SCRIPTS_DIR/restart.sh" "$service"; then
        print_status "success" "Сервис $service успешно перезапущен"
        echo ""
        return 0
    else
        print_status "error" "Ошибка при перезапуске $service"
        return 1
    fi
}

##############################################################################
# [СЕКЦИЯ 4: REPORTING]
##############################################################################

show_rebuild_summary() {
    print_header "Итоговая сводка"

    echo -e "${BLUE}Статус пересборки Go сервисов:${NC}"
    echo ""

    if [ ${#REBUILD_SERVICES[@]} -gt 0 ]; then
        echo -e "${YELLOW}Пересобранные сервисы (${#REBUILD_SERVICES[@]}):${NC}"
        for service in "${REBUILD_SERVICES[@]}"; do
            echo -e "  ${GREEN}✓${NC} $service"
        done
        echo ""
    fi

    if [ ${#SKIPPED_SERVICES[@]} -gt 0 ]; then
        echo -e "${BLUE}Пропущенные сервисы (${#SKIPPED_SERVICES[@]}):${NC}"
        for service in "${SKIPPED_SERVICES[@]}"; do
            echo -e "  ${BLUE}ℹ${NC} $service (бинарник актуален)"
        done
        echo ""
    fi

    echo -e "${BLUE}Управление:${NC}"
    echo -e "  Просмотр логов:   ${GREEN}./scripts/dev/logs.sh <service>${NC}"
    echo -e "  Health check:     ${GREEN}./scripts/dev/health-check.sh${NC}"
    echo -e "  Остановка всех:   ${GREEN}./scripts/dev/stop-all.sh${NC}"
    echo ""
}

##############################################################################
# [СЕКЦИЯ 5: ARGUMENT PARSING]
##############################################################################

parse_arguments() {
    while [[ $# -gt 0 ]]; do
        case $1 in
            --help)
                show_help
                exit 0
                ;;
            --force-rebuild)
                FORCE_REBUILD=true
                shift
                ;;
            --no-rebuild)
                NO_REBUILD=true
                shift
                ;;
            --parallel-build)
                PARALLEL_BUILD=true
                shift
                ;;
            --service=*)
                SINGLE_SERVICE="${1#*=}"
                shift
                ;;
            --verbose)
                VERBOSE=true
                shift
                ;;
            *)
                echo -e "${RED}Неизвестный флаг: $1${NC}"
                echo ""
                show_help
                exit 1
                ;;
        esac
    done

    # Валидация: --force-rebuild и --no-rebuild конфликтуют
    if [ "$FORCE_REBUILD" = true ] && [ "$NO_REBUILD" = true ]; then
        echo -e "${RED}Ошибка: Флаги --force-rebuild и --no-rebuild несовместимы${NC}"
        exit 1
    fi
}

##############################################################################
# [СЕКЦИЯ 6: MAIN LOGIC]
##############################################################################

main() {
    # Парсинг аргументов
    parse_arguments "$@"

    print_header "CommandCenter1C - Smart Restart"

    # Вывести параметры в verbose режиме
    if [ "$VERBOSE" = true ]; then
        log_verbose "Параметры:"
        log_verbose "  FORCE_REBUILD: $FORCE_REBUILD"
        log_verbose "  NO_REBUILD: $NO_REBUILD"
        log_verbose "  PARALLEL_BUILD: $PARALLEL_BUILD"
        log_verbose "  SINGLE_SERVICE: $SINGLE_SERVICE"
        log_verbose ""
    fi

    # Режим: перезапуск одного сервиса
    if [ -n "$SINGLE_SERVICE" ]; then
        # Для Go сервисов: умная проверка изменений
        if [[ " ${GO_SERVICES[@]} " =~ " ${SINGLE_SERVICE} " ]] && [ "$NO_REBUILD" = false ]; then
            echo -e "${BLUE}Проверка изменений для $SINGLE_SERVICE...${NC}"
            echo ""

            local status=$(detect_go_service_changes "$SINGLE_SERVICE")

            case "$status" in
                REBUILD_NEEDED)
                    print_status "warning" "Обнаружены изменения → требуется пересборка"
                    REBUILD_SERVICES+=("$SINGLE_SERVICE")
                    echo ""
                    ;;
                UP_TO_DATE)
                    if [ "$FORCE_REBUILD" = true ]; then
                        print_status "info" "Принудительная пересборка (--force-rebuild)"
                        REBUILD_SERVICES+=("$SINGLE_SERVICE")
                    else
                        print_status "success" "Бинарник актуален → пересборка не требуется"
                    fi
                    echo ""
                    ;;
                NO_SOURCES)
                    print_status "warning" "Исходники не найдены → пересборка не требуется"
                    echo ""
                    ;;
            esac
        fi

        # Перезапуск одного сервиса
        if restart_single_service "$SINGLE_SERVICE"; then
            print_status "success" "Сервис $SINGLE_SERVICE успешно перезапущен"
            exit 0
        else
            print_status "error" "Ошибка при перезапуске $SINGLE_SERVICE"
            exit 1
        fi
    fi

    # Режим: перезапуск всех сервисов
    # Note: Генерация конфигурации выполняется в start-all.sh (Phase 1.5a)

    # Шаг 1: Умная пересборка Go сервисов
    if ! smart_rebuild_services; then
        print_status "error" "Ошибка при пересборке Go сервисов"
        exit 1
    fi

    # Шаг 2: Перезапуск всех сервисов
    if ! restart_all_services; then
        print_status "error" "Ошибка при перезапуске сервисов"
        exit 1
    fi

    # Шаг 3: Итоговая сводка
    show_rebuild_summary

    print_header "Перезапуск завершен успешно"

    exit 0
}

##############################################################################
# Entry point
##############################################################################

main "$@"
