#!/bin/bash

##############################################################################
# CommandCenter1C - Monitoring Stack Installation
##############################################################################
#
# Установка стека мониторинга: Prometheus, Grafana, exporters.
# Использует кросс-платформенную библиотеку packages.sh.
#
# Компоненты:
#   - Prometheus (9090)     - сбор и хранение метрик
#   - Grafana (3000)        - визуализация
#   - node_exporter (9100)  - системные метрики
#   - blackbox_exporter (9115) - TCP/HTTP probes (RAS port monitoring)
#   - postgres_exporter (9187) - метрики PostgreSQL (AUR)
#   - redis_exporter (9121) - метрики Redis (AUR)
#
# Usage:
#   ./scripts/setup/install-monitoring.sh [OPTIONS]
#
# Options:
#   --only-prometheus       Установить только Prometheus
#   --only-grafana          Установить только Grafana
#   --only-exporters        Установить только exporters
#   --skip-prometheus       Пропустить Prometheus
#   --skip-grafana          Пропустить Grafana
#   --skip-exporters        Пропустить exporters
#   --skip-config           Не копировать конфигурационные файлы
#   --dry-run               Показать план без установки
#   -v, --verbose           Подробный вывод
#   -h, --help              Показать справку
#
# Examples:
#   ./scripts/setup/install-monitoring.sh                # Полная установка
#   ./scripts/setup/install-monitoring.sh --dry-run      # Показать план
#   ./scripts/setup/install-monitoring.sh --only-exporters
#   ./scripts/setup/install-monitoring.sh --skip-exporters
#
# Version: 1.0.0
##############################################################################

set -e

# Версия скрипта
SCRIPT_VERSION="1.0.0"

# Директории
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

# Пути к конфигурациям
PROMETHEUS_CONFIG_SRC="$PROJECT_ROOT/infrastructure/monitoring/prometheus/prometheus-native.yml"
SYSTEMD_DIR="$PROJECT_ROOT/infrastructure/systemd"

# Системные пути
PROMETHEUS_CONFIG_DEST="/etc/prometheus/prometheus.yml"
SYSTEMD_SYSTEM_DIR="/etc/systemd/system"

# Подключение библиотеки
if [[ -f "$PROJECT_ROOT/scripts/lib/init.sh" ]]; then
    source "$PROJECT_ROOT/scripts/lib/init.sh"
else
    echo "FATAL: scripts/lib/init.sh не найден в $PROJECT_ROOT" >&2
    exit 1
fi

##############################################################################
# PACKAGE DEFINITIONS
##############################################################################

# Основные пакеты (canonical names из packages.sh)
PROMETHEUS_PACKAGES=(
    "prometheus"
)

GRAFANA_PACKAGES=(
    "grafana"
)

# Exporters - node_exporter из pacman, остальные из AUR
EXPORTER_PACKAGES=(
    "node_exporter"
    "blackbox_exporter"
)

# AUR пакеты для Arch Linux
AUR_EXPORTER_PACKAGES=(
    "prometheus-postgres-exporter"
    "prometheus-redis-exporter"
)

# Systemd unit files для exporters
EXPORTER_SERVICES=(
    "postgres-exporter.service"
    "redis-exporter.service"
    "blackbox-exporter.service"
)

##############################################################################
# CLI ARGUMENTS
##############################################################################

DRY_RUN=false
VERBOSE=false
SKIP_CONFIG=false

# Флаги установки компонентов
INSTALL_PROMETHEUS=true
INSTALL_GRAFANA=true
INSTALL_EXPORTERS=true

parse_args() {
    while [[ $# -gt 0 ]]; do
        case $1 in
            --only-prometheus)
                INSTALL_PROMETHEUS=true
                INSTALL_GRAFANA=false
                INSTALL_EXPORTERS=false
                shift
                ;;
            --only-grafana)
                INSTALL_PROMETHEUS=false
                INSTALL_GRAFANA=true
                INSTALL_EXPORTERS=false
                shift
                ;;
            --only-exporters)
                INSTALL_PROMETHEUS=false
                INSTALL_GRAFANA=false
                INSTALL_EXPORTERS=true
                shift
                ;;
            --skip-prometheus)
                INSTALL_PROMETHEUS=false
                shift
                ;;
            --skip-grafana)
                INSTALL_GRAFANA=false
                shift
                ;;
            --skip-exporters)
                INSTALL_EXPORTERS=false
                shift
                ;;
            --skip-config)
                SKIP_CONFIG=true
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
CommandCenter1C - Monitoring Stack Installation

Usage:
  ./scripts/setup/install-monitoring.sh [OPTIONS]

Options:
  --only-prometheus       Установить только Prometheus
  --only-grafana          Установить только Grafana
  --only-exporters        Установить только exporters
  --skip-prometheus       Пропустить Prometheus
  --skip-grafana          Пропустить Grafana
  --skip-exporters        Пропустить exporters
  --skip-config           Не копировать конфигурационные файлы
  --dry-run               Показать план без установки
  -v, --verbose           Подробный вывод
  -h, --help              Показать эту справку

Компоненты:
  Prometheus (9090)       Сбор и хранение метрик
  Grafana (3000)          Визуализация метрик
  node_exporter (9100)    Системные метрики (CPU, RAM, disk, network)
  blackbox_exporter (9115) TCP/HTTP probes (e.g., RAS port monitoring)
  postgres_exporter (9187) Метрики PostgreSQL (connections, queries, etc.)
  redis_exporter (9121)   Метрики Redis (memory, clients, commands)

Конфигурация:
  Prometheus config       infrastructure/monitoring/prometheus/prometheus-native.yml
  Systemd services        infrastructure/systemd/*.service

Examples:
  ./scripts/setup/install-monitoring.sh                # Полная установка
  ./scripts/setup/install-monitoring.sh --dry-run      # Показать план
  ./scripts/setup/install-monitoring.sh --only-exporters
  ./scripts/setup/install-monitoring.sh --skip-exporters

Notes:
  - blackbox targets for RAS are generated from .env.local via:
      ./scripts/dev/generate-blackbox-targets.sh
    and then copied to:
      /etc/prometheus/targets/blackbox_tcp.yml
      /etc/prometheus/targets/blackbox_http.yml
EOF
}

##############################################################################
# HELPER FUNCTIONS
##############################################################################

# Проверка наличия sudo
check_sudo() {
    if ! check_sudo_available; then
        log_error "Для установки системных сервисов требуется sudo"
        return 1
    fi
    return 0
}

# Бэкап существующего файла
backup_file() {
    local file=$1
    if [[ -f "$file" ]]; then
        local backup="${file}.backup.$(date +%Y%m%d_%H%M%S)"
        $DRY_RUN && log_info "[DRY-RUN] Backup: $file -> $backup" && return 0
        sudo cp "$file" "$backup"
        log_verbose "Создан backup: $backup"
    fi
}

# Проверка установлен ли пакет (с учетом AUR имен)
is_pkg_installed() {
    local pkg=$1
    # Проверяем через pacman напрямую для точного имени
    if pacman -Qi "$pkg" &>/dev/null; then
        return 0
    fi
    return 1
}

# Получить версию пакета
get_pkg_version() {
    local pkg=$1
    pacman -Qi "$pkg" 2>/dev/null | grep "^Version" | awk '{print $3}'
}

##############################################################################
# INSTALLATION FUNCTIONS
##############################################################################

# Установка Prometheus
install_prometheus() {
    log_step "Установка Prometheus..."

    local need_install=false

    # Проверка уже установленных
    local mapped_name
    mapped_name=$(pkg_map_name "prometheus")

    if pkg_is_installed "$mapped_name"; then
        local version
        version=$(pkg_version "$mapped_name")
        log_success "Prometheus уже установлен: $version"
    else
        need_install=true
    fi

    if $need_install; then
        if $DRY_RUN; then
            log_info "[DRY-RUN] Будет установлен: prometheus"
        else
            log_info "Установка prometheus..."
            pkg_install "prometheus"
        fi
    fi

    # Конфигурация Prometheus
    if ! $SKIP_CONFIG; then
        configure_prometheus
    fi
}

# Конфигурация Prometheus
configure_prometheus() {
    log_step "Настройка конфигурации Prometheus..."

    # Проверка наличия исходного конфига
    if [[ ! -f "$PROMETHEUS_CONFIG_SRC" ]]; then
        log_warning "Конфигурация не найдена: $PROMETHEUS_CONFIG_SRC"
        log_info "Будет использован конфиг по умолчанию"
        return 0
    fi

    if $DRY_RUN; then
        log_info "[DRY-RUN] Конфигурация:"
        log_info "  Источник: $PROMETHEUS_CONFIG_SRC"
        log_info "  Назначение: $PROMETHEUS_CONFIG_DEST"
        return 0
    fi

    # Создание директории если нужно
    if [[ ! -d "/etc/prometheus" ]]; then
        sudo mkdir -p /etc/prometheus
        log_verbose "Создана директория /etc/prometheus"
    fi

    # Бэкап существующего конфига
    backup_file "$PROMETHEUS_CONFIG_DEST"

    # Копирование конфига
    sudo cp "$PROMETHEUS_CONFIG_SRC" "$PROMETHEUS_CONFIG_DEST"
    log_success "Конфигурация Prometheus скопирована"

    # Включение targets для exporters в конфиге
    enable_prometheus_targets
}

# Включение targets в prometheus.yml (раскомментирование)
enable_prometheus_targets() {
    log_verbose "Включение targets в prometheus.yml..."

    if $DRY_RUN; then
        log_info "[DRY-RUN] Будут раскомментированы targets: postgres, redis, node"
        return 0
    fi

    # Раскомментировать секции для exporters
    # node_exporter
    sudo sed -i '/job_name.*node/,/targets.*9100/ s/^  # /  /' "$PROMETHEUS_CONFIG_DEST" 2>/dev/null || true

    # postgres_exporter
    sudo sed -i '/job_name.*postgres/,/targets.*9187/ s/^  # /  /' "$PROMETHEUS_CONFIG_DEST" 2>/dev/null || true

    # redis_exporter
    sudo sed -i '/job_name.*redis/,/targets.*9121/ s/^  # /  /' "$PROMETHEUS_CONFIG_DEST" 2>/dev/null || true

    log_verbose "Targets включены в конфигурации"
}

# Установка Grafana
install_grafana() {
    log_step "Установка Grafana..."

    local mapped_name
    mapped_name=$(pkg_map_name "grafana")

    if pkg_is_installed "$mapped_name"; then
        local version
        version=$(pkg_version "$mapped_name")
        log_success "Grafana уже установлена: $version"
    else
        if $DRY_RUN; then
            log_info "[DRY-RUN] Будет установлена: grafana"
        else
            log_info "Установка grafana..."
            pkg_install "grafana"
        fi
    fi
}

# Установка exporters
install_exporters() {
    log_step "Установка Prometheus exporters..."

    # node_exporter (из основных репозиториев)
    install_node_exporter

    # blackbox_exporter (из основных репозиториев)
    install_blackbox_exporter

    # AUR exporters (postgres, redis)
    if is_arch; then
        install_aur_exporters
    else
        log_warning "AUR пакеты доступны только на Arch Linux"
        log_info "Для других дистрибутивов установите вручную:"
        log_info "  postgres_exporter: https://github.com/prometheus-community/postgres_exporter"
        log_info "  redis_exporter: https://github.com/oliver006/redis_exporter"
    fi

    # Установка systemd unit files
    if ! $SKIP_CONFIG; then
        configure_blackbox_exporter
        install_exporter_services
    fi
}

# Установка node_exporter
install_node_exporter() {
    log_verbose "Проверка node_exporter..."

    local mapped_name
    mapped_name=$(pkg_map_name "node_exporter")

    if pkg_is_installed "$mapped_name"; then
        local version
        version=$(pkg_version "$mapped_name")
        log_success "node_exporter уже установлен: $version"
    else
        if $DRY_RUN; then
            log_info "[DRY-RUN] Будет установлен: $mapped_name"
        else
            log_info "Установка node_exporter..."
            pkg_install "node_exporter"
        fi
    fi
}

install_blackbox_exporter() {
    log_verbose "Проверка blackbox_exporter..."

    local mapped_name
    mapped_name=$(pkg_map_name "blackbox_exporter")

    if pkg_is_installed "$mapped_name"; then
        local version
        version=$(pkg_version "$mapped_name")
        log_success "blackbox_exporter уже установлен: $version"
        return 0
    fi

    if $DRY_RUN; then
        log_info "[DRY-RUN] Будет установлен: $mapped_name"
        return 0
    fi

    log_info "Установка blackbox_exporter..."
    pkg_install "blackbox_exporter"
}

configure_blackbox_exporter() {
    log_step "Настройка blackbox_exporter (config + targets)..."

    local blackbox_config_src="$PROJECT_ROOT/infrastructure/monitoring/blackbox/blackbox.yml"
    local blackbox_config_dest_dir="/etc/blackbox_exporter"
    local blackbox_config_dest="$blackbox_config_dest_dir/config.yml"

    local targets_tcp_src="$PROJECT_ROOT/infrastructure/monitoring/prometheus/targets/blackbox_tcp.yml"
    local targets_http_src="$PROJECT_ROOT/infrastructure/monitoring/prometheus/targets/blackbox_http.yml"
    local targets_dest_dir="/etc/prometheus/targets"
    local targets_tcp_dest="$targets_dest_dir/blackbox_tcp.yml"
    local targets_http_dest="$targets_dest_dir/blackbox_http.yml"

    if $DRY_RUN; then
        log_info "[DRY-RUN] blackbox config: $blackbox_config_src -> $blackbox_config_dest"
        log_info "[DRY-RUN] blackbox targets: $targets_tcp_src -> $targets_tcp_dest"
        log_info "[DRY-RUN] blackbox targets: $targets_http_src -> $targets_http_dest"
        return 0
    fi

    # Ensure dirs
    sudo mkdir -p "$blackbox_config_dest_dir"
    sudo mkdir -p "$targets_dest_dir"

    if [[ -x "$PROJECT_ROOT/scripts/dev/generate-blackbox-targets.sh" ]]; then
        "$PROJECT_ROOT/scripts/dev/generate-blackbox-targets.sh" || true
    fi

    if [[ -f "$blackbox_config_src" ]]; then
        backup_file "$blackbox_config_dest"
        sudo cp "$blackbox_config_src" "$blackbox_config_dest"
        log_success "blackbox_exporter config установлен: $blackbox_config_dest"
    else
        log_warning "blackbox_exporter config не найден: $blackbox_config_src"
    fi

    if [[ -f "$targets_tcp_src" ]]; then
        backup_file "$targets_tcp_dest"
        sudo cp "$targets_tcp_src" "$targets_tcp_dest"
        log_success "blackbox targets установлен: $targets_tcp_dest"
    else
        log_warning "blackbox targets не найден: $targets_tcp_src (сгенерируйте через scripts/dev/generate-blackbox-targets.sh)"
    fi

    if [[ -f "$targets_http_src" ]]; then
        backup_file "$targets_http_dest"
        sudo cp "$targets_http_src" "$targets_http_dest"
        log_success "blackbox targets установлен: $targets_http_dest"
    else
        log_warning "blackbox targets не найден: $targets_http_src (сгенерируйте через scripts/dev/generate-blackbox-targets.sh)"
    fi
}

# Установка AUR exporters
install_aur_exporters() {
    log_verbose "Установка exporters из AUR..."

    # Проверка наличия AUR helper
    if ! has_aur_helper; then
        log_warning "AUR helper не найден (yay или paru)"
        log_info ""
        log_info "Для установки yay выполните:"
        log_info "  git clone https://aur.archlinux.org/yay.git"
        log_info "  cd yay && makepkg -si"
        log_info ""
        log_info "После установки yay, запустите скрипт повторно"
        return 1
    fi

    local helper
    helper=$(get_aur_helper)
    log_verbose "Используется AUR helper: $helper"

    for pkg in "${AUR_EXPORTER_PACKAGES[@]}"; do
        if is_pkg_installed "$pkg"; then
            local version
            version=$(get_pkg_version "$pkg")
            log_success "$pkg уже установлен: $version"
        else
            if $DRY_RUN; then
                log_info "[DRY-RUN] Будет установлен из AUR: $pkg"
            else
                log_info "Установка $pkg из AUR..."
                aur_install "$pkg"
            fi
        fi
    done
}

# Установка systemd unit files для exporters
install_exporter_services() {
    log_step "Установка systemd unit files для exporters..."

    if $DRY_RUN; then
        log_info "[DRY-RUN] Systemd services:"
        for service in "${EXPORTER_SERVICES[@]}"; do
            if [[ -f "$SYSTEMD_DIR/$service" ]]; then
                log_info "  $SYSTEMD_DIR/$service -> $SYSTEMD_SYSTEM_DIR/$service"
            else
                log_warning "  Файл не найден: $SYSTEMD_DIR/$service"
            fi
        done
        return 0
    fi

    local installed_count=0

    for service in "${EXPORTER_SERVICES[@]}"; do
        local src="$SYSTEMD_DIR/$service"
        local dest="$SYSTEMD_SYSTEM_DIR/$service"

        if [[ ! -f "$src" ]]; then
            log_warning "Systemd unit не найден: $src"
            continue
        fi

        # Бэкап существующего
        backup_file "$dest"

        # Копирование
        sudo cp "$src" "$dest"
        log_verbose "Установлен: $service"
        ((installed_count++))
    done

    if [[ $installed_count -gt 0 ]]; then
        # Reload systemd
        sudo systemctl daemon-reload
        log_success "Установлено systemd unit files: $installed_count"
    fi
}

##############################################################################
# ENABLE AND START SERVICES
##############################################################################

enable_services() {
    log_step "Включение systemd сервисов..."

    if $DRY_RUN; then
        log_info "[DRY-RUN] Будут включены сервисы:"
        $INSTALL_PROMETHEUS && log_info "  - prometheus"
        $INSTALL_GRAFANA && log_info "  - grafana"
        $INSTALL_EXPORTERS && log_info "  - prometheus-node-exporter"
        $INSTALL_EXPORTERS && log_info "  - blackbox-exporter"
        $INSTALL_EXPORTERS && log_info "  - postgres-exporter"
        $INSTALL_EXPORTERS && log_info "  - redis-exporter"
        return 0
    fi

    local services_to_enable=()

    if $INSTALL_PROMETHEUS; then
        services_to_enable+=("prometheus")
    fi

    if $INSTALL_GRAFANA; then
        services_to_enable+=("grafana")
    fi

    if $INSTALL_EXPORTERS; then
        services_to_enable+=("prometheus-node-exporter")
        services_to_enable+=("blackbox-exporter")
        # Добавляем только если пакеты установлены
        is_pkg_installed "prometheus-postgres-exporter" && services_to_enable+=("postgres-exporter")
        is_pkg_installed "prometheus-redis-exporter" && services_to_enable+=("redis-exporter")
    fi

    for service in "${services_to_enable[@]}"; do
        if systemctl list-unit-files | grep -q "^${service}.service"; then
            sudo systemctl enable "$service" 2>/dev/null || true
            log_verbose "Включен автозапуск: $service"
        else
            log_verbose "Сервис не найден: $service"
        fi
    done

    log_success "Сервисы настроены на автозапуск"
}

##############################################################################
# VERIFICATION
##############################################################################

verify_installation() {
    log_step "Проверка установки..."
    echo ""

    local failed=0

    # Prometheus
    if $INSTALL_PROMETHEUS; then
        local prom_name
        prom_name=$(pkg_map_name "prometheus")
        if pkg_is_installed "$prom_name"; then
            local version
            version=$(pkg_version "$prom_name")
            print_status "success" "Prometheus: $version (порт 9090)"
        else
            print_status "error" "Prometheus: не установлен"
            ((failed++))
        fi
    fi

    # Grafana
    if $INSTALL_GRAFANA; then
        local graf_name
        graf_name=$(pkg_map_name "grafana")
        if pkg_is_installed "$graf_name"; then
            local version
            version=$(pkg_version "$graf_name")
            print_status "success" "Grafana: $version (порт 3000)"
        else
            print_status "error" "Grafana: не установлена"
            ((failed++))
        fi
    fi

    # Exporters
    if $INSTALL_EXPORTERS; then
        # node_exporter
        local node_name
        node_name=$(pkg_map_name "node_exporter")
        if pkg_is_installed "$node_name"; then
            local version
            version=$(pkg_version "$node_name")
            print_status "success" "node_exporter: $version (порт 9100)"
        else
            print_status "error" "node_exporter: не установлен"
            ((failed++))
        fi

        # postgres_exporter (AUR)
        if is_pkg_installed "prometheus-postgres-exporter"; then
            local version
            version=$(get_pkg_version "prometheus-postgres-exporter")
            print_status "success" "postgres_exporter: $version (порт 9187)"
        else
            print_status "warning" "postgres_exporter: не установлен (AUR)"
        fi

        # redis_exporter (AUR)
        if is_pkg_installed "prometheus-redis-exporter"; then
            local version
            version=$(get_pkg_version "prometheus-redis-exporter")
            print_status "success" "redis_exporter: $version (порт 9121)"
        else
            print_status "warning" "redis_exporter: не установлен (AUR)"
        fi
    fi

    echo ""

    # Проверка конфигурации
    if [[ -f "$PROMETHEUS_CONFIG_DEST" ]]; then
        print_status "success" "Prometheus config: $PROMETHEUS_CONFIG_DEST"
    else
        print_status "info" "Prometheus config: используется default"
    fi

    echo ""

    if [[ $failed -gt 0 ]]; then
        log_warning "Не установлено компонентов: $failed"
        return 1
    else
        log_success "Все компоненты установлены корректно"
        return 0
    fi
}

##############################################################################
# POST-INSTALL INFO
##############################################################################

show_post_install_info() {
    echo ""
    log_info "Следующие шаги:"
    echo ""

    echo "  1. Запуск сервисов:"
    $INSTALL_PROMETHEUS && echo "     sudo systemctl start prometheus"
    $INSTALL_GRAFANA && echo "     sudo systemctl start grafana"
    $INSTALL_EXPORTERS && echo "     sudo systemctl start prometheus-node-exporter"
    $INSTALL_EXPORTERS && is_pkg_installed "prometheus-postgres-exporter" && echo "     sudo systemctl start postgres-exporter"
    $INSTALL_EXPORTERS && is_pkg_installed "prometheus-redis-exporter" && echo "     sudo systemctl start redis-exporter"
    echo ""

    echo "  2. Проверка статуса:"
    $INSTALL_PROMETHEUS && echo "     systemctl status prometheus"
    $INSTALL_GRAFANA && echo "     systemctl status grafana"
    echo ""

    echo "  3. Веб-интерфейсы:"
    $INSTALL_PROMETHEUS && echo "     Prometheus: http://localhost:9090"
    $INSTALL_GRAFANA && echo "     Grafana: http://localhost:3000 (admin/admin)"
    echo ""

    echo "  4. Проверка метрик:"
    $INSTALL_EXPORTERS && echo "     curl http://localhost:9100/metrics  # node"
    $INSTALL_EXPORTERS && echo "     curl http://localhost:9187/metrics  # postgresql"
    $INSTALL_EXPORTERS && echo "     curl http://localhost:9121/metrics  # redis"
    echo ""

    echo "  5. Или используй скрипт запуска:"
    echo "     ./scripts/dev/start-monitoring.sh"
    echo ""
}

##############################################################################
# MAIN
##############################################################################

main() {
    parse_args "$@"

    echo ""
    echo -e "${BOLD}========================================${NC}"
    echo -e "${BOLD}  Monitoring Stack Installation${NC}"
    echo -e "${BOLD}========================================${NC}"
    echo ""

    # Информация о платформе
    local platform
    platform=$(detect_platform)
    local pm
    pm=$(get_package_manager)

    log_info "Платформа: $platform"
    log_info "Пакетный менеджер: $pm"
    log_info "Версия скрипта: $SCRIPT_VERSION"
    echo ""

    # Режим работы
    if $DRY_RUN; then
        log_warning "Режим DRY-RUN: изменения НЕ будут применены"
        echo ""
    fi

    # План установки
    log_info "План установки:"
    $INSTALL_PROMETHEUS && log_info "  - Prometheus (9090)"
    $INSTALL_GRAFANA && log_info "  - Grafana (3000)"
    $INSTALL_EXPORTERS && log_info "  - node_exporter (9100)"
    $INSTALL_EXPORTERS && log_info "  - postgres_exporter (9187) [AUR]"
    $INSTALL_EXPORTERS && log_info "  - redis_exporter (9121) [AUR]"
    echo ""

    # Проверка sudo для системных операций
    if ! $DRY_RUN; then
        if ! check_sudo; then
            exit 1
        fi
    fi

    # Установка компонентов
    local install_result=0

    if $INSTALL_PROMETHEUS; then
        install_prometheus || install_result=1
        echo ""
    fi

    if $INSTALL_GRAFANA; then
        install_grafana || install_result=1
        echo ""
    fi

    if $INSTALL_EXPORTERS; then
        install_exporters || install_result=1
        echo ""
    fi

    # Включение сервисов
    if ! $DRY_RUN; then
        enable_services
        echo ""
    fi

    # Верификация
    if ! $DRY_RUN; then
        verify_installation
    fi

    # Информация после установки
    if ! $DRY_RUN && [[ $install_result -eq 0 ]]; then
        show_post_install_info
    fi

    return $install_result
}

main "$@"
