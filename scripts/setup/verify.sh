#!/bin/bash

##############################################################################
# CommandCenter1C - Environment Verification Script
##############################################################################
#
# Проверяет что все компоненты установлены и работают.
# Используется после install.sh или для диагностики проблем.
#
# Usage:
#   ./scripts/setup/verify.sh [OPTIONS]
#
# Options:
#   --quick          Только критичные проверки (без мониторинга)
#   --json           Вывод в JSON формате
#   --fix            Попытаться исправить проблемы
#   -v, --verbose    Подробный вывод
#   -h, --help       Показать справку
#
# Exit codes:
#   0 - все проверки прошли
#   1 - есть критичные ошибки (инфраструктура не работает)
#   2 - есть некритичные ошибки (мониторинг не работает)
#
# Examples:
#   ./scripts/setup/verify.sh                 # Полная проверка
#   ./scripts/setup/verify.sh --quick         # Только критичные
#   ./scripts/setup/verify.sh --json          # JSON вывод
#   ./scripts/setup/verify.sh --fix           # Попробовать починить
#
# Version: 1.0.0
##############################################################################

# Не используем set -e чтобы скрипт продолжал работу при ошибках проверок

# Версия скрипта
SCRIPT_VERSION="1.0.0"

# Директории
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

# Подключение единой библиотеки
if [[ -f "$PROJECT_ROOT/scripts/lib/init.sh" ]]; then
    source "$PROJECT_ROOT/scripts/lib/init.sh"
else
    echo "FATAL: scripts/lib/init.sh not found in $PROJECT_ROOT" >&2
    exit 1
fi

# Подключение postgres helpers
if [[ -f "$PROJECT_ROOT/scripts/setup/lib/postgres.sh" ]]; then
    source "$PROJECT_ROOT/scripts/setup/lib/postgres.sh"
fi

##############################################################################
# CLI ARGUMENTS
##############################################################################

QUICK_MODE=false
JSON_OUTPUT=false
FIX_MODE=false
VERBOSE=false

parse_args() {
    while [[ $# -gt 0 ]]; do
        case $1 in
            --quick)       QUICK_MODE=true; shift ;;
            --json)        JSON_OUTPUT=true; shift ;;
            --fix)         FIX_MODE=true; shift ;;
            --verbose|-v)  VERBOSE=true; shift ;;
            --help|-h)     show_help; exit 0 ;;
            *)
                log_error "Unknown option: $1"
                show_help
                exit 1
                ;;
        esac
    done
}

show_help() {
    cat << EOF
CommandCenter1C - Environment Verification Script v${SCRIPT_VERSION}

Usage: $(basename "$0") [OPTIONS]

Options:
  --quick          Only critical checks (skip monitoring)
  --json           Output in JSON format
  --fix            Attempt to fix issues (start stopped services)
  -v, --verbose    Verbose output
  -h, --help       Show this help

Exit codes:
  0 - All checks passed
  1 - Critical errors (infrastructure not working)
  2 - Non-critical errors (monitoring not working)

Examples:
  $(basename "$0")                  # Full verification
  $(basename "$0") --quick          # Only critical checks
  $(basename "$0") --json           # JSON output
  $(basename "$0") --fix            # Try to fix issues
EOF
}

##############################################################################
# COUNTERS & RESULTS
##############################################################################

TOTAL_CHECKS=0
PASSED_CHECKS=0
CRITICAL_FAILURES=0
NONCRITICAL_FAILURES=0

# Массивы для JSON вывода
declare -a JSON_RESULTS=()

# Добавление результата проверки
add_result() {
    local category=$1
    local name=$2
    local status=$3        # pass | fail
    local critical=$4      # true | false
    local version=${5:-""}
    local message=${6:-""}

    ((TOTAL_CHECKS++))

    if [[ "$status" == "pass" ]]; then
        ((PASSED_CHECKS++))
    else
        if [[ "$critical" == "true" ]]; then
            ((CRITICAL_FAILURES++))
        else
            ((NONCRITICAL_FAILURES++))
        fi
    fi

    # JSON формат
    local json_entry
    json_entry="{\"category\":\"${category}\",\"name\":\"${name}\",\"status\":\"${status}\",\"critical\":${critical},\"version\":\"${version}\",\"message\":\"${message}\"}"
    JSON_RESULTS+=("$json_entry")
}

##############################################################################
# OUTPUT FUNCTIONS
##############################################################################

# Символы для вывода
CHECK_MARK="+"
CROSS_MARK="x"
WARN_MARK="!"

print_check_result() {
    local status=$1
    local name=$2
    local details=${3:-""}

    if [[ "$JSON_OUTPUT" == "true" ]]; then
        return
    fi

    case "$status" in
        pass)
            echo -e "  ${GREEN}${CHECK_MARK}${NC} ${name}${details:+ (${details})}"
            ;;
        fail)
            echo -e "  ${RED}${CROSS_MARK}${NC} ${name}${details:+ - ${details}}"
            ;;
        warn)
            echo -e "  ${YELLOW}${WARN_MARK}${NC} ${name}${details:+ - ${details}}"
            ;;
    esac
}

print_section() {
    local title=$1

    if [[ "$JSON_OUTPUT" == "true" ]]; then
        return
    fi

    echo ""
    echo -e "${CYAN}${title}:${NC}"
}

##############################################################################
# VERSION HELPERS
##############################################################################

# Получение версии команды
get_cmd_version() {
    local cmd=$1
    local version=""

    case "$cmd" in
        git)
            version=$(git --version 2>/dev/null | grep -oE '[0-9]+\.[0-9]+(\.[0-9]+)?' | head -1)
            ;;
        curl)
            version=$(curl --version 2>/dev/null | head -1 | grep -oE '[0-9]+\.[0-9]+(\.[0-9]+)?' | head -1)
            ;;
        wget)
            version=$(wget --version 2>/dev/null | head -1 | grep -oE '[0-9]+\.[0-9]+(\.[0-9]+)?' | head -1)
            ;;
        jq)
            version=$(jq --version 2>/dev/null | grep -oE '[0-9]+\.[0-9]+(\.[0-9]+)?' | head -1)
            ;;
        fd)
            version=$(fd --version 2>/dev/null | grep -oE '[0-9]+\.[0-9]+(\.[0-9]+)?' | head -1)
            ;;
        rg|ripgrep)
            version=$(rg --version 2>/dev/null | head -1 | grep -oE '[0-9]+\.[0-9]+(\.[0-9]+)?' | head -1)
            ;;
        mise)
            version=$(mise --version 2>/dev/null | grep -oE '[0-9]+\.[0-9]+(\.[0-9]+)?' | head -1)
            ;;
        go)
            version=$(go version 2>/dev/null | grep -oE '[0-9]+\.[0-9]+(\.[0-9]+)?' | head -1)
            ;;
        python|python3)
            version=$(python3 --version 2>/dev/null | grep -oE '[0-9]+\.[0-9]+(\.[0-9]+)?' | head -1)
            ;;
        node|nodejs)
            version=$(node --version 2>/dev/null | grep -oE '[0-9]+\.[0-9]+(\.[0-9]+)?' | head -1)
            ;;
        psql)
            version=$(psql --version 2>/dev/null | grep -oE '[0-9]+(\.[0-9]+)?' | head -1)
            ;;
        redis-cli)
            version=$(redis-cli --version 2>/dev/null | grep -oE '[0-9]+\.[0-9]+(\.[0-9]+)?' | head -1)
            ;;
        prometheus)
            version=$(prometheus --version 2>/dev/null | head -1 | grep -oE '[0-9]+\.[0-9]+(\.[0-9]+)?' | head -1)
            ;;
        grafana-server)
            version=$(grafana-server -v 2>/dev/null | grep -oE '[0-9]+\.[0-9]+(\.[0-9]+)?' | head -1)
            ;;
        *)
            version=$($cmd --version 2>/dev/null | grep -oE '[0-9]+\.[0-9]+(\.[0-9]+)?' | head -1)
            ;;
    esac

    echo "$version"
}

##############################################################################
# CHECK FUNCTIONS
##############################################################################

# Проверка системных пакетов
check_system_packages() {
    print_section "System Packages"

    local packages=("git" "curl" "wget" "jq")

    for pkg in "${packages[@]}"; do
        if command -v "$pkg" &>/dev/null; then
            local version
            version=$(get_cmd_version "$pkg")
            print_check_result "pass" "$pkg" "$version"
            add_result "system_packages" "$pkg" "pass" "true" "$version" ""
        else
            print_check_result "fail" "$pkg" "NOT INSTALLED"
            add_result "system_packages" "$pkg" "fail" "true" "" "Not installed"
        fi
    done

    # Опциональные пакеты (не критичные)
    local optional_packages=("fd" "rg")

    for pkg in "${optional_packages[@]}"; do
        if command -v "$pkg" &>/dev/null; then
            local version
            version=$(get_cmd_version "$pkg")
            print_check_result "pass" "$pkg" "$version"
            add_result "system_packages" "$pkg" "pass" "false" "$version" ""
        else
            print_check_result "warn" "$pkg" "NOT INSTALLED (optional)"
            add_result "system_packages" "$pkg" "fail" "false" "" "Not installed (optional)"
        fi
    done
}

# Проверка инфраструктуры
check_infrastructure() {
    print_section "Infrastructure"

    # PostgreSQL
    if command -v psql &>/dev/null; then
        local pg_version
        pg_version=$(get_cmd_version "psql")

        if pg_is_running 2>/dev/null; then
            print_check_result "pass" "PostgreSQL ($pg_version)" "running"
            add_result "infrastructure" "postgresql" "pass" "true" "$pg_version" "running"

            # Проверка подключения
            if pg_isready -h localhost -p 5432 &>/dev/null; then
                print_check_result "pass" "PostgreSQL connection" "localhost:5432"
                add_result "infrastructure" "postgresql_connection" "pass" "true" "" "localhost:5432"

                # Проверка пользователя commandcenter
                if pg_user_exists "commandcenter" 2>/dev/null; then
                    print_check_result "pass" "User 'commandcenter'" "exists"
                    add_result "infrastructure" "user_commandcenter" "pass" "true" "" "exists"
                else
                    print_check_result "fail" "User 'commandcenter'" "NOT EXISTS"
                    add_result "infrastructure" "user_commandcenter" "fail" "true" "" "User not created"

                    if [[ "$FIX_MODE" == "true" ]]; then
                        log_info "Attempting to create user 'commandcenter'..."
                        if pg_create_user "commandcenter" "commandcenter" 2>/dev/null; then
                            print_check_result "pass" "User 'commandcenter'" "CREATED"
                        fi
                    fi
                fi

                # Проверка базы commandcenter
                if pg_database_exists "commandcenter" 2>/dev/null; then
                    print_check_result "pass" "Database 'commandcenter'" "exists"
                    add_result "infrastructure" "database_commandcenter" "pass" "true" "" "exists"
                else
                    print_check_result "fail" "Database 'commandcenter'" "NOT EXISTS"
                    add_result "infrastructure" "database_commandcenter" "fail" "true" "" "Database not created"

                    if [[ "$FIX_MODE" == "true" ]]; then
                        log_info "Attempting to create database 'commandcenter'..."
                        # Создаем пользователя если его нет
                        pg_user_exists "commandcenter" 2>/dev/null || pg_create_user "commandcenter" "commandcenter" 2>/dev/null
                        if pg_create_database "commandcenter" "commandcenter" 2>/dev/null; then
                            print_check_result "pass" "Database 'commandcenter'" "CREATED"
                        fi
                    fi
                fi
            else
                print_check_result "fail" "PostgreSQL connection" "FAILED"
                add_result "infrastructure" "postgresql_connection" "fail" "true" "" "Connection failed"
            fi
        else
            print_check_result "fail" "PostgreSQL ($pg_version)" "NOT RUNNING"
            add_result "infrastructure" "postgresql" "fail" "true" "$pg_version" "Not running"

            if [[ "$FIX_MODE" == "true" ]]; then
                log_info "Attempting to start PostgreSQL..."
                if pg_start 2>/dev/null; then
                    print_check_result "pass" "PostgreSQL" "STARTED"
                fi
            fi
        fi
    else
        print_check_result "fail" "PostgreSQL" "NOT INSTALLED"
        add_result "infrastructure" "postgresql" "fail" "true" "" "Not installed"
    fi

    # Redis
    if command -v redis-cli &>/dev/null; then
        local redis_version
        redis_version=$(get_cmd_version "redis-cli")

        if check_systemd_service "redis" 2>/dev/null; then
            local ping_result
            ping_result=$(redis-cli ping 2>/dev/null)

            if [[ "$ping_result" == "PONG" ]]; then
                print_check_result "pass" "Redis ($redis_version)" "running (PONG)"
                add_result "infrastructure" "redis" "pass" "true" "$redis_version" "running"
            else
                print_check_result "warn" "Redis ($redis_version)" "running but not responding"
                add_result "infrastructure" "redis" "fail" "true" "$redis_version" "Not responding"
            fi
        else
            print_check_result "fail" "Redis ($redis_version)" "NOT RUNNING"
            add_result "infrastructure" "redis" "fail" "true" "$redis_version" "Not running"

            if [[ "$FIX_MODE" == "true" ]]; then
                log_info "Attempting to start Redis..."
                if start_systemd_service "redis" 2>/dev/null; then
                    print_check_result "pass" "Redis" "STARTED"
                fi
            fi
        fi
    else
        print_check_result "fail" "Redis" "NOT INSTALLED"
        add_result "infrastructure" "redis" "fail" "true" "" "Not installed"
    fi
}

# Проверка рантаймов (mise)
check_runtimes() {
    print_section "Runtimes (mise)"

    # mise
    if is_mise_installed; then
        local mise_version
        mise_version=$(get_cmd_version "mise")
        print_check_result "pass" "mise" "$mise_version"
        add_result "runtimes" "mise" "pass" "true" "$mise_version" ""

        # Чтение .tool-versions
        local tool_versions_file="$PROJECT_ROOT/.tool-versions"
        if [[ -f "$tool_versions_file" ]]; then

            # Go
            local required_go
            required_go=$(grep "^go " "$tool_versions_file" 2>/dev/null | awk '{print $2}')
            if command -v go &>/dev/null; then
                local actual_go
                actual_go=$(get_cmd_version "go")
                if [[ -n "$required_go" ]] && [[ "$actual_go" == "$required_go"* ]]; then
                    print_check_result "pass" "Go" "$actual_go"
                    add_result "runtimes" "go" "pass" "true" "$actual_go" ""
                elif [[ -n "$actual_go" ]]; then
                    print_check_result "warn" "Go" "$actual_go (expected: $required_go)"
                    add_result "runtimes" "go" "pass" "false" "$actual_go" "Version mismatch"
                else
                    print_check_result "fail" "Go" "NOT WORKING"
                    add_result "runtimes" "go" "fail" "true" "" "Not working"
                fi
            else
                print_check_result "fail" "Go" "NOT INSTALLED"
                add_result "runtimes" "go" "fail" "true" "" "Not installed"
            fi

            # Python
            local required_python
            required_python=$(grep "^python " "$tool_versions_file" 2>/dev/null | awk '{print $2}')
            if command -v python3 &>/dev/null; then
                local actual_python
                actual_python=$(get_cmd_version "python3")
                if [[ -n "$required_python" ]] && [[ "$actual_python" == "$required_python"* ]]; then
                    print_check_result "pass" "Python" "$actual_python"
                    add_result "runtimes" "python" "pass" "true" "$actual_python" ""
                elif [[ -n "$actual_python" ]]; then
                    print_check_result "warn" "Python" "$actual_python (expected: $required_python)"
                    add_result "runtimes" "python" "pass" "false" "$actual_python" "Version mismatch"
                else
                    print_check_result "fail" "Python" "NOT WORKING"
                    add_result "runtimes" "python" "fail" "true" "" "Not working"
                fi
            else
                print_check_result "fail" "Python" "NOT INSTALLED"
                add_result "runtimes" "python" "fail" "true" "" "Not installed"
            fi

            # Node.js
            local required_node
            required_node=$(grep "^nodejs " "$tool_versions_file" 2>/dev/null | awk '{print $2}')
            if command -v node &>/dev/null; then
                local actual_node
                actual_node=$(get_cmd_version "node")
                if [[ -n "$required_node" ]] && [[ "$actual_node" == "$required_node"* ]]; then
                    print_check_result "pass" "Node.js" "$actual_node"
                    add_result "runtimes" "nodejs" "pass" "true" "$actual_node" ""
                elif [[ -n "$actual_node" ]]; then
                    print_check_result "warn" "Node.js" "$actual_node (expected: $required_node)"
                    add_result "runtimes" "nodejs" "pass" "false" "$actual_node" "Version mismatch"
                else
                    print_check_result "fail" "Node.js" "NOT WORKING"
                    add_result "runtimes" "nodejs" "fail" "true" "" "Not working"
                fi
            else
                print_check_result "fail" "Node.js" "NOT INSTALLED"
                add_result "runtimes" "nodejs" "fail" "true" "" "Not installed"
            fi
        else
            print_check_result "warn" ".tool-versions" "NOT FOUND"
            add_result "runtimes" "tool_versions" "fail" "false" "" "File not found"
        fi
    else
        print_check_result "fail" "mise" "NOT INSTALLED"
        add_result "runtimes" "mise" "fail" "true" "" "Not installed"

        # Fallback: проверить системные версии
        if command -v go &>/dev/null; then
            local go_ver
            go_ver=$(get_cmd_version "go")
            print_check_result "warn" "Go (system)" "$go_ver"
            add_result "runtimes" "go" "pass" "false" "$go_ver" "System version"
        fi

        if command -v python3 &>/dev/null; then
            local py_ver
            py_ver=$(get_cmd_version "python3")
            print_check_result "warn" "Python (system)" "$py_ver"
            add_result "runtimes" "python" "pass" "false" "$py_ver" "System version"
        fi

        if command -v node &>/dev/null; then
            local node_ver
            node_ver=$(get_cmd_version "node")
            print_check_result "warn" "Node.js (system)" "$node_ver"
            add_result "runtimes" "nodejs" "pass" "false" "$node_ver" "System version"
        fi
    fi
}

# Проверка мониторинга
check_monitoring() {
    print_section "Monitoring"

    # Prometheus
    if command -v prometheus &>/dev/null; then
        local prom_version
        prom_version=$(get_cmd_version "prometheus")

        if check_systemd_service "prometheus" 2>/dev/null; then
            if check_health_endpoint "http://localhost:9090/-/healthy" 2 2>/dev/null; then
                print_check_result "pass" "Prometheus" "http://localhost:9090"
                add_result "monitoring" "prometheus" "pass" "false" "$prom_version" "http://localhost:9090"
            else
                print_check_result "warn" "Prometheus" "running but not responding"
                add_result "monitoring" "prometheus" "fail" "false" "$prom_version" "Not responding"
            fi
        else
            print_check_result "warn" "Prometheus ($prom_version)" "NOT RUNNING"
            add_result "monitoring" "prometheus" "fail" "false" "$prom_version" "Not running"

            if [[ "$FIX_MODE" == "true" ]]; then
                log_info "Attempting to start Prometheus..."
                if start_systemd_service "prometheus" 2>/dev/null; then
                    print_check_result "pass" "Prometheus" "STARTED"
                fi
            fi
        fi
    else
        print_check_result "warn" "Prometheus" "NOT INSTALLED"
        add_result "monitoring" "prometheus" "fail" "false" "" "Not installed"
    fi

    # Grafana
    if command -v grafana-server &>/dev/null || command -v grafana &>/dev/null; then
        local grafana_version
        grafana_version=$(get_cmd_version "grafana-server")

        if check_systemd_service "grafana" 2>/dev/null; then
            if check_health_endpoint "http://localhost:3000/api/health" 2 2>/dev/null; then
                print_check_result "pass" "Grafana" "http://localhost:3000"
                add_result "monitoring" "grafana" "pass" "false" "$grafana_version" "http://localhost:3000"
            else
                print_check_result "warn" "Grafana" "running but not responding"
                add_result "monitoring" "grafana" "fail" "false" "$grafana_version" "Not responding"
            fi
        else
            print_check_result "warn" "Grafana ($grafana_version)" "NOT RUNNING"
            add_result "monitoring" "grafana" "fail" "false" "$grafana_version" "Not running"

            if [[ "$FIX_MODE" == "true" ]]; then
                log_info "Attempting to start Grafana..."
                if start_systemd_service "grafana" 2>/dev/null; then
                    print_check_result "pass" "Grafana" "STARTED"
                fi
            fi
        fi
    else
        print_check_result "warn" "Grafana" "NOT INSTALLED"
        add_result "monitoring" "grafana" "fail" "false" "" "Not installed"
    fi

    # postgres_exporter
    if check_port_listening 9187 2>/dev/null; then
        print_check_result "pass" "postgres_exporter" "http://localhost:9187"
        add_result "monitoring" "postgres_exporter" "pass" "false" "" "http://localhost:9187"
    else
        print_check_result "warn" "postgres_exporter" "NOT RUNNING"
        add_result "monitoring" "postgres_exporter" "fail" "false" "" "Not running"
    fi

    # redis_exporter
    if check_port_listening 9121 2>/dev/null; then
        print_check_result "pass" "redis_exporter" "http://localhost:9121"
        add_result "monitoring" "redis_exporter" "pass" "false" "" "http://localhost:9121"
    else
        print_check_result "warn" "redis_exporter" "NOT RUNNING"
        add_result "monitoring" "redis_exporter" "fail" "false" "" "Not running"
    fi
}

##############################################################################
# OUTPUT RESULTS
##############################################################################

print_summary() {
    if [[ "$JSON_OUTPUT" == "true" ]]; then
        return
    fi

    echo ""
    echo -e "${BOLD}Summary:${NC} ${PASSED_CHECKS}/${TOTAL_CHECKS} checks passed"

    if [[ $CRITICAL_FAILURES -gt 0 ]]; then
        echo -e "${RED}Critical failures: ${CRITICAL_FAILURES}${NC}"
    fi

    if [[ $NONCRITICAL_FAILURES -gt 0 ]]; then
        echo -e "${YELLOW}Non-critical failures: ${NONCRITICAL_FAILURES}${NC}"
    fi

    if [[ $CRITICAL_FAILURES -eq 0 ]] && [[ $NONCRITICAL_FAILURES -eq 0 ]]; then
        echo -e "${GREEN}All checks passed!${NC}"
    fi
}

output_json() {
    if [[ "$JSON_OUTPUT" != "true" ]]; then
        return
    fi

    local results_json
    results_json=$(printf '%s\n' "${JSON_RESULTS[@]}" | paste -sd ',' -)

    cat << JSONEOF
{
  "version": "${SCRIPT_VERSION}",
  "timestamp": "$(date -Iseconds)",
  "summary": {
    "total": ${TOTAL_CHECKS},
    "passed": ${PASSED_CHECKS},
    "critical_failures": ${CRITICAL_FAILURES},
    "noncritical_failures": ${NONCRITICAL_FAILURES}
  },
  "results": [${results_json}]
}
JSONEOF
}

##############################################################################
# MAIN
##############################################################################

main() {
    parse_args "$@"

    # Header
    if [[ "$JSON_OUTPUT" != "true" ]]; then
        echo ""
        echo -e "${BOLD}=== CommandCenter1C - Verification ===${NC}"
    fi

    # Run checks
    check_system_packages
    check_infrastructure
    check_runtimes

    if [[ "$QUICK_MODE" != "true" ]]; then
        check_monitoring
    fi

    # Output
    if [[ "$JSON_OUTPUT" == "true" ]]; then
        output_json
    else
        print_summary
    fi

    # Exit code
    if [[ $CRITICAL_FAILURES -gt 0 ]]; then
        exit 1
    elif [[ $NONCRITICAL_FAILURES -gt 0 ]]; then
        exit 2
    else
        exit 0
    fi
}

main "$@"
