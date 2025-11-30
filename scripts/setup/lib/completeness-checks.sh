#!/bin/bash

##############################################################################
# CommandCenter1C - Completeness Checks
##############################################################################
# Проверка полноты установки компонентов
#
# Usage:
#   source scripts/setup/lib/completeness-checks.sh
#   result=$(check_python_completeness)
#   status=$(echo "$result" | cut -d'|' -f1)
#
# Формат возврата функций check_*:
#   "STATUS|MISSING_COMPONENTS|MESSAGE"
#   STATUS: MISSING | INCOMPLETE | READY
#   MISSING_COMPONENTS: через запятую (venv,dev,pip)
#   MESSAGE: человекочитаемое сообщение
##############################################################################

# Предотвращение повторного sourcing
if [ -n "$COMPLETENESS_CHECKS_LOADED" ]; then
    return 0
fi
COMPLETENESS_CHECKS_LOADED=true

##############################################################################
# PYTHON COMPLETENESS
##############################################################################

# check_python_completeness - проверка полноты установки Python
# Проверяет: python3, venv модуль, pip
check_python_completeness() {
    local missing_components=""
    local messages=""

    # Проверка python3
    if ! command_exists python3; then
        echo "MISSING||Python3 не установлен"
        return
    fi

    # Проверка venv модуля (включая ensurepip, необходимый для создания venv)
    if ! python3 -c "import venv; import ensurepip" &>/dev/null; then
        missing_components="venv"
        messages="модуль venv/ensurepip недоступен"
    fi

    # Проверка pip
    if ! python3 -m pip --version &>/dev/null; then
        if [ -n "$missing_components" ]; then
            missing_components="${missing_components},pip"
            messages="${messages}, pip недоступен"
        else
            missing_components="pip"
            messages="pip недоступен"
        fi
    fi

    # Определение статуса
    if [ -n "$missing_components" ]; then
        echo "INCOMPLETE|${missing_components}|Python установлен, но ${messages}"
    else
        echo "READY||Python полностью готов к работе"
    fi
}

# fix_python_incomplete - исправление неполной установки Python
# Usage: fix_python_incomplete "venv,pip"
fix_python_incomplete() {
    local missing=$1
    local pkg_manager=$(detect_package_manager)

    # Получаем версию УСТАНОВЛЕННОГО Python (не требуемого!)
    # python3 --version -> "Python 3.12.3" -> "3.12"
    local py_full_version=$(python3 --version 2>/dev/null | grep -oE '[0-9]+\.[0-9]+\.[0-9]+')
    local py_major_minor=$(echo "$py_full_version" | cut -d'.' -f1,2)  # 3.12.3 -> 3.12

    # Fallback на требуемую версию если не удалось определить
    if [ -z "$py_major_minor" ]; then
        py_major_minor=$(get_required_python_version)
    fi

    # Исправление venv
    if [[ "$missing" == *"venv"* ]]; then
        log_info "Установка python${py_major_minor}-venv..."

        case "$pkg_manager" in
            apt)
                sudo_cmd apt-get update -qq
                sudo_cmd apt-get install -y "python${py_major_minor}-venv" || {
                    # Попробовать без точной версии
                    sudo_cmd apt-get install -y python3-venv
                }
                ;;
            dnf|yum)
                sudo_cmd "$pkg_manager" install -y python3-venv 2>/dev/null || true
                ;;
            pacman)
                # В Arch venv включен в python
                log_info "В Arch Linux venv включен в пакет python"
                ;;
            apk)
                # В Alpine venv включен в python3
                log_info "В Alpine Linux venv включен в пакет python3"
                ;;
            *)
                log_warning "Неизвестный пакетный менеджер, попробуйте установить python3-venv вручную"
                return 1
                ;;
        esac
    fi

    # Исправление pip
    if [[ "$missing" == *"pip"* ]]; then
        log_info "Установка pip через ensurepip..."

        # Сначала пробуем ensurepip
        if python3 -m ensurepip --upgrade &>/dev/null; then
            log_success "pip установлен через ensurepip"
        else
            # Если ensurepip не работает, пробуем через пакетный менеджер
            log_info "ensurepip не сработал, пробуем через пакетный менеджер..."

            case "$pkg_manager" in
                apt)
                    sudo_cmd apt-get update -qq
                    sudo_cmd apt-get install -y python3-pip
                    ;;
                dnf|yum)
                    sudo_cmd "$pkg_manager" install -y python3-pip
                    ;;
                pacman)
                    sudo_cmd pacman -S --noconfirm python-pip
                    ;;
                apk)
                    sudo_cmd apk add py3-pip
                    ;;
                *)
                    log_warning "Не удалось установить pip автоматически"
                    return 1
                    ;;
            esac
        fi
    fi

    return 0
}

##############################################################################
# GO COMPLETENESS
##############################################################################

# check_go_completeness - проверка полноты установки Go
# Проверяет: go в PATH, GOPATH настроен
check_go_completeness() {
    local missing_components=""
    local messages=""

    # Проверка go в PATH
    if ! command_exists go; then
        # Проверяем стандартное расположение
        if [ -x "/usr/local/go/bin/go" ]; then
            echo "INCOMPLETE|PATH|Go установлен в /usr/local/go, но не добавлен в PATH"
            return
        fi
        echo "MISSING||Go не установлен"
        return
    fi

    # Проверка GOPATH
    local gopath=$(go env GOPATH 2>/dev/null)
    if [ -z "$gopath" ]; then
        missing_components="GOPATH"
        messages="GOPATH не настроен"
    fi

    # Определение статуса
    if [ -n "$missing_components" ]; then
        echo "INCOMPLETE|${missing_components}|Go установлен, но ${messages}"
    else
        echo "READY||Go полностью готов к работе"
    fi
}

# fix_go_incomplete - исправление неполной установки Go
# Usage: fix_go_incomplete "PATH"
fix_go_incomplete() {
    local missing=$1

    # Исправление PATH
    if [[ "$missing" == *"PATH"* ]]; then
        log_info "Добавление /usr/local/go/bin в PATH..."

        local shell_rc=""
        local current_shell=$(basename "$SHELL")

        case "$current_shell" in
            bash)
                shell_rc="$HOME/.bashrc"
                ;;
            zsh)
                shell_rc="$HOME/.zshrc"
                ;;
            *)
                shell_rc="$HOME/.profile"
                ;;
        esac

        # Проверяем, не добавлен ли уже
        if ! grep -q '/usr/local/go/bin' "$shell_rc" 2>/dev/null; then
            echo '' >> "$shell_rc"
            echo '# Go (добавлено setup скриптом)' >> "$shell_rc"
            echo 'export PATH=$PATH:/usr/local/go/bin' >> "$shell_rc"
            log_success "Добавлено в $shell_rc"
        else
            log_info "PATH для Go уже настроен в $shell_rc"
        fi

        # Применить изменения для текущей сессии
        export PATH=$PATH:/usr/local/go/bin

        log_warning "Для полного применения выполните: source $shell_rc"
    fi

    # Исправление GOPATH (обычно Go сам создает ~/go)
    if [[ "$missing" == *"GOPATH"* ]]; then
        log_info "GOPATH обычно автоматически устанавливается в ~/go"

        if [ ! -d "$HOME/go" ]; then
            mkdir -p "$HOME/go"
            log_success "Создана директория ~/go"
        fi
    fi

    return 0
}

##############################################################################
# NODE.JS COMPLETENESS
##############################################################################

# check_nodejs_completeness - проверка полноты установки Node.js
# Проверяет: node, npm, npx
check_nodejs_completeness() {
    local missing_components=""
    local messages=""

    # Проверка node
    if ! command_exists node; then
        echo "MISSING||Node.js не установлен"
        return
    fi

    # Проверка npm
    if ! npm --version &>/dev/null; then
        missing_components="npm"
        messages="npm недоступен"
    fi

    # Проверка npx
    if ! npx --version &>/dev/null; then
        if [ -n "$missing_components" ]; then
            missing_components="${missing_components},npx"
            messages="${messages}, npx недоступен"
        else
            missing_components="npx"
            messages="npx недоступен"
        fi
    fi

    # Определение статуса
    if [ -n "$missing_components" ]; then
        echo "INCOMPLETE|${missing_components}|Node.js установлен, но ${messages}"
    else
        echo "READY||Node.js полностью готов к работе"
    fi
}

# fix_nodejs_incomplete - исправление неполной установки Node.js
# Usage: fix_nodejs_incomplete "npm,npx"
fix_nodejs_incomplete() {
    local missing=$1
    local pkg_manager=$(detect_package_manager)

    # npm и npx обычно идут вместе
    if [[ "$missing" == *"npm"* ]] || [[ "$missing" == *"npx"* ]]; then
        log_info "Установка npm..."

        case "$pkg_manager" in
            apt)
                sudo_cmd apt-get update -qq
                sudo_cmd apt-get install -y npm
                ;;
            dnf|yum)
                sudo_cmd "$pkg_manager" install -y npm
                ;;
            pacman)
                sudo_cmd pacman -S --noconfirm npm
                ;;
            apk)
                sudo_cmd apk add npm
                ;;
            brew)
                # На macOS npm идёт с node
                log_info "На macOS npm должен быть включен в пакет node"
                log_warning "Попробуйте переустановить: brew reinstall node"
                return 1
                ;;
            *)
                log_warning "Неизвестный пакетный менеджер, попробуйте установить npm вручную"
                return 1
                ;;
        esac
    fi

    return 0
}

##############################################################################
# DOCKER COMPLETENESS
##############################################################################

# check_docker_completeness - проверка полноты установки Docker
# Для WSL: только docker (compose идёт с Docker Desktop)
# Для Linux: docker, docker compose plugin, daemon, группа docker
check_docker_completeness() {
    local missing_components=""
    local messages=""

    # Проверка docker
    if ! command_exists docker; then
        echo "MISSING||Docker не установлен"
        return
    fi

    # Для WSL проверяем только базовый docker
    if is_wsl; then
        if ! command_exists docker; then
            echo "MISSING||Docker Desktop не установлен или WSL integration отключен"
            return
        fi
        if ! docker compose version &>/dev/null; then
            echo "INCOMPLETE|compose|Docker Desktop не запущен или docker compose недоступен"
            return
        fi
        echo "READY||Docker (WSL) готов к работе"
        return
    fi

    # Для нативного Linux - полная проверка

    # Проверка docker compose plugin
    if ! docker compose version &>/dev/null; then
        missing_components="compose"
        messages="docker compose plugin не установлен"
    fi

    # Проверка daemon
    if ! docker info &>/dev/null; then
        if [ -n "$missing_components" ]; then
            missing_components="${missing_components},daemon"
            messages="${messages}, Docker daemon не запущен"
        else
            missing_components="daemon"
            messages="Docker daemon не запущен"
        fi
    fi

    # Проверка группы docker (если не root)
    if ! is_root; then
        if ! groups | grep -q '\bdocker\b'; then
            if [ -n "$missing_components" ]; then
                missing_components="${missing_components},docker-group"
                messages="${messages}, пользователь не в группе docker"
            else
                missing_components="docker-group"
                messages="пользователь не в группе docker"
            fi
        fi
    fi

    # Определение статуса
    if [ -n "$missing_components" ]; then
        echo "INCOMPLETE|${missing_components}|Docker установлен, но ${messages}"
    else
        echo "READY||Docker полностью готов к работе"
    fi
}

# fix_docker_incomplete - исправление неполной установки Docker
# Usage: fix_docker_incomplete "compose,daemon,docker-group"
fix_docker_incomplete() {
    local missing=$1
    local pkg_manager=$(detect_package_manager)

    # Исправление compose
    if [[ "$missing" == *"compose"* ]]; then
        log_info "Установка docker-compose-plugin..."

        case "$pkg_manager" in
            apt)
                sudo_cmd apt-get update -qq
                sudo_cmd apt-get install -y docker-compose-plugin
                ;;
            dnf|yum)
                sudo_cmd "$pkg_manager" install -y docker-compose-plugin
                ;;
            pacman)
                sudo_cmd pacman -S --noconfirm docker-compose
                ;;
            apk)
                sudo_cmd apk add docker-compose
                ;;
            *)
                log_warning "Неизвестный пакетный менеджер"
                log_info "Установите docker-compose-plugin вручную:"
                log_info "  https://docs.docker.com/compose/install/"
                ;;
        esac
    fi

    # Исправление daemon
    if [[ "$missing" == *"daemon"* ]]; then
        log_info "Запуск Docker daemon..."

        if command_exists systemctl; then
            sudo_cmd systemctl start docker
            sudo_cmd systemctl enable docker
            log_success "Docker daemon запущен и добавлен в автозагрузку"
        elif command_exists service; then
            sudo_cmd service docker start
            log_success "Docker daemon запущен"
            log_warning "Добавьте docker в автозагрузку вручную"
        else
            log_warning "Не удалось запустить Docker daemon автоматически"
            log_info "Запустите Docker daemon вручную"
        fi
    fi

    # Исправление docker-group
    if [[ "$missing" == *"docker-group"* ]]; then
        log_info "Добавление пользователя в группу docker..."

        local current_user=$(whoami)
        sudo_cmd usermod -aG docker "$current_user"

        log_success "Пользователь $current_user добавлен в группу docker"
        log_warning "ВАЖНО: Для применения изменений необходимо:"
        log_warning "  1. Выйти из системы и войти снова, ИЛИ"
        log_warning "  2. Выполнить: newgrp docker"
    fi

    return 0
}

##############################################################################
# HELPER FUNCTIONS
##############################################################################

# parse_check_result - разбор результата проверки
# Usage:
#   result=$(check_python_completeness)
#   status=$(parse_check_result "$result" "status")
#   missing=$(parse_check_result "$result" "missing")
#   message=$(parse_check_result "$result" "message")
parse_check_result() {
    local result=$1
    local field=$2

    case "$field" in
        status)
            echo "$result" | cut -d'|' -f1
            ;;
        missing)
            echo "$result" | cut -d'|' -f2
            ;;
        message)
            echo "$result" | cut -d'|' -f3
            ;;
        *)
            echo ""
            ;;
    esac
}

# check_all_completeness - проверка всех компонентов
# Возвращает сводную информацию
check_all_completeness() {
    local components=("python" "go" "nodejs" "docker")
    local all_ready=true

    for component in "${components[@]}"; do
        local result=$(check_${component}_completeness)
        local status=$(parse_check_result "$result" "status")
        local message=$(parse_check_result "$result" "message")

        case "$status" in
            READY)
                log_success "${component}: ${message}"
                ;;
            INCOMPLETE)
                log_warning "${component}: ${message}"
                all_ready=false
                ;;
            MISSING)
                log_error "${component}: ${message}"
                all_ready=false
                ;;
        esac
    done

    if $all_ready; then
        return 0
    else
        return 1
    fi
}

##############################################################################
# End of completeness-checks.sh
##############################################################################
