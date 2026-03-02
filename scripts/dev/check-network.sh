#!/bin/bash
#
# check-network.sh - Диагностика сетевой связности WSL2 / Windows / Docker
#
# Использование:
#   ./scripts/dev/check-network.sh           # Полная диагностика
#   ./scripts/dev/check-network.sh --quick   # Быстрая проверка (только connectivity)
#

set -euo pipefail

# Цвета для вывода
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color
BOLD='\033[1m'

# Иконки
ICON_OK="✓"
ICON_FAIL="✗"
ICON_WARN="!"
ICON_INFO="→"

# Счётчики
PASSED=0
FAILED=0
WARNINGS=0

#######################################
# Вывод с форматированием
#######################################
print_header() {
    echo -e "\n${BOLD}${BLUE}═══════════════════════════════════════════════════════════════${NC}"
    echo -e "${BOLD}${BLUE}  $1${NC}"
    echo -e "${BOLD}${BLUE}═══════════════════════════════════════════════════════════════${NC}"
}

print_section() {
    echo -e "\n${CYAN}[$1]${NC}"
}

print_ok() {
    echo -e "  ${GREEN}${ICON_OK}${NC} $1"
    ((PASSED++)) || true
}

print_fail() {
    echo -e "  ${RED}${ICON_FAIL}${NC} $1"
    ((FAILED++)) || true
}

print_warn() {
    echo -e "  ${YELLOW}${ICON_WARN}${NC} $1"
    ((WARNINGS++)) || true
}

print_info() {
    echo -e "  ${ICON_INFO} $1"
}

#######################################
# Проверка TCP порта
#######################################
check_port() {
    local host=$1
    local port=$2
    local timeout_sec=${3:-2}

    # Используем nc (netcat) если доступен, иначе /dev/tcp
    if command -v nc &>/dev/null; then
        nc -z -w "$timeout_sec" "$host" "$port" 2>/dev/null
        return $?
    elif command -v timeout &>/dev/null; then
        timeout "$timeout_sec" bash -c "echo >/dev/tcp/$host/$port" 2>/dev/null
        return $?
    else
        # Fallback без timeout
        (echo >/dev/tcp/"$host"/"$port") 2>/dev/null
        return $?
    fi
}

#######################################
# Проверка HTTP endpoint
#######################################
check_http() {
    local url=$1
    local timeout=${2:-5}

    if curl -sf --max-time "$timeout" "$url" >/dev/null 2>&1; then
        return 0
    else
        return 1
    fi
}

#######################################
# 1. Информация о системе
#######################################
check_system_info() {
    print_section "1. Системная информация"

    # WSL версия
    if [[ -f /proc/version ]]; then
        if grep -qi "microsoft" /proc/version; then
            local wsl_version=$(uname -r | grep -oP 'WSL\d?' || echo "WSL2")
            print_info "Окружение: ${BOLD}$wsl_version${NC} ($(uname -r))"
        else
            print_info "Окружение: Native Linux ($(uname -r))"
        fi
    fi

    # WSL2 IP (используем ip addr вместо hostname -I для совместимости)
    local wsl_ip=$(ip -4 addr show eth0 2>/dev/null | grep -oP '(?<=inet\s)\d+(\.\d+){3}' | head -1)
    if [[ -z "$wsl_ip" ]]; then
        wsl_ip=$(ip -4 addr 2>/dev/null | grep -oP '(?<=inet\s)\d+(\.\d+){3}' | grep -v '127.0.0.1' | head -1)
    fi
    print_info "WSL2 IP: ${BOLD}${wsl_ip:-N/A}${NC}"

    # Windows Host IP (из resolv.conf)
    local windows_host=""
    if [[ -f /etc/resolv.conf ]]; then
        windows_host=$(grep nameserver /etc/resolv.conf 2>/dev/null | head -1 | awk '{print $2}')
        print_info "Windows Host IP (resolv.conf): ${BOLD}${windows_host:-N/A}${NC}"
    fi

    # Hostname (совместимость с минималистичными дистрибутивами)
    local hostname_val=""
    if command -v hostname &>/dev/null; then
        hostname_val=$(hostname)
    elif [[ -f /etc/hostname ]]; then
        hostname_val=$(cat /etc/hostname)
    else
        hostname_val=$(cat /proc/sys/kernel/hostname 2>/dev/null || echo "N/A")
    fi
    print_info "Hostname: $hostname_val"
}

#######################################
# 2. Проверка режима сети WSL2
#######################################
check_wsl_network_mode() {
    print_section "2. Режим сети WSL2"

    local wslconfig="/mnt/c/Users/$USER/.wslconfig"
    local network_mode="NAT (default)"

    if [[ -f "$wslconfig" ]]; then
        if grep -qi "networkingMode.*=.*mirrored" "$wslconfig" 2>/dev/null; then
            network_mode="mirrored"
            print_ok "Режим: ${BOLD}mirrored${NC} (рекомендуется)"
            print_info "localhost в WSL = localhost в Windows"
        else
            print_warn "Режим: ${BOLD}NAT${NC} (legacy)"
            print_info "Для доступа к Windows используйте IP из resolv.conf"
        fi

        # Проверка дополнительных настроек
        if grep -qi "dnsTunneling.*=.*true" "$wslconfig" 2>/dev/null; then
            print_ok "DNS Tunneling: включен"
        fi

        if grep -qi "firewall.*=.*true" "$wslconfig" 2>/dev/null; then
            print_ok "Firewall integration: включен"
        fi
    else
        print_warn ".wslconfig не найден: $wslconfig"
        print_info "Используется режим NAT по умолчанию"
        print_info "Рекомендация: создайте .wslconfig с networkingMode=mirrored"
    fi
}

#######################################
# 3. Проверка связности с Windows Host
#######################################
check_windows_connectivity() {
    print_section "3. Связность с Windows Host"

    local windows_host=$(grep nameserver /etc/resolv.conf 2>/dev/null | head -1 | awk '{print $2}')

    # Проверка через resolv.conf IP
    if [[ -n "$windows_host" ]]; then
        if ping -c 1 -W 2 "$windows_host" >/dev/null 2>&1; then
            print_ok "Ping $windows_host: доступен"
        else
            print_fail "Ping $windows_host: недоступен"
        fi
    fi

    # Проверка localhost (для mirrored mode)
    if check_port "localhost" "135" 2; then
        print_ok "localhost:135 (Windows RPC): доступен (mirrored mode работает)"
    else
        print_info "localhost:135: недоступен (NAT mode или firewall)"
    fi
}

#######################################
# 4. Проверка RAS сервера
#######################################
check_ras_connectivity() {
    print_section "4. RAS сервер (1С)"

    # Загружаем .env.local если есть
    local env_file="${PROJECT_ROOT:-.}/.env.local"
    if [[ -f "$env_file" ]]; then
        # shellcheck disable=SC1090
        source <(grep -E '^(RAS_SERVER|RAS_SERVER_ADDR|RAS_PORT)=' "$env_file" 2>/dev/null) || true
    fi

    # Парсим RAS_SERVER или RAS_SERVER_ADDR (формат: host:port)
    local ras_host=""
    local ras_port="${RAS_PORT:-1645}"

    if [[ -n "${RAS_SERVER:-}" ]]; then
        ras_host=$(echo "$RAS_SERVER" | cut -d':' -f1)
        ras_port=$(echo "$RAS_SERVER" | cut -d':' -f2)
    elif [[ -n "${RAS_SERVER_ADDR:-}" ]]; then
        ras_host=$(echo "$RAS_SERVER_ADDR" | cut -d':' -f1)
        ras_port=$(echo "$RAS_SERVER_ADDR" | cut -d':' -f2)
    fi

    local windows_host=$(grep nameserver /etc/resolv.conf 2>/dev/null | head -1 | awk '{print $2}')

    # Определяем хост для проверки
    if [[ -z "$ras_host" ]]; then
        print_info "RAS_SERVER не задан в .env.local, проверяем варианты..."
    else
        print_info "RAS_SERVER=$ras_host:$ras_port (из .env.local)"
    fi

    # Проверка localhost (mirrored mode)
    echo -e "\n  ${CYAN}Проверка localhost:$ras_port:${NC}"
    if check_port "localhost" "$ras_port" 3; then
        print_ok "localhost:$ras_port - ДОСТУПЕН"
    else
        print_fail "localhost:$ras_port - недоступен"
    fi

    # Проверка Windows Host IP (NAT mode)
    if [[ -n "$windows_host" ]]; then
        echo -e "\n  ${CYAN}Проверка $windows_host:$ras_port:${NC}"
        if check_port "$windows_host" "$ras_port" 3; then
            print_ok "$windows_host:$ras_port - ДОСТУПЕН"
        else
            print_fail "$windows_host:$ras_port - недоступен"
            print_info "Возможные причины:"
            print_info "  - RAS сервер не запущен на Windows"
            print_info "  - Windows Firewall блокирует порт $ras_port"
            print_info "  - RAS слушает только 127.0.0.1"
        fi
    fi

    # Проверка заданного хоста
    if [[ -n "$ras_host" && "$ras_host" != "localhost" && "$ras_host" != "$windows_host" ]]; then
        echo -e "\n  ${CYAN}Проверка $ras_host:$ras_port (из конфига):${NC}"
        if check_port "$ras_host" "$ras_port" 3; then
            print_ok "$ras_host:$ras_port - ДОСТУПЕН"
        else
            print_fail "$ras_host:$ras_port - недоступен"
        fi
    fi
}

#######################################
# 5. Проверка локальных сервисов
#######################################
check_local_services() {
    print_section "5. Локальные сервисы проекта"

    declare -A services=(
        ["API Gateway"]="localhost:8180/health"
        ["Orchestrator"]="localhost:8200/api/health/"
        ["RAS Adapter"]="localhost:8188/health"
        ["Batch Service"]="localhost:8187/health"
        ["Frontend"]="localhost:15173"
    )

    for name in "${!services[@]}"; do
        local endpoint="${services[$name]}"
        local host_port=$(echo "$endpoint" | cut -d'/' -f1)
        local host=$(echo "$host_port" | cut -d':' -f1)
        local port=$(echo "$host_port" | cut -d':' -f2)

        if check_port "$host" "$port" 2; then
            if check_http "http://$endpoint" 3; then
                print_ok "$name (http://$endpoint): работает"
            else
                print_warn "$name: порт открыт, но HTTP не отвечает"
            fi
        else
            print_info "$name ($host_port): не запущен"
        fi
    done
}

#######################################
# 6. Проверка Docker
#######################################
check_docker() {
    print_section "6. Docker Desktop"

    if command -v docker &>/dev/null; then
        if docker info >/dev/null 2>&1; then
            print_ok "Docker daemon: работает"

            # Docker networks
            local networks=$(docker network ls --format '{{.Name}}' 2>/dev/null | head -5 | tr '\n' ', ' | sed 's/,$//')
            print_info "Сети: $networks"

            # host.docker.internal
            if getent hosts host.docker.internal >/dev/null 2>&1; then
                local docker_host_ip=$(getent hosts host.docker.internal | awk '{print $1}')
                print_ok "host.docker.internal: $docker_host_ip"
            else
                print_info "host.docker.internal: не резолвится (ожидаемо вне контейнера)"
            fi
        else
            print_warn "Docker установлен, но daemon не отвечает"
        fi
    else
        print_info "Docker CLI не установлен"
    fi
}

#######################################
# 7. Проверка инфраструктурных сервисов
#######################################
check_infrastructure() {
    print_section "7. Инфраструктурные сервисы"

    # PostgreSQL
    if check_port "localhost" "5432" 2; then
        print_ok "PostgreSQL (localhost:5432): доступен"
    else
        print_fail "PostgreSQL (localhost:5432): недоступен"
    fi

    # Redis
    if check_port "localhost" "6379" 2; then
        if command -v redis-cli &>/dev/null; then
            if redis-cli ping >/dev/null 2>&1; then
                print_ok "Redis (localhost:6379): работает"
            else
                print_warn "Redis: порт открыт, но не отвечает на PING"
            fi
        else
            print_ok "Redis (localhost:6379): порт открыт"
        fi
    else
        print_fail "Redis (localhost:6379): недоступен"
    fi

    # Prometheus
    if check_port "localhost" "9090" 2; then
        print_ok "Prometheus (localhost:9090): доступен"
    else
        print_info "Prometheus (localhost:9090): не запущен"
    fi

    # Grafana (порт зависит от режима)
    if check_port "localhost" "3000" 2; then
        print_ok "Grafana (localhost:3000): доступен (native mode)"
    elif check_port "localhost" "5000" 2; then
        print_ok "Grafana (localhost:5000): доступен (docker mode)"
    else
        print_info "Grafana: не запущен"
    fi
}

#######################################
# 8. Рекомендации
#######################################
print_recommendations() {
    print_section "8. Рекомендации"

    # Загружаем .env.local если есть
    local env_file="${PROJECT_ROOT:-.}/.env.local"
    if [[ -f "$env_file" ]]; then
        # shellcheck disable=SC1090
        source <(grep -E '^(RAS_SERVER|RAS_SERVER_ADDR|RAS_PORT)=' "$env_file" 2>/dev/null) || true
    fi

    local windows_host=$(grep nameserver /etc/resolv.conf 2>/dev/null | head -1 | awk '{print $2}')
    local wslconfig="/mnt/c/Users/$USER/.wslconfig"
    local default_ras_port="${RAS_PORT:-1645}"
    local configured_ras_host=""

    if [[ -n "${RAS_SERVER:-}" ]]; then
        configured_ras_host=$(echo "$RAS_SERVER" | cut -d':' -f1)
        default_ras_port=$(echo "$RAS_SERVER" | cut -d':' -f2)
    elif [[ -n "${RAS_SERVER_ADDR:-}" ]]; then
        configured_ras_host=$(echo "$RAS_SERVER_ADDR" | cut -d':' -f1)
        default_ras_port=$(echo "$RAS_SERVER_ADDR" | cut -d':' -f2)
    fi

    # Проверяем режим сети
    local is_mirrored=false
    if [[ -f "$wslconfig" ]] && grep -qi "networkingMode.*=.*mirrored" "$wslconfig" 2>/dev/null; then
        is_mirrored=true
    fi

    # Проверяем доступность RAS
    local ras_via_localhost=false
    local ras_via_windows=false
    local ras_via_config=false

    if check_port "localhost" "$default_ras_port" 2; then
        ras_via_localhost=true
    fi

    if [[ -n "$windows_host" ]] && check_port "$windows_host" "$default_ras_port" 2; then
        ras_via_windows=true
    fi

    if [[ -n "$configured_ras_host" ]] && check_port "$configured_ras_host" "$default_ras_port" 2; then
        ras_via_config=true
    fi

    echo ""

    if $ras_via_config; then
        echo -e "  ${GREEN}RAS доступен по адресу из .env.local${NC}"
        echo -e "  Рекомендуемая конфигурация .env.local:"
        echo -e "    ${BOLD}RAS_SERVER=$configured_ras_host:${default_ras_port}${NC}"
    elif $ras_via_localhost; then
        echo -e "  ${GREEN}RAS доступен через localhost${NC}"
        echo -e "  Рекомендуемая конфигурация .env.local:"
        echo -e "    ${BOLD}RAS_SERVER=localhost:${default_ras_port}${NC}"
    elif $ras_via_windows; then
        echo -e "  ${YELLOW}RAS доступен только через Windows IP${NC}"
        echo -e "  Рекомендуемая конфигурация .env.local:"
        echo -e "    ${BOLD}RAS_SERVER=$windows_host:${default_ras_port}${NC}"
        echo ""
        if ! $is_mirrored; then
            echo -e "  ${YELLOW}Рекомендация:${NC} включите mirrored mode в .wslconfig:"
            echo -e "    [wsl2]"
            echo -e "    networkingMode=mirrored"
        fi
    else
        echo -e "  ${RED}RAS сервер недоступен!${NC}"
        echo ""
        echo -e "  Проверьте:"
        echo -e "  1. Запущен ли RAS сервер в WSL (порт ${default_ras_port})"
        echo -e "  2. RAS слушает на localhost/0.0.0.0:"
        echo -e "     ${CYAN}ss -ltnp | grep :${default_ras_port}${NC}"
        echo -e "  3. Если RAS работает на Windows-host, разрешите входящие на порт ${default_ras_port}:"
        echo -e "     ${CYAN}New-NetFirewallRule -DisplayName \"1C RAS\" -Direction Inbound -Protocol TCP -LocalPort ${default_ras_port} -Action Allow${NC}"

        if ! $is_mirrored; then
            echo ""
            echo -e "  4. Включите mirrored mode в C:\\Users\\$USER\\.wslconfig:"
            echo -e "     [wsl2]"
            echo -e "     networkingMode=mirrored"
            echo -e "     Затем: ${CYAN}wsl --shutdown${NC} и перезапустите WSL"
        fi

        echo ""
        echo -e "  ${CYAN}Или используйте PowerShell скрипт на Windows:${NC}"
        echo -e "     ${BOLD}powershell -ExecutionPolicy Bypass -File scripts\\windows\\setup-wsl-network.ps1 -Diagnose${NC}"
        echo -e "     ${BOLD}powershell -ExecutionPolicy Bypass -File scripts\\windows\\setup-wsl-network.ps1 -Setup${NC}"
    fi
}

#######################################
# Итоговая статистика
#######################################
print_summary() {
    print_header "Итоги диагностики"

    echo -e "  ${GREEN}Успешно:${NC} $PASSED"
    echo -e "  ${RED}Ошибок:${NC}  $FAILED"
    echo -e "  ${YELLOW}Предупр.:${NC} $WARNINGS"
    echo ""

    if [[ $FAILED -eq 0 ]]; then
        echo -e "  ${GREEN}${BOLD}Сетевая конфигурация в порядке!${NC}"
    else
        echo -e "  ${RED}${BOLD}Обнаружены проблемы. См. рекомендации выше.${NC}"
    fi
}

#######################################
# Main
#######################################
main() {
    local quick_mode=false

    # Парсинг аргументов
    while [[ $# -gt 0 ]]; do
        case $1 in
            --quick|-q)
                quick_mode=true
                shift
                ;;
            --help|-h)
                echo "Использование: $0 [--quick]"
                echo ""
                echo "Опции:"
                echo "  --quick, -q    Быстрая проверка (только connectivity)"
                echo "  --help, -h     Показать справку"
                exit 0
                ;;
            *)
                echo "Неизвестный аргумент: $1"
                exit 1
                ;;
        esac
    done

    print_header "Диагностика сетевой связности WSL2"
    echo -e "  Дата: $(date '+%Y-%m-%d %H:%M:%S')"
    echo -e "  Проект: CommandCenter1C"

    if $quick_mode; then
        check_ras_connectivity
        check_local_services
    else
        check_system_info
        check_wsl_network_mode
        check_windows_connectivity
        check_ras_connectivity
        check_local_services
        check_docker
        check_infrastructure
        print_recommendations
    fi

    print_summary

    # Exit code
    if [[ $FAILED -gt 0 ]]; then
        exit 1
    fi
}

main "$@"
