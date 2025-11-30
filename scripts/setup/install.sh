#!/bin/bash

##############################################################################
# CommandCenter1C - Development Environment Setup
##############################################################################
#
# Универсальный скрипт установки зависимостей для разработчиков.
# Автоматически определяет ОС и устанавливает необходимые компоненты.
#
# Usage:
#   ./scripts/setup/install.sh [OPTIONS]
#
# Options:
#   --dry-run           Показать что будет установлено без изменений
#   --only-go           Установить только Go
#   --only-python       Установить только Python + venv
#   --only-nodejs       Установить только Node.js + npm
#   --only-docker       Установить только Docker
#   --only-deps         Установить только зависимости проекта (pip, npm, go mod)
#   --skip-docker       Пропустить установку Docker
#   --skip-deps         Пропустить установку зависимостей проекта
#   --force             Принудительная переустановка
#   --verbose           Подробный вывод
#   --help              Показать справку
#
# Examples:
#   ./scripts/setup/install.sh                    # Полная установка
#   ./scripts/setup/install.sh --dry-run          # Проверка
#   ./scripts/setup/install.sh --only-go --only-python
#   ./scripts/setup/install.sh --skip-docker
#
##############################################################################

set -e  # Exit on error

# Определить директории (используем уникальные имена, чтобы избежать конфликтов)
INSTALL_SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$INSTALL_SCRIPT_DIR/../.." && pwd)"

# Загрузить библиотеки
source "$INSTALL_SCRIPT_DIR/lib/common.sh"
source "$INSTALL_SCRIPT_DIR/lib/version-parser.sh"
source "$INSTALL_SCRIPT_DIR/lib/completeness-checks.sh"

##############################################################################
# CLI ARGUMENTS
##############################################################################

DRY_RUN=false
VERBOSE=false
FORCE=false
SKIP_DOCKER=false
SKIP_DEPS=false

# Флаги --only-*
ONLY_GO=false
ONLY_PYTHON=false
ONLY_NODEJS=false
ONLY_DOCKER=false
ONLY_DEPS=false

# Парсинг аргументов
parse_args() {
    while [[ $# -gt 0 ]]; do
        case $1 in
            --dry-run)
                DRY_RUN=true
                shift
                ;;
            --only-go)
                ONLY_GO=true
                shift
                ;;
            --only-python)
                ONLY_PYTHON=true
                shift
                ;;
            --only-nodejs)
                ONLY_NODEJS=true
                shift
                ;;
            --only-docker)
                ONLY_DOCKER=true
                shift
                ;;
            --only-deps)
                ONLY_DEPS=true
                shift
                ;;
            --skip-docker)
                SKIP_DOCKER=true
                shift
                ;;
            --skip-deps)
                SKIP_DEPS=true
                shift
                ;;
            --force)
                FORCE=true
                shift
                ;;
            --verbose|-v)
                VERBOSE=true
                shift
                ;;
            --help|-h)
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
    cat << EOF
CommandCenter1C - Development Environment Setup

Usage:
  ./scripts/setup/install.sh [OPTIONS]

Options:
  --dry-run           Показать что будет установлено без изменений
  --only-go           Установить только Go
  --only-python       Установить только Python + venv
  --only-nodejs       Установить только Node.js + npm
  --only-docker       Установить только Docker
  --only-deps         Установить только зависимости проекта
  --skip-docker       Пропустить установку Docker
  --skip-deps         Пропустить установку зависимостей проекта
  --force             Принудительная переустановка
  --verbose, -v       Подробный вывод
  --help, -h          Показать эту справку

Examples:
  ./scripts/setup/install.sh                    # Полная установка
  ./scripts/setup/install.sh --dry-run          # Показать план
  ./scripts/setup/install.sh --only-go          # Только Go
  ./scripts/setup/install.sh --skip-docker      # Всё кроме Docker
EOF
}

# Проверка --only-* флагов
has_only_flags() {
    $ONLY_GO || $ONLY_PYTHON || $ONLY_NODEJS || $ONLY_DOCKER || $ONLY_DEPS
}

should_install() {
    local component=$1

    # Если нет --only-* флагов, устанавливаем всё
    if ! has_only_flags; then
        return 0
    fi

    # Иначе проверяем конкретный флаг
    case $component in
        go)      $ONLY_GO ;;
        python)  $ONLY_PYTHON ;;
        nodejs)  $ONLY_NODEJS ;;
        docker)  $ONLY_DOCKER ;;
        deps)    $ONLY_DEPS ;;
        *)       return 1 ;;
    esac
}

##############################################################################
# SYSTEM PACKAGES INSTALLATION
##############################################################################

install_system_packages() {
    log_section "Системные пакеты"

    local pkg_manager=$(detect_package_manager)
    log_info "Пакетный менеджер: $pkg_manager"

    # Список базовых пакетов
    local packages=("git" "curl" "wget" "jq")

    # Пакеты для сборки
    case $pkg_manager in
        apt)
            packages+=("build-essential" "libpq-dev" "ca-certificates" "gnupg")
            ;;
        dnf|yum)
            packages+=("gcc" "gcc-c++" "make" "postgresql-devel")
            ;;
        pacman)
            packages+=("base-devel" "postgresql-libs")
            ;;
    esac

    if $DRY_RUN; then
        log_info "[DRY-RUN] Будут установлены пакеты: ${packages[*]}"
        return
    fi

    case $pkg_manager in
        apt)
            log_info "Обновление списка пакетов..."
            sudo_cmd apt-get update -qq

            log_info "Установка пакетов: ${packages[*]}"
            sudo_cmd apt-get install -y -qq "${packages[@]}"
            ;;
        dnf)
            log_info "Установка пакетов: ${packages[*]}"
            sudo_cmd dnf install -y -q "${packages[@]}"
            ;;
        yum)
            sudo_cmd yum install -y -q "${packages[@]}"
            ;;
        pacman)
            sudo_cmd pacman -Syu --noconfirm --quiet "${packages[@]}"
            ;;
        *)
            log_warning "Неизвестный пакетный менеджер: $pkg_manager"
            log_warning "Установите вручную: ${packages[*]}"
            ;;
    esac

    log_success "Системные пакеты установлены"
}

##############################################################################
# GO INSTALLATION
##############################################################################

install_go() {
    local required_version=$(get_required_go_version)
    local current_version=$(get_command_version "go")
    local action="SKIP"
    local missing=""

    log_subsection "Go"

    # Проверка полноты установки
    local completeness=$(check_go_completeness)
    local status=$(echo "$completeness" | cut -d'|' -f1)
    missing=$(echo "$completeness" | cut -d'|' -f2)

    # Определить действие на основе статуса
    case "$status" in
        MISSING)
            action="INSTALL"
            ;;
        INCOMPLETE)
            action="FIX"
            ;;
        READY)
            if ! version_gte "$current_version" "$required_version"; then
                action="UPGRADE"
            elif $FORCE; then
                action="REINSTALL"
            fi
            ;;
    esac

    log_info "Требуется: $required_version"
    log_info "Текущая:   ${current_version:-не установлен}"
    [ -n "$missing" ] && log_info "Недостающее: $missing"
    log_info "Действие:  $action"

    if [ "$action" = "SKIP" ]; then
        log_success "Go $current_version уже установлен и полностью готов"
        return
    fi

    if $DRY_RUN; then
        case "$action" in
            FIX)     log_info "[DRY-RUN] Будет исправлено: $missing" ;;
            *)       log_info "[DRY-RUN] Будет установлен Go $required_version" ;;
        esac
        return
    fi

    # Исправление неполной установки
    if [ "$action" = "FIX" ]; then
        if fix_go_incomplete "$missing"; then
            log_success "Go настроен"
        else
            log_error "Не удалось настроить Go"
            return 1
        fi
        return
    fi

    # Определить архитектуру
    local arch=$(uname -m)
    case $arch in
        x86_64)  arch="amd64" ;;
        aarch64) arch="arm64" ;;
        armv7l)  arch="armv6l" ;;
    esac

    local os="linux"
    if [ "$(detect_os)" = "macos" ]; then
        os="darwin"
    fi

    local go_tarball="go${required_version}.${os}-${arch}.tar.gz"
    local download_url="https://go.dev/dl/${go_tarball}"
    local tmp_file="/tmp/${go_tarball}"

    log_info "Скачивание Go $required_version..."
    download_file "$download_url" "$tmp_file"

    log_info "Установка в /usr/local/go..."
    sudo_cmd rm -rf /usr/local/go
    sudo_cmd tar -C /usr/local -xzf "$tmp_file"
    rm -f "$tmp_file"

    # Добавить в PATH если нужно
    local go_path_line='export PATH=$PATH:/usr/local/go/bin'
    local profile_file="$HOME/.bashrc"

    if [ -f "$HOME/.zshrc" ]; then
        profile_file="$HOME/.zshrc"
    fi

    if ! grep -q '/usr/local/go/bin' "$profile_file" 2>/dev/null; then
        echo "" >> "$profile_file"
        echo "# Go" >> "$profile_file"
        echo "$go_path_line" >> "$profile_file"
        log_info "Добавлено в $profile_file"
    fi

    # Обновить PATH для текущей сессии
    export PATH=$PATH:/usr/local/go/bin

    log_success "Go $required_version установлен"
}

##############################################################################
# PYTHON INSTALLATION
##############################################################################

install_python() {
    local required_version=$(get_required_python_version)
    local current_version=$(get_command_version "python3")
    local action="SKIP"
    local missing=""

    log_subsection "Python"

    # Проверка полноты установки
    local completeness=$(check_python_completeness)
    local status=$(echo "$completeness" | cut -d'|' -f1)
    missing=$(echo "$completeness" | cut -d'|' -f2)

    case "$status" in
        MISSING)
            action="INSTALL"
            ;;
        INCOMPLETE)
            action="FIX"
            ;;
        READY)
            if ! version_gte "$current_version" "$required_version"; then
                action="UPGRADE"
            elif $FORCE; then
                action="REINSTALL"
            fi
            ;;
    esac

    log_info "Требуется: $required_version+"
    log_info "Текущая:   ${current_version:-не установлен}"
    [ -n "$missing" ] && log_info "Недостающее: $missing"
    log_info "Действие:  $action"

    if [ "$action" = "SKIP" ]; then
        log_success "Python $current_version уже установлен и полностью готов"
        return
    fi

    if $DRY_RUN; then
        case "$action" in
            FIX)     log_info "[DRY-RUN] Будет исправлено: $missing" ;;
            *)       log_info "[DRY-RUN] Будет установлен Python $required_version" ;;
        esac
        return
    fi

    if [ "$action" = "FIX" ]; then
        if fix_python_incomplete "$missing"; then
            log_success "Python дополнен"
        else
            log_error "Не удалось настроить Python"
            return 1
        fi
        return
    fi

    local pkg_manager=$(detect_package_manager)
    local python_pkg="python${required_version}"

    case $pkg_manager in
        apt)
            # Добавить deadsnakes PPA для свежих версий Python
            if ! apt-cache show "python${required_version}" &>/dev/null; then
                log_info "Добавление deadsnakes PPA..."
                sudo_cmd apt-get install -y software-properties-common
                sudo_cmd add-apt-repository -y ppa:deadsnakes/ppa
                sudo_cmd apt-get update -qq
            fi

            log_info "Установка Python ${required_version}..."
            sudo_cmd apt-get install -y -qq \
                "python${required_version}" \
                "python${required_version}-venv" \
                "python${required_version}-dev"
            ;;
        dnf)
            sudo_cmd dnf install -y "python${required_version}" "python${required_version}-devel"
            ;;
        pacman)
            sudo_cmd pacman -Syu --noconfirm python python-pip
            ;;
        *)
            log_warning "Установите Python ${required_version}+ вручную"
            return 1
            ;;
    esac

    log_success "Python ${required_version} установлен"
}

##############################################################################
# NODE.JS INSTALLATION
##############################################################################

install_nodejs() {
    local required_version=$(get_required_nodejs_version)

    # Валидация версии (защита от injection)
    if ! [[ "$required_version" =~ ^[0-9]+$ ]]; then
        log_error "Некорректная версия Node.js: $required_version"
        return 1
    fi

    local current_version=$(get_command_version "node")
    local action="SKIP"
    local missing=""

    log_subsection "Node.js"

    # Проверка полноты установки
    local completeness=$(check_nodejs_completeness)
    local status=$(echo "$completeness" | cut -d'|' -f1)
    missing=$(echo "$completeness" | cut -d'|' -f2)

    case "$status" in
        MISSING)
            action="INSTALL"
            ;;
        INCOMPLETE)
            action="FIX"
            ;;
        READY)
            local current_major=$(echo "$current_version" | cut -d'.' -f1)
            if [ "$current_major" -lt "$required_version" ]; then
                action="UPGRADE"
            elif $FORCE; then
                action="REINSTALL"
            fi
            ;;
    esac

    log_info "Требуется: $required_version+"
    log_info "Текущая:   ${current_version:-не установлен}"
    [ -n "$missing" ] && log_info "Недостающее: $missing"
    log_info "Действие:  $action"

    if [ "$action" = "SKIP" ]; then
        log_success "Node.js $current_version уже установлен и полностью готов"
        return
    fi

    if $DRY_RUN; then
        case "$action" in
            FIX)     log_info "[DRY-RUN] Будет исправлено: $missing" ;;
            *)       log_info "[DRY-RUN] Будет установлен Node.js $required_version" ;;
        esac
        return
    fi

    if [ "$action" = "FIX" ]; then
        if fix_nodejs_incomplete "$missing"; then
            log_success "Node.js дополнен"
        else
            log_error "Не удалось настроить Node.js"
            return 1
        fi
        return
    fi

    local pkg_manager=$(detect_package_manager)

    case $pkg_manager in
        apt)
            # NodeSource repository
            log_info "Добавление NodeSource репозитория..."
            curl -fsSL "https://deb.nodesource.com/setup_${required_version}.x" | sudo_cmd bash -

            log_info "Установка Node.js..."
            sudo_cmd apt-get install -y -qq nodejs
            ;;
        dnf)
            curl -fsSL "https://rpm.nodesource.com/setup_${required_version}.x" | sudo_cmd bash -
            sudo_cmd dnf install -y nodejs
            ;;
        pacman)
            sudo_cmd pacman -Syu --noconfirm nodejs npm
            ;;
        *)
            log_warning "Установите Node.js ${required_version}+ вручную"
            log_info "Рекомендуем использовать nvm: https://github.com/nvm-sh/nvm"
            return 1
            ;;
    esac

    log_success "Node.js $(node --version) установлен"
}

##############################################################################
# DOCKER INSTALLATION
##############################################################################

install_docker() {
    local required_version=$(get_required_docker_version)
    local current_version=$(get_command_version "docker")
    local compose_version=$(get_command_version "compose")
    local action="SKIP"
    local missing=""

    log_subsection "Docker"

    # Проверка полноты установки
    local completeness=$(check_docker_completeness)
    local status=$(echo "$completeness" | cut -d'|' -f1)
    missing=$(echo "$completeness" | cut -d'|' -f2)

    # WSL: проверяем Docker Desktop из Windows
    if is_wsl; then
        log_info "Обнаружен WSL"
        if command_exists docker; then
            log_success "Docker Desktop обнаружен через WSL integration"
            log_info "Docker version: $current_version"
            log_info "Compose version: $compose_version"
            return
        else
            log_warning "Docker Desktop не обнаружен в WSL"
            log_info "Установите Docker Desktop для Windows и включите WSL integration:"
            log_info "  https://docs.docker.com/desktop/windows/wsl/"
            return 1
        fi
    fi

    case "$status" in
        MISSING)
            action="INSTALL"
            ;;
        INCOMPLETE)
            action="FIX"
            ;;
        READY)
            if ! version_gte "$current_version" "$required_version"; then
                action="UPGRADE"
            elif $FORCE; then
                action="REINSTALL"
            fi
            ;;
    esac

    log_info "Требуется: Docker $required_version+, Compose 2.0+"
    log_info "Docker:    ${current_version:-не установлен}"
    log_info "Compose:   ${compose_version:-не установлен}"
    [ -n "$missing" ] && log_info "Недостающее: $missing"
    log_info "Действие:  $action"

    if [ "$action" = "SKIP" ]; then
        log_success "Docker уже установлен и полностью готов"
        return
    fi

    if $DRY_RUN; then
        case "$action" in
            FIX)     log_info "[DRY-RUN] Будет исправлено: $missing" ;;
            *)       log_info "[DRY-RUN] Будет установлен Docker" ;;
        esac
        return
    fi

    if [ "$action" = "FIX" ]; then
        if fix_docker_incomplete "$missing"; then
            log_success "Docker дополнен"
        else
            log_error "Не удалось настроить Docker"
            return 1
        fi
        return
    fi

    local pkg_manager=$(detect_package_manager)
    local distro=$(detect_distro)

    case $pkg_manager in
        apt)
            log_info "Установка Docker через официальный репозиторий..."

            # Удалить старые версии
            sudo_cmd apt-get remove -y docker docker-engine docker.io containerd runc 2>/dev/null || true

            # Установить зависимости
            sudo_cmd apt-get install -y ca-certificates curl gnupg

            # Добавить GPG ключ Docker
            sudo_cmd install -m 0755 -d /etc/apt/keyrings
            curl -fsSL "https://download.docker.com/linux/${distro}/gpg" | \
                sudo_cmd gpg --dearmor -o /etc/apt/keyrings/docker.gpg
            sudo_cmd chmod a+r /etc/apt/keyrings/docker.gpg

            # Добавить репозиторий
            echo \
                "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/${distro} \
                $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | \
                sudo_cmd tee /etc/apt/sources.list.d/docker.list > /dev/null

            # Установить Docker
            sudo_cmd apt-get update -qq
            sudo_cmd apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
            ;;

        dnf)
            sudo_cmd dnf config-manager --add-repo https://download.docker.com/linux/fedora/docker-ce.repo
            sudo_cmd dnf install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
            sudo_cmd systemctl start docker
            sudo_cmd systemctl enable docker
            ;;

        *)
            log_warning "Установите Docker вручную: https://docs.docker.com/engine/install/"
            return 1
            ;;
    esac

    # Добавить пользователя в группу docker
    if ! groups | grep -q docker; then
        log_info "Добавление пользователя в группу docker..."
        sudo_cmd usermod -aG docker "$USER"
        log_warning "Перезайдите в систему для применения изменений группы docker"
    fi

    log_success "Docker установлен"
}

##############################################################################
# PROJECT DEPENDENCIES
##############################################################################

install_project_deps() {
    log_section "Зависимости проекта"

    if $DRY_RUN; then
        log_info "[DRY-RUN] Будут установлены:"
        log_info "  - Python: pip install -r requirements.txt"
        log_info "  - Node.js: npm ci"
        log_info "  - Go: go mod download для всех сервисов"
        return
    fi

    # Python venv + pip
    install_python_deps

    # Node.js npm
    install_nodejs_deps

    # Go modules
    install_go_deps
}

install_python_deps() {
    log_subsection "Python зависимости"

    local venv_dir="$PROJECT_ROOT/orchestrator/venv"
    local requirements="$PROJECT_ROOT/orchestrator/requirements.txt"
    local python_cmd="python3"

    # Найти правильный python
    local required_version=$(get_required_python_version)
    if command_exists "python${required_version}"; then
        python_cmd="python${required_version}"
    fi

    local activate_script="$venv_dir/${VENV_BIN_DIR:-bin}/activate"

    # Создать venv если не существует или сломан (нет activate)
    if [ ! -d "$venv_dir" ] || [ ! -f "$activate_script" ]; then
        if [ -d "$venv_dir" ]; then
            log_warning "venv повреждён (нет activate), пересоздаём..."
            rm -rf "$venv_dir"
        fi
        log_info "Создание виртуального окружения..."
        if ! $python_cmd -m venv "$venv_dir"; then
            log_error "Не удалось создать venv. Проверьте что установлен python3-venv"
            return 1
        fi
    fi

    # Активировать venv
    source "$activate_script"

    # Обновить pip
    log_info "Обновление pip..."
    pip install --upgrade pip -q

    # Установить зависимости
    if [ -f "$requirements" ]; then
        log_info "Установка зависимостей из requirements.txt..."
        pip install -r "$requirements" -q

        local pkg_count=$(pip list --format=freeze | wc -l)
        log_success "Установлено $pkg_count Python пакетов"
    else
        log_warning "requirements.txt не найден"
    fi

    deactivate
}

install_nodejs_deps() {
    log_subsection "Node.js зависимости"

    local frontend_dir="$PROJECT_ROOT/frontend"

    if [ ! -f "$frontend_dir/package.json" ]; then
        log_warning "package.json не найден в frontend/"
        return
    fi

    cd "$frontend_dir"

    # Используем npm ci для чистой установки если есть package-lock.json
    if [ -f "package-lock.json" ]; then
        log_info "Установка зависимостей через npm ci..."
        npm ci --silent
    else
        log_info "Установка зависимостей через npm install..."
        npm install --silent
    fi

    local pkg_count=$(npm list --depth=0 2>/dev/null | wc -l)
    log_success "Установлено ~$pkg_count npm пакетов"

    cd "$PROJECT_ROOT"
}

install_go_deps() {
    log_subsection "Go зависимости"

    local go_services_dir="$PROJECT_ROOT/go-services"

    if [ ! -d "$go_services_dir" ]; then
        log_warning "Директория go-services не найдена"
        return
    fi

    # Проверить что go в PATH
    if ! command_exists go; then
        export PATH=$PATH:/usr/local/go/bin
    fi

    # Для каждого сервиса с go.mod
    for service_dir in "$go_services_dir"/*/; do
        local service_name=$(basename "$service_dir")

        if [ -f "$service_dir/go.mod" ]; then
            log_info "go mod download для $service_name..."
            (cd "$service_dir" && go mod download)
        fi
    done

    log_success "Go модули загружены"
}

##############################################################################
# VERSION CHECK & REPORT
##############################################################################

check_versions() {
    log_section "Проверка установленных версий"

    # Требуемые версии
    local req_go=$(get_required_go_version)
    local req_py=$(get_required_python_version)
    local req_node=$(get_required_nodejs_version)
    local req_docker=$(get_required_docker_version)

    # Текущие версии
    local cur_go=$(get_command_version "go")
    local cur_py=$(get_command_version "python3")
    local cur_node=$(get_command_version "node")
    local cur_docker=$(get_command_version "docker")
    local cur_compose=$(get_command_version "compose")

    # Определить действия через completeness checks
    local go_check=$(check_go_completeness)
    local py_check=$(check_python_completeness)
    local node_check=$(check_nodejs_completeness)
    local docker_check=$(check_docker_completeness)

    local act_go=$(echo "$go_check" | cut -d'|' -f1)
    local act_py=$(echo "$py_check" | cut -d'|' -f1)
    local act_node=$(echo "$node_check" | cut -d'|' -f1)
    local act_docker=$(echo "$docker_check" | cut -d'|' -f1)

    # Преобразовать READY в OK, проверить версии
    if [ "$act_go" = "READY" ]; then
        version_gte "$cur_go" "$req_go" && act_go="OK" || act_go="UPGRADE"
    fi
    [ "$act_go" = "MISSING" ] && act_go="INSTALL"
    [ "$act_go" = "INCOMPLETE" ] && act_go="FIX"

    if [ "$act_py" = "READY" ]; then
        version_gte "$cur_py" "$req_py" && act_py="OK" || act_py="UPGRADE"
    fi
    [ "$act_py" = "MISSING" ] && act_py="INSTALL"
    [ "$act_py" = "INCOMPLETE" ] && act_py="FIX"

    if [ "$act_node" = "READY" ]; then
        local cur_node_major=$(echo "$cur_node" | cut -d'.' -f1)
        [ "$cur_node_major" -ge "$req_node" ] && act_node="OK" || act_node="UPGRADE"
    fi
    [ "$act_node" = "MISSING" ] && act_node="INSTALL"
    [ "$act_node" = "INCOMPLETE" ] && act_node="FIX"

    if [ "$act_docker" = "READY" ]; then
        version_gte "$cur_docker" "$req_docker" && act_docker="OK" || act_docker="UPGRADE"
    fi
    [ "$act_docker" = "MISSING" ] && act_docker="INSTALL"
    [ "$act_docker" = "INCOMPLETE" ] && act_docker="FIX"

    # Вывести таблицу
    print_table_header
    print_table_row "Go" "$req_go" "$cur_go" "$act_go"
    print_table_row "Python" "${req_py}+" "$cur_py" "$act_py"
    print_table_row "Node.js" "${req_node}+" "$cur_node" "$act_node"
    print_table_row "Docker" "${req_docker}+" "$cur_docker" "$act_docker"
    print_table_row "Compose" "2.0+" "$cur_compose" "${cur_compose:+OK}"
    print_table_footer

    echo ""

    # Записать в глобальные переменные для использования
    NEED_GO=$( [ "$act_go" != "OK" ] && echo true || echo false )
    NEED_PYTHON=$( [ "$act_py" != "OK" ] && echo true || echo false )
    NEED_NODEJS=$( [ "$act_node" != "OK" ] && echo true || echo false )
    NEED_DOCKER=$( [ "$act_docker" != "OK" ] && echo true || echo false )
}

##############################################################################
# FINAL REPORT
##############################################################################

print_final_report() {
    log_section "Установка завершена!"

    echo "Установленные компоненты:"
    echo "  - Go:        $(get_command_version go)"
    echo "  - Python:    $(get_command_version python3)"
    echo "  - Node.js:   $(get_command_version node)"
    echo "  - npm:       $(get_command_version npm)"
    echo "  - Docker:    $(get_command_version docker)"
    echo "  - Compose:   $(get_command_version 'compose')"
    echo ""

    log_info "Следующие шаги:"
    echo ""
    echo "  1. Запустить инфраструктуру:"
    echo "     docker compose up -d postgres redis"
    echo ""
    echo "  2. Применить миграции:"
    echo "     ./scripts/dev/run-migrations.sh"
    echo ""
    echo "  3. Запустить все сервисы:"
    echo "     ./scripts/dev/start-all.sh"
    echo ""
    echo "  4. Проверить статус:"
    echo "     ./scripts/dev/health-check.sh"
    echo ""
}

##############################################################################
# MAIN
##############################################################################

main() {
    parse_args "$@"

    # Заголовок
    echo ""
    echo -e "${BOLD}════════════════════════════════════════════════════════════════${NC}"
    echo -e "${BOLD}  CommandCenter1C - Development Environment Setup${NC}"
    echo -e "${BOLD}════════════════════════════════════════════════════════════════${NC}"
    echo ""

    # Информация о платформе
    log_section "Определение платформы"

    local os=$(detect_os)
    local distro=$(detect_distro)
    local pkg_manager=$(detect_package_manager)

    log_info "ОС:              $os"
    log_info "Дистрибутив:     $distro"
    log_info "Пакетный менеджер: $pkg_manager"

    if is_wsl; then
        log_info "WSL:             Да (Docker должен быть установлен в Windows)"
    fi

    # Показать требуемые версии
    print_required_versions

    # Проверить текущие версии
    check_versions

    if $DRY_RUN; then
        log_warning "Режим DRY-RUN: изменения НЕ будут применены"
        echo ""
    fi

    # Установка системных пакетов (всегда, если не --only-*)
    if ! has_only_flags; then
        install_system_packages
    fi

    # Установка компонентов
    if should_install "go"; then
        install_go
    fi

    if should_install "python"; then
        install_python
    fi

    if should_install "nodejs"; then
        install_nodejs
    fi

    if should_install "docker" && ! $SKIP_DOCKER; then
        install_docker
    fi

    # Установка зависимостей проекта
    if should_install "deps" && ! $SKIP_DEPS && ! $DRY_RUN; then
        install_project_deps
    fi

    # Финальный отчет
    if ! $DRY_RUN; then
        print_final_report
    fi
}

# Запуск
main "$@"
