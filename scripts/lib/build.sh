#!/bin/bash

##############################################################################
# CommandCenter1C - Build Utilities Library
##############################################################################
#
# Утилиты для сборки Go сервисов: умная пересборка с определением изменений.
#
# Usage:
#   source scripts/lib/build.sh
#
# Dependencies:
#   - scripts/lib/core.sh
#   - scripts/lib/platform.sh
#   - scripts/lib/files.sh
#   - scripts/lib/services.sh
#
# Exports:
#   smart_rebuild_services - умная пересборка с определением изменений
#   rebuild_go_services    - пересборка Go сервисов через scripts/build.sh
#
# Required Variables (set before calling functions):
#   PROJECT_ROOT       - корень проекта
#   GO_SERVICES_DIR    - директория Go сервисов
#   GO_SERVICES        - массив имен Go сервисов
#   FORCE_REBUILD      - флаг принудительной пересборки (true/false)
#   NO_REBUILD         - флаг пропуска пересборки (true/false)
#   PARALLEL_BUILD     - флаг параллельной сборки (true/false)
#   REBUILD_SERVICES   - массив сервисов для пересборки (будет заполнен)
#   SKIPPED_SERVICES   - массив пропущенных сервисов (будет заполнен)
#
# Version: 1.0.0
##############################################################################

# Проверка зависимостей
if [[ -z "${CC1C_LIB_CORE_LOADED:-}" ]]; then
    echo "ERROR: build.sh requires core.sh to be loaded first" >&2
    return 1
fi

if [[ -z "${CC1C_LIB_SERVICES_LOADED:-}" ]]; then
    echo "ERROR: build.sh requires services.sh to be loaded first" >&2
    return 1
fi

if [[ -z "${CC1C_LIB_FILES_LOADED:-}" ]]; then
    echo "ERROR: build.sh requires files.sh to be loaded first" >&2
    return 1
fi

# Предотвращение повторного sourcing
if [[ -n "${CC1C_LIB_BUILD_LOADED:-}" ]]; then
    return 0
fi
CC1C_LIB_BUILD_LOADED=true

##############################################################################
# SMART REBUILD
##############################################################################

# smart_rebuild_services - умная пересборка с определением изменений
# Usage: smart_rebuild_services
# Requires:
#   FORCE_REBUILD, NO_REBUILD, PARALLEL_BUILD (флаги)
#   GO_SERVICES (массив сервисов)
#   GO_SERVICES_DIR, PROJECT_ROOT (пути)
#   REBUILD_SERVICES, SKIPPED_SERVICES (массивы, будут заполнены)
# Returns: 0 on success, 1 on error
smart_rebuild_services() {
    print_header "Проверка необходимости пересборки Go сервисов"

    # Если --no-rebuild, пропускаем
    if [[ "${NO_REBUILD:-false}" == "true" ]]; then
        print_status "info" "Пересборка отключена (--no-rebuild)"
        echo ""
        return 0
    fi

    # Если --force-rebuild, пересобрать все
    if [[ "${FORCE_REBUILD:-false}" == "true" ]]; then
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

        local status
        status=$(detect_go_service_changes "$service")

        case "$status" in
            REBUILD_NEEDED)
                print_status "warning" "Обнаружены изменения -> требуется пересборка"
                REBUILD_SERVICES+=("$service")
                ;;
            UP_TO_DATE)
                print_status "success" "Бинарник актуален -> пересборка не требуется"
                SKIPPED_SERVICES+=("$service")
                ;;
            NO_SOURCES)
                print_status "warning" "Исходники не найдены -> пересборка не требуется"
                SKIPPED_SERVICES+=("$service")
                ;;
            *)
                print_status "error" "Неизвестный статус: $status"
                ;;
        esac
        echo ""
    done

    # Проверка изменений в shared/ (для всех сервисов сразу)
    if [[ -d "${GO_SERVICES_DIR:-go-services}/shared" ]]; then
        echo -e "${BLUE}Проверка shared/ модулей...${NC}"

        # Используем кросс-платформенную функцию
        local newest_shared
        newest_shared=$(find_newest_file "${GO_SERVICES_DIR:-go-services}/shared" "*.go")

        if [[ -n "$newest_shared" ]]; then
            # Найти самый старый бинарник
            local oldest_binary=""
            local oldest_time=""

            for service in "${GO_SERVICES[@]}"; do
                local binary_path
                binary_path=$(get_binary_path "$service")

                if [[ -f "$binary_path" ]]; then
                    # Используем кросс-платформенную функцию
                    local binary_time
                    binary_time=$(get_file_mtime "$binary_path")
                    binary_time=${binary_time:-0}

                    if [[ -z "$oldest_time" ]] || [[ "$binary_time" -lt "$oldest_time" ]]; then
                        oldest_binary="$binary_path"
                        oldest_time="$binary_time"
                    fi
                fi
            done

            # Если есть бинарники И shared/ новее самого старого бинарника
            if [[ -n "$oldest_binary" ]] && is_file_newer "$newest_shared" "$oldest_binary"; then
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
            elif [[ -z "$oldest_binary" ]]; then
                log_verbose "shared/ проверка пропущена - бинарники отсутствуют"
            else
                print_status "success" "shared/ модули актуальны"
                echo ""
            fi
        fi
    fi

    # Если есть что пересобирать
    if [[ ${#REBUILD_SERVICES[@]} -gt 0 ]]; then
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
# Requires: REBUILD_SERVICES, PARALLEL_BUILD, PROJECT_ROOT
# Returns: 0 on success, 1 on error
rebuild_go_services() {
    echo -e "${BLUE}Пересборка Go сервисов...${NC}"
    echo ""

    # Проверить что build.sh существует
    if [[ ! -f "${PROJECT_ROOT:-}/scripts/build.sh" ]]; then
        print_status "error" "Скрипт build.sh не найден: ${PROJECT_ROOT:-}/scripts/build.sh"
        return 1
    fi

    # Собрать параметры для build.sh
    local build_args=""

    # Если только один сервис, использовать --service=
    if [[ ${#REBUILD_SERVICES[@]} -eq 1 ]]; then
        build_args="--service=${REBUILD_SERVICES[0]}"

        print_status "info" "Пересборка сервиса: ${REBUILD_SERVICES[0]}"
        echo ""

        # Запустить build.sh
        if bash "${PROJECT_ROOT:-}/scripts/build.sh" $build_args; then
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
        if [[ "${PARALLEL_BUILD:-false}" == "true" ]]; then
            build_args="--parallel"
        fi

        print_status "info" "Пересборка сервисов: ${REBUILD_SERVICES[*]}"
        echo ""

        # Запустить build.sh
        if bash "${PROJECT_ROOT:-}/scripts/build.sh" $build_args; then
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
# End of build.sh
##############################################################################
