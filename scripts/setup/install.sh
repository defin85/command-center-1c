#!/bin/bash

##############################################################################
# CommandCenter1C - Development Environment Setup
##############################################################################
#
# Использует mise для управления Go, Python, Node.js
# Docker устанавливается отдельно (платформо-зависимо)
#
# Usage:
#   ./scripts/setup/install.sh [OPTIONS]
#
# Options:
#   --dry-run           Показать план без изменений
#   --only-mise         Установить только mise
#   --only-docker       Установить только Docker
#   --only-deps         Установить только зависимости проекта
#   --skip-mise         Пропустить установку mise и runtime'ов
#   --skip-docker       Пропустить установку Docker
#   --skip-deps         Пропустить установку зависимостей проекта
#   --verbose, -v       Подробный вывод
#   --help, -h          Показать справку
#
# Examples:
#   ./scripts/setup/install.sh                # Полная установка
#   ./scripts/setup/install.sh --dry-run      # Показать план
#   ./scripts/setup/install.sh --only-mise    # Только mise + runtime'ы
#   ./scripts/setup/install.sh --skip-docker  # Всё кроме Docker
#
##############################################################################

set -e

# Версия скрипта
SCRIPT_VERSION="1.0.0"

# Директории
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

# Cleanup при выходе
TEMP_FILES=()
cleanup() {
    local exit_code=$?
    for f in "${TEMP_FILES[@]}"; do
        rm -f "$f" 2>/dev/null || true
    done
    exit $exit_code
}
trap cleanup EXIT INT TERM

# Функция для регистрации временных файлов
register_temp_file() {
    TEMP_FILES+=("$1")
}

# Подключение единой библиотеки
if [[ -f "$PROJECT_ROOT/scripts/lib/init.sh" ]]; then
    source "$PROJECT_ROOT/scripts/lib/init.sh"
else
    echo "FATAL: scripts/lib/init.sh не найден в $PROJECT_ROOT" >&2
    exit 1
fi

##############################################################################
# CLI ARGUMENTS
##############################################################################

DRY_RUN=false
VERBOSE=false
SKIP_MISE=false
SKIP_DOCKER=false
SKIP_DEPS=false

ONLY_MISE=false
ONLY_DOCKER=false
ONLY_DEPS=false

# Offline режим
MODE="install"  # install | prepare_offline | install_offline
OFFLINE_BUNDLE_DIR=""
OFFLINE_PLATFORM=""
SKIP_NPM=false
SKIP_PIP=false
SKIP_VERIFY=false

parse_args() {
    while [[ $# -gt 0 ]]; do
        case $1 in
            --dry-run)      DRY_RUN=true; shift ;;
            --only-mise)    ONLY_MISE=true; shift ;;
            --only-docker)  ONLY_DOCKER=true; shift ;;
            --only-deps)    ONLY_DEPS=true; shift ;;
            --skip-mise)    SKIP_MISE=true; shift ;;
            --skip-docker)  SKIP_DOCKER=true; shift ;;
            --skip-deps)    SKIP_DEPS=true; shift ;;
            --verbose|-v)   VERBOSE=true; shift ;;
            --help|-h)      show_help; exit 0 ;;
            --prepare-offline)  MODE="prepare_offline"; shift ;;
            --offline)          MODE="install_offline"; shift ;;
            --bundle=*)         OFFLINE_BUNDLE_DIR="${1#*=}"; shift ;;
            --platform=*)       OFFLINE_PLATFORM="${1#*=}"; shift ;;
            --skip-npm)         SKIP_NPM=true; shift ;;
            --skip-pip)         SKIP_PIP=true; shift ;;
            --skip-verify)      SKIP_VERIFY=true; shift ;;
            *)
                log_error "Неизвестный параметр: $1"
                show_help
                exit 1
                ;;
        esac
    done

    # Валидация конфликтующих флагов
    validate_flags
}

validate_flags() {
    # Проверка конфликтов --only-X и --skip-X
    if [[ "$ONLY_MISE" == "true" && "$SKIP_MISE" == "true" ]]; then
        log_error "Конфликтующие флаги: --only-mise и --skip-mise"
        exit 1
    fi

    if [[ "$ONLY_DOCKER" == "true" && "$SKIP_DOCKER" == "true" ]]; then
        log_error "Конфликтующие флаги: --only-docker и --skip-docker"
        exit 1
    fi

    if [[ "$ONLY_DEPS" == "true" && "$SKIP_DEPS" == "true" ]]; then
        log_error "Конфликтующие флаги: --only-deps и --skip-deps"
        exit 1
    fi

    # Проверка множественных --only-X флагов
    local only_count=0
    [[ "$ONLY_MISE" == "true" ]] && only_count=$((only_count + 1))
    [[ "$ONLY_DOCKER" == "true" ]] && only_count=$((only_count + 1))
    [[ "$ONLY_DEPS" == "true" ]] && only_count=$((only_count + 1))

    if [[ $only_count -gt 1 ]]; then
        log_error "Можно указать только один --only-X флаг"
        exit 1
    fi
}

show_help() {
    cat << 'EOF'
CommandCenter1C - Development Environment Setup (mise edition)

Usage:
  ./scripts/setup/install.sh [OPTIONS]

Options:
  --dry-run           Показать план без изменений
  --only-mise         Установить только mise + runtime'ы (Go, Python, Node.js)
  --only-docker       Установить только Docker
  --only-deps         Установить только зависимости проекта (pip, npm, go mod)
  --skip-mise         Пропустить установку mise и runtime'ов
  --skip-docker       Пропустить установку Docker
  --skip-deps         Пропустить установку зависимостей проекта
  --verbose, -v       Подробный вывод
  --help, -h          Показать эту справку

Offline режим:
  --prepare-offline       Подготовить bundle для offline установки
  --offline               Установить из локального bundle
  --bundle=DIR            Путь к bundle (default: ./offline-bundle)
  --platform=PLATFORM     Платформа для bundle (linux-amd64, linux-arm64)
  --skip-npm              Не включать npm packages в bundle
  --skip-pip              Не включать pip packages в bundle
  --skip-verify           Пропустить проверку checksums при offline установке

Examples:
  ./scripts/setup/install.sh                # Полная установка
  ./scripts/setup/install.sh --dry-run      # Показать план
  ./scripts/setup/install.sh --only-mise    # Только mise + runtime'ы
  ./scripts/setup/install.sh --skip-docker  # Всё кроме Docker

  # Offline режим
  ./scripts/setup/install.sh --prepare-offline --platform=linux-amd64
  ./scripts/setup/install.sh --offline --bundle=/path/to/bundle
EOF
}

has_only_flags() {
    $ONLY_MISE || $ONLY_DOCKER || $ONLY_DEPS
}

should_install() {
    local component=$1

    if ! has_only_flags; then
        case $component in
            mise)   ! $SKIP_MISE ;;
            docker) ! $SKIP_DOCKER ;;
            deps)   ! $SKIP_DEPS ;;
            *)      return 1 ;;
        esac
    else
        case $component in
            mise)   $ONLY_MISE ;;
            docker) $ONLY_DOCKER ;;
            deps)   $ONLY_DEPS ;;
            *)      return 1 ;;
        esac
    fi
}

##############################################################################
# MISE INSTALLATION
##############################################################################

# Безопасная установка mise через официальный скрипт
# (скачать, проверить, выполнить вместо curl | sh)
_install_mise_via_script() {
    local installer
    installer=$(mktemp)
    register_temp_file "$installer"

    log_verbose "Скачивание установщика mise..."
    if ! curl -fsSL "https://mise.run" -o "$installer"; then
        log_error "Не удалось скачать установщик mise"
        return 1
    fi

    chmod +x "$installer"
    log_verbose "Запуск установщика..."
    if ! bash "$installer"; then
        log_error "Установщик mise завершился с ошибкой"
        return 1
    fi

    rm -f "$installer"
    return 0
}

install_mise() {
    log_step "Установка mise..."

    if command -v mise &>/dev/null; then
        local current_version=$(mise --version 2>/dev/null | head -1)
        log_success "mise уже установлен: $current_version"
        return 0
    fi

    if $DRY_RUN; then
        log_info "[DRY-RUN] Будет установлен mise"
        return 0
    fi

    local platform=$(detect_platform)
    log_info "Платформа: $platform"

    case "$platform" in
        linux-pacman|wsl-pacman)
            log_info "Установка mise через pacman..."
            sudo pacman -Syu --noconfirm --needed mise
            ;;
        linux-apt|wsl-apt)
            log_info "Установка mise через apt (официальный репозиторий)..."
            sudo install -dm 755 /etc/apt/keyrings
            wget -qO - https://mise.jdx.dev/gpg-key.pub | \
                gpg --dearmor | sudo tee /etc/apt/keyrings/mise-archive-keyring.gpg >/dev/null
            echo "deb [signed-by=/etc/apt/keyrings/mise-archive-keyring.gpg arch=amd64] https://mise.jdx.dev/deb stable main" | \
                sudo tee /etc/apt/sources.list.d/mise.list >/dev/null
            sudo apt update && sudo apt install -y mise
            ;;
        linux-dnf)
            log_info "Установка mise через dnf..."
            sudo dnf install -y dnf-plugins-core
            sudo dnf config-manager --add-repo https://mise.jdx.dev/rpm/mise.repo
            sudo dnf install -y mise
            ;;
        macos)
            if command -v brew &>/dev/null; then
                log_info "Установка mise через Homebrew..."
                brew install mise
            else
                log_info "Установка mise через официальный скрипт..."
                _install_mise_via_script
            fi
            ;;
        *)
            log_info "Установка mise через официальный скрипт..."
            _install_mise_via_script
            ;;
    esac

    # Проверка установки
    if command -v mise &>/dev/null; then
        log_success "mise установлен: $(mise --version | head -1)"
    else
        # mise может быть установлен в ~/.local/bin
        if [[ -x "$HOME/.local/bin/mise" ]]; then
            export PATH="$HOME/.local/bin:$PATH"
            log_success "mise установлен в ~/.local/bin: $(mise --version | head -1)"
        else
            log_error "Не удалось установить mise"
            return 1
        fi
    fi
}

activate_mise_in_shell() {
    log_step "Активация mise в shell..."

    local shell_name=$(basename "$SHELL")
    local shell_rc=""

    case "$shell_name" in
        bash) shell_rc="$HOME/.bashrc" ;;
        zsh)  shell_rc="$HOME/.zshrc" ;;
        fish) shell_rc="$HOME/.config/fish/config.fish" ;;
        *)    shell_rc="$HOME/.profile" ;;
    esac

    if $DRY_RUN; then
        log_info "[DRY-RUN] Будет добавлена активация mise в $shell_rc"
        return 0
    fi

    # Проверка: уже активирован?
    if grep -q "mise activate" "$shell_rc" 2>/dev/null; then
        log_info "mise уже активирован в $shell_rc"
        return 0
    fi

    # Добавление активации
    echo '' >> "$shell_rc"
    echo '# mise - runtime version manager (added by setup script)' >> "$shell_rc"

    case "$shell_name" in
        fish)
            echo 'mise activate fish | source' >> "$shell_rc"
            ;;
        *)
            echo "eval \"\$(mise activate $shell_name)\"" >> "$shell_rc"
            ;;
    esac

    log_success "mise активирован в $shell_rc"
    log_warning "Выполните: source $shell_rc (или перезапустите терминал)"
}

##############################################################################
# RUNTIME INSTALLATION (via mise)
##############################################################################

install_runtimes() {
    log_step "Установка runtime'ов через mise..."

    cd "$PROJECT_ROOT"

    if $DRY_RUN; then
        log_info "[DRY-RUN] Будут установлены runtime'ы из .tool-versions:"
        cat "$PROJECT_ROOT/.tool-versions" | grep -v '^#' | grep -v '^$'
        return 0
    fi

    # Активировать mise для текущей сессии
    eval "$(mise activate bash 2>/dev/null)" || true

    # Trust конфигурации проекта (убирает интерактивный prompt)
    mise trust --all 2>/dev/null || true

    # Установка всех инструментов из .tool-versions
    log_info "Установка инструментов из .tool-versions..."
    mise install --yes

    # Создать shims для всех инструментов
    log_info "Создание shims..."
    mise reshim

    # Добавить shims в PATH для текущей сессии
    export PATH="$HOME/.local/share/mise/shims:$PATH"

    # Установка Go инструментов для разработки
    log_info "Установка Go инструментов (oapi-codegen)..."
    if command -v go &>/dev/null; then
        go install github.com/oapi-codegen/oapi-codegen/v2/cmd/oapi-codegen@latest 2>/dev/null || true
    fi

    # Вывод установленных версий
    echo ""
    log_info "Установленные версии:"
    mise current
}

##############################################################################
# DOCKER INSTALLATION
##############################################################################

install_docker() {
    log_step "Установка Docker..."

    # Загрузить Docker-специфичный модуль
    if [[ -f "$SCRIPT_DIR/lib/docker.sh" ]]; then
        source "$SCRIPT_DIR/lib/docker.sh"
        _install_docker_for_platform
    else
        log_error "Модуль lib/docker.sh не найден"
        return 1
    fi
}

##############################################################################
# PROJECT DEPENDENCIES
##############################################################################

install_project_deps() {
    log_step "Установка зависимостей проекта..."

    if $DRY_RUN; then
        log_info "[DRY-RUN] Будут установлены:"
        log_info "  - Python: pip install -r requirements.txt"
        log_info "  - Node.js: npm ci"
        log_info "  - Go: go mod download для всех сервисов"
        return 0
    fi

    cd "$PROJECT_ROOT"

    # Активировать mise для текущей сессии
    eval "$(mise activate bash 2>/dev/null)" || true

    # Python venv + pip
    if [[ -d "orchestrator" ]]; then
        log_info "Python зависимости..."
        cd orchestrator

        local python_cmd="python"
        command -v python3 &>/dev/null && python_cmd="python3"

        if [[ ! -d "venv" ]]; then
            $python_cmd -m venv venv
        fi

        # Activate script path
        local activate_script="venv/bin/activate"
        [[ -f "venv/Scripts/activate" ]] && activate_script="venv/Scripts/activate"

        source "$activate_script"
        pip install --upgrade pip -q
        pip install -r requirements.txt -q
        deactivate

        log_success "Python зависимости установлены"
        cd "$PROJECT_ROOT"
    fi

    # Node.js npm
    if [[ -d "frontend" && -f "frontend/package.json" ]]; then
        log_info "Node.js зависимости..."
        cd frontend

        if [[ -f "package-lock.json" ]]; then
            npm ci --silent
        else
            npm install --silent
        fi

        log_success "Node.js зависимости установлены"
        cd "$PROJECT_ROOT"
    fi

    # Go modules
    if [[ -d "go-services" ]]; then
        log_info "Go зависимости..."

        for service_dir in go-services/*/; do
            if [[ -f "$service_dir/go.mod" ]]; then
                local service_name=$(basename "$service_dir")
                $VERBOSE && log_info "  go mod download: $service_name"
                (cd "$service_dir" && go mod download 2>/dev/null) || true
            fi
        done

        log_success "Go зависимости загружены"
    fi
}

##############################################################################
# FINAL REPORT
##############################################################################

print_report() {
    echo ""
    echo -e "${BOLD}════════════════════════════════════════════════════════════════${NC}"
    echo -e "${BOLD}  Установка завершена!${NC}"
    echo -e "${BOLD}════════════════════════════════════════════════════════════════${NC}"
    echo ""

    # Версии инструментов
    if command -v mise &>/dev/null; then
        echo "Версии инструментов (mise current):"
        mise current 2>/dev/null || echo "  (выполните source ~/.bashrc для активации mise)"
        echo ""
    fi

    # Docker
    if command -v docker &>/dev/null; then
        echo "Docker: $(docker --version 2>/dev/null || echo 'не доступен')"
        echo "Compose: $(docker compose version 2>/dev/null || echo 'не доступен')"
        echo ""
    fi

    echo "Следующие шаги:"
    echo ""
    echo "  1. Перезапустите терминал или выполните:"
    echo "     source ~/.bashrc  # или ~/.zshrc"
    echo ""
    echo "  2. Запустите инфраструктуру:"
    echo "     docker compose up -d postgres redis"
    echo ""
    echo "  3. Примените миграции:"
    echo "     ./scripts/dev/run-migrations.sh"
    echo ""
    echo "  4. Запустите все сервисы:"
    echo "     ./scripts/dev/start-all.sh"
    echo ""
    echo "  5. Проверьте статус:"
    echo "     ./scripts/dev/health-check.sh"
    echo ""
}

##############################################################################
# MAIN
##############################################################################

main() {
    parse_args "$@"

    # Mode-based execution
    case "$MODE" in
        prepare_offline)
            if [[ -f "$SCRIPT_DIR/lib/offline.sh" ]]; then
                source "$SCRIPT_DIR/lib/offline.sh"
                prepare_offline_bundle \
                    "${OFFLINE_PLATFORM:-linux-amd64}" \
                    "${OFFLINE_BUNDLE_DIR:-$SCRIPT_DIR/offline-bundle}"
            else
                log_error "Модуль lib/offline.sh не найден"
                exit 1
            fi
            exit 0
            ;;
        install_offline)
            if [[ -f "$SCRIPT_DIR/lib/offline.sh" ]]; then
                source "$SCRIPT_DIR/lib/offline.sh"
                install_from_offline_bundle \
                    "${OFFLINE_BUNDLE_DIR:-$SCRIPT_DIR/offline-bundle}"
                # После offline установки продолжаем с активацией shell и т.д.
            else
                log_error "Модуль lib/offline.sh не найден"
                exit 1
            fi
            ;;
    esac

    echo ""
    echo -e "${BOLD}════════════════════════════════════════════════════════════════${NC}"
    echo -e "${BOLD}  CommandCenter1C - Development Environment Setup${NC}"
    echo -e "${BOLD}════════════════════════════════════════════════════════════════${NC}"
    echo ""

    local platform=$(detect_platform)
    log_info "Платформа: $platform"
    log_info "Проект: $PROJECT_ROOT"
    echo ""

    if $DRY_RUN; then
        log_warning "Режим DRY-RUN: изменения НЕ будут применены"
        echo ""
    fi

    # Шаг 1: mise + runtime'ы
    if should_install "mise"; then
        install_mise
        activate_mise_in_shell
        install_runtimes
        echo ""
    fi

    # Шаг 2: Docker
    if should_install "docker"; then
        install_docker
        echo ""
    fi

    # Шаг 3: Зависимости проекта
    if should_install "deps"; then
        install_project_deps
        echo ""
    fi

    # Финальный отчет
    if ! $DRY_RUN; then
        print_report
    fi
}

main "$@"
