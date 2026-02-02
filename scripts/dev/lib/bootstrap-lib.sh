#!/bin/bash

##############################################################################
# CommandCenter1C - Bootstrap Library
##############################################################################
#
# Вспомогательные функции для bootstrap.sh
# Используется через source.
#
# Требования:
#   - PROJECT_ROOT должен быть установлен ДО source
#   - scripts/lib/init.sh должен быть загружен (core, platform, files, services, build)
#
# Version: 1.1.0
##############################################################################

# Предотвращение повторного sourcing
if [[ -n "$BOOTSTRAP_LIB_LOADED" ]]; then
    return 0
fi
BOOTSTRAP_LIB_LOADED=true

# Проверка что PROJECT_ROOT установлен
if [[ -z "${PROJECT_ROOT:-}" ]]; then
    echo "ERROR: PROJECT_ROOT must be set before sourcing bootstrap-lib.sh" >&2
    return 1
fi

##############################################################################
# ФЛАГИ (defaults)
##############################################################################

SKIP_PREREQUISITES=false
SKIP_DEPS=false
SKIP_BUILD=false
SKIP_DOCKER=false
SKIP_MIGRATIONS=false
ONLY_CHECK=false
FORCE=false
FORCE_REBUILD=false
RESET_STATE=false
VERBOSE=false

##############################################################################
# CONSTANTS
##############################################################################

BOOTSTRAP_DIR="${PROJECT_ROOT:-.}/.bootstrap"

# Имена маркеров
MARKER_PREREQUISITES="prerequisites.done"
MARKER_DEPS="deps.done"
MARKER_BUILD="build.done"
MARKER_DOCKER="docker.done"
MARKER_MIGRATIONS="migrations.done"

# Таймауты
POSTGRES_TIMEOUT=30
REDIS_TIMEOUT=30

##############################################################################
# PARSE ARGUMENTS
##############################################################################

parse_bootstrap_args() {
    while [[ $# -gt 0 ]]; do
        case $1 in
            --skip-prerequisites)
                SKIP_PREREQUISITES=true
                shift
                ;;
            --skip-deps)
                SKIP_DEPS=true
                shift
                ;;
            --skip-build)
                SKIP_BUILD=true
                shift
                ;;
            --skip-docker)
                SKIP_DOCKER=true
                shift
                ;;
            --skip-migrations)
                SKIP_MIGRATIONS=true
                shift
                ;;
            --only-check)
                ONLY_CHECK=true
                shift
                ;;
            --force)
                FORCE=true
                shift
                ;;
            --force-rebuild)
                FORCE_REBUILD=true
                shift
                ;;
            --reset)
                RESET_STATE=true
                shift
                ;;
            --verbose|-v)
                VERBOSE=true
                shift
                ;;
            --help|-h)
                show_bootstrap_help
                exit 0
                ;;
            *)
                log_error "Неизвестный параметр: $1"
                show_bootstrap_help
                exit 1
                ;;
        esac
    done
}

show_bootstrap_help() {
    cat << 'EOF'
CommandCenter1C - Bootstrap Script

Полная инициализация окружения разработки: от установки инструментов
до запуска всех сервисов.

Usage:
  ./scripts/dev/bootstrap.sh [OPTIONS]

Options:
  --skip-prerequisites    Пропустить проверку/установку инструментов (mise, Go, Python, Node)
  --skip-deps             Пропустить установку зависимостей (pip, npm, go mod)
  --skip-build            Пропустить сборку Go бинарников
  --skip-docker           Пропустить запуск Docker инфраструктуры
  --skip-migrations       Пропустить миграции Django
  --only-check            Только проверить состояние, не запускать сервисы
  --force                 Принудительно переделать все этапы
  --force-rebuild         Принудительно пересобрать Go сервисы
  --reset                 Сбросить состояние (.bootstrap/)
  --verbose, -v           Подробный вывод
  --help, -h              Показать эту справку

Этапы выполнения:
  1. Prerequisites  - mise + Go/Python/Node/Docker через install.sh
  2. Dependencies   - pip + npm + go mod
  3. Build          - Go бинарники (smart rebuild)
  4. Docker         - PostgreSQL + Redis containers
  5. Migrations     - Django migrate
  6. Services       - start-all.sh --no-rebuild

Состояние хранится в .bootstrap/ (маркеры завершенных этапов).

Examples:
  ./scripts/dev/bootstrap.sh                    # Полная инициализация
  ./scripts/dev/bootstrap.sh --only-check       # Только проверить
  ./scripts/dev/bootstrap.sh --skip-docker      # Без Docker (уже запущен)
  ./scripts/dev/bootstrap.sh --force            # Переделать все
  ./scripts/dev/bootstrap.sh --reset            # Сбросить состояние

EOF
}

##############################################################################
# BOOTSTRAP STATE MANAGEMENT
##############################################################################

# init_bootstrap_dir - создание директории .bootstrap/
init_bootstrap_dir() {
    if [[ ! -d "$BOOTSTRAP_DIR" ]]; then
        mkdir -p "$BOOTSTRAP_DIR"
        log_verbose "Создана директория: $BOOTSTRAP_DIR"
    fi

    # Создать .gitignore если нет
    local gitignore="$BOOTSTRAP_DIR/.gitignore"
    if [[ ! -f "$gitignore" ]]; then
        echo "*" > "$gitignore"
        log_verbose "Создан .gitignore в $BOOTSTRAP_DIR"
    fi

    # Проверка на параллельный запуск через lock file
    local lockfile="$BOOTSTRAP_DIR/.lock"
    if [[ -f "$lockfile" ]]; then
        local lock_pid
        lock_pid=$(cat "$lockfile" 2>/dev/null)
        if [[ -n "$lock_pid" ]] && kill -0 "$lock_pid" 2>/dev/null; then
            log_error "Bootstrap уже запущен (PID: $lock_pid)"
            log_info "Если это ошибка, удалите: $lockfile"
            exit 1
        fi
        # Старый lock file от завершившегося процесса - удаляем
        rm -f "$lockfile"
    fi

    # Записать текущий PID
    echo $$ > "$lockfile"

    # Удалить lock при выходе
    trap 'rm -f "$lockfile" 2>/dev/null' EXIT
}

# is_stage_done - проверка завершенности этапа
# Usage: if is_stage_done "prerequisites"; then ...
is_stage_done() {
    local stage=$1
    local marker="$BOOTSTRAP_DIR/${stage}.done"
    [[ -f "$marker" ]]
}

# mark_stage_done - пометить этап как завершенный
# Usage: mark_stage_done "prerequisites"
mark_stage_done() {
    local stage=$1
    local marker="$BOOTSTRAP_DIR/${stage}.done"
    date +%s > "$marker"
    log_verbose "Этап '$stage' помечен как завершенный"
}

# get_stage_timestamp - получить timestamp завершения этапа
# Usage: ts=$(get_stage_timestamp "deps")
get_stage_timestamp() {
    local stage=$1
    local marker="$BOOTSTRAP_DIR/${stage}.done"

    if [[ -f "$marker" ]]; then
        cat "$marker"
    else
        echo "0"
    fi
}

# should_skip - проверка нужно ли пропустить этап
# Usage: if should_skip "prerequisites"; then ...
should_skip() {
    local stage=$1

    # Принудительный режим - не пропускаем
    if [[ "$FORCE" == "true" ]]; then
        return 1
    fi

    # Проверка флагов пропуска
    case "$stage" in
        prerequisites)
            [[ "$SKIP_PREREQUISITES" == "true" ]] && return 0
            ;;
        deps)
            [[ "$SKIP_DEPS" == "true" ]] && return 0
            ;;
        build)
            [[ "$SKIP_BUILD" == "true" ]] && return 0
            ;;
        docker)
            [[ "$SKIP_DOCKER" == "true" ]] && return 0
            ;;
        migrations)
            [[ "$SKIP_MIGRATIONS" == "true" ]] && return 0
            ;;
    esac

    # Проверка маркера завершенности
    if is_stage_done "$stage"; then
        return 0
    fi

    return 1
}

##############################################################################
# GLOBAL SYMLINKS FOR mise TOOLS
##############################################################################

# setup_global_symlinks - создание симлинков для python/go в /usr/local/bin
# Это нужно для субагентов Claude Code и скриптов, которые не имеют доступа к mise shims
# Usage: setup_global_symlinks
setup_global_symlinks() {
    log_info "Настройка глобальных симлинков для mise tools..."

    local mise_installs_dir="$HOME/.local/share/mise/installs"
    local symlink_dir="/usr/local/bin"
    local created=0
    local skipped=0

    # Определить пути к бинарникам mise
    local python_bin=""
    local python3_bin=""
    local go_bin=""

    # Найти Python
    if [[ -d "$mise_installs_dir/python" ]]; then
        # Найти последнюю версию Python
        local python_version
        python_version=$(ls -1 "$mise_installs_dir/python" 2>/dev/null | sort -V | tail -1)
        if [[ -n "$python_version" ]]; then
            python_bin="$mise_installs_dir/python/$python_version/bin/python"
            python3_bin="$mise_installs_dir/python/$python_version/bin/python3"
        fi
    fi

    # Найти Go
    if [[ -d "$mise_installs_dir/go" ]]; then
        local go_version
        go_version=$(ls -1 "$mise_installs_dir/go" 2>/dev/null | sort -V | tail -1)
        if [[ -n "$go_version" ]]; then
            go_bin="$mise_installs_dir/go/$go_version/bin/go"
        fi
    fi

    # Создать симлинки
    local symlinks_to_create=()

    # Python symlinks
    if [[ -x "$python_bin" ]]; then
        symlinks_to_create+=("python:$python_bin")
    fi
    if [[ -x "$python3_bin" ]]; then
        symlinks_to_create+=("python3:$python3_bin")
    fi

    # Go symlink
    if [[ -x "$go_bin" ]]; then
        symlinks_to_create+=("go:$go_bin")
    fi

    if [[ ${#symlinks_to_create[@]} -eq 0 ]]; then
        log_warning "Не найдены mise installations для создания симлинков"
        return 0
    fi

    # Проверить права на /usr/local/bin
    if [[ ! -w "$symlink_dir" ]]; then
        log_info "Требуются права sudo для создания симлинков в $symlink_dir"
    fi

    for entry in "${symlinks_to_create[@]}"; do
        local name="${entry%%:*}"
        local target="${entry#*:}"
        local symlink_path="$symlink_dir/$name"

        # Проверить существует ли уже симлинк на правильный target
        if [[ -L "$symlink_path" ]]; then
            local current_target
            current_target=$(readlink -f "$symlink_path" 2>/dev/null)
            if [[ "$current_target" == "$target" ]]; then
                log_verbose "Симлинк $name уже существует и актуален"
                ((skipped++))
                continue
            else
                log_info "Обновление симлинка $name: $current_target -> $target"
            fi
        elif [[ -e "$symlink_path" ]]; then
            log_verbose "Пропуск $name: уже существует (не симлинк)"
            ((skipped++))
            continue
        fi

        # Создать симлинк
        if [[ -w "$symlink_dir" ]]; then
            ln -sf "$target" "$symlink_path" && ((created++)) || log_warning "Не удалось создать $symlink_path"
        else
            sudo ln -sf "$target" "$symlink_path" && ((created++)) || log_warning "Не удалось создать $symlink_path"
        fi
    done

    if [[ $created -gt 0 ]]; then
        log_success "Создано симлинков: $created"
    fi
    if [[ $skipped -gt 0 ]]; then
        log_verbose "Пропущено симлинков: $skipped"
    fi
}

# remove_global_symlinks - удаление симлинков из /usr/local/bin
# Usage: remove_global_symlinks
remove_global_symlinks() {
    log_info "Удаление глобальных симлинков..."

    local symlink_dir="/usr/local/bin"
    local mise_installs_dir="$HOME/.local/share/mise/installs"
    local removed=0

    for name in python python3 go; do
        local symlink_path="$symlink_dir/$name"

        if [[ -L "$symlink_path" ]]; then
            local target
            target=$(readlink -f "$symlink_path" 2>/dev/null)

            # Удалять только симлинки, указывающие на mise installs
            if [[ "$target" == "$mise_installs_dir"* ]]; then
                if [[ -w "$symlink_dir" ]]; then
                    rm -f "$symlink_path" && ((removed++))
                else
                    sudo rm -f "$symlink_path" && ((removed++))
                fi
                log_verbose "Удален симлинк: $name"
            fi
        fi
    done

    if [[ $removed -gt 0 ]]; then
        log_success "Удалено симлинков: $removed"
    else
        log_info "Симлинки не найдены"
    fi
}

##############################################################################
# DEPENDENCIES CHECK
##############################################################################

# deps_up_to_date - проверка актуальности зависимостей
# Сравнивает timestamp маркера deps.done с requirements.txt, package.json, go.mod
# Usage: if deps_up_to_date; then echo "deps актуальны"; fi
deps_up_to_date() {
    local marker="$BOOTSTRAP_DIR/deps.done"

    # Если маркера нет - зависимости не установлены
    if [[ ! -f "$marker" ]]; then
        log_verbose "Маркер deps.done не найден"
        return 1
    fi

    local marker_time
    marker_time=$(get_file_mtime "$marker")

    # Проверить requirements.txt
    local requirements="$PROJECT_ROOT/orchestrator/requirements.txt"
    if [[ -f "$requirements" ]]; then
        local req_time
        req_time=$(get_file_mtime "$requirements")
        if [[ "$req_time" -gt "$marker_time" ]]; then
            log_verbose "requirements.txt новее маркера deps.done"
            return 1
        fi
    fi

    # Проверить package.json
    local package_json="$PROJECT_ROOT/frontend/package.json"
    if [[ -f "$package_json" ]]; then
        local pkg_time
        pkg_time=$(get_file_mtime "$package_json")
        if [[ "$pkg_time" -gt "$marker_time" ]]; then
            log_verbose "package.json новее маркера deps.done"
            return 1
        fi
    fi

    # Проверить go.mod файлы
    for service_dir in "$PROJECT_ROOT"/go-services/*/; do
        local go_mod="$service_dir/go.mod"
        if [[ -f "$go_mod" ]]; then
            local mod_time
            mod_time=$(get_file_mtime "$go_mod")
            if [[ "$mod_time" -gt "$marker_time" ]]; then
                log_verbose "$(basename "$service_dir")/go.mod новее маркера deps.done"
                return 1
            fi
        fi
    done

    log_verbose "Все зависимости актуальны"
    return 0
}

##############################################################################
# PREREQUISITES
##############################################################################

# verify_prerequisites - проверка наличия необходимых инструментов
# Usage: if verify_prerequisites; then echo "все ок"; fi
verify_prerequisites() {
    local missing=()

    # mise
    if ! command -v mise &>/dev/null && [[ ! -x "$HOME/.local/bin/mise" ]]; then
        missing+=("mise")
    fi

    # Go
    if ! command -v go &>/dev/null; then
        missing+=("go")
    fi

    # Python
    if ! command -v python &>/dev/null && ! command -v python3 &>/dev/null; then
        missing+=("python")
    fi

    # Node.js
    if ! command -v node &>/dev/null; then
        missing+=("node")
    fi

    # Docker
    if ! command -v docker &>/dev/null; then
        missing+=("docker")
    fi

    if [[ ${#missing[@]} -gt 0 ]]; then
        log_warning "Отсутствуют инструменты: ${missing[*]}"
        return 1
    fi

    return 0
}

##############################################################################
# ENVIRONMENT SETUP
##############################################################################

# ensure_env_local - проверка и создание .env.local
# Копирует .env.local.example если .env.local не существует
# Генерирует DB_ENCRYPTION_KEY если не установлен
ensure_env_local() {
    local env_file="$PROJECT_ROOT/.env.local"
    local env_example="$PROJECT_ROOT/.env.local.example"

    # Создать .env.local из примера если не существует
    if [[ ! -f "$env_file" ]]; then
        if [[ -f "$env_example" ]]; then
            log_info "Создание .env.local из .env.local.example..."
            cp "$env_example" "$env_file"
        else
            log_error ".env.local.example не найден"
            return 1
        fi
    fi

    # Проверить и сгенерировать DB_ENCRYPTION_KEY
    local current_key
    current_key=$(grep -E "^DB_ENCRYPTION_KEY=" "$env_file" 2>/dev/null | cut -d'=' -f2-)

    if [[ -z "$current_key" ]] || [[ "$current_key" == "your-generated-key-here" ]]; then
        log_info "Генерация ключа шифрования DB_ENCRYPTION_KEY..."

        local new_key
        # Попробовать использовать Python с cryptography
        if command -v python3 &>/dev/null; then
            new_key=$(python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())" 2>/dev/null)
        elif command -v python &>/dev/null; then
            new_key=$(python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())" 2>/dev/null)
        fi

        # Fallback: openssl
        if [[ -z "$new_key" ]] && command -v openssl &>/dev/null; then
            new_key=$(openssl rand -base64 32 | tr '+/' '-_')
        fi

        if [[ -z "$new_key" ]]; then
            log_error "Не удалось сгенерировать ключ шифрования"
            log_info "Установите вручную: DB_ENCRYPTION_KEY в .env.local"
            return 1
        fi

        # Заменить placeholder или добавить ключ
        if grep -q "^DB_ENCRYPTION_KEY=" "$env_file" 2>/dev/null; then
            # Используем sed с другим разделителем из-за base64 символов
            sed -i "s|^DB_ENCRYPTION_KEY=.*|DB_ENCRYPTION_KEY=$new_key|" "$env_file"
        else
            echo "DB_ENCRYPTION_KEY=$new_key" >> "$env_file"
        fi

        log_success "Ключ шифрования сгенерирован"
    else
        log_verbose "DB_ENCRYPTION_KEY уже установлен"
    fi

    # Проверить и сгенерировать CREDENTIALS_TRANSPORT_KEY (для Worker)
    local transport_key
    transport_key=$(grep -E "^CREDENTIALS_TRANSPORT_KEY=" "$env_file" 2>/dev/null | cut -d'=' -f2-)

    # Формат: 64+ hex chars (32+ bytes), т.к. Go Worker ожидает hex-encoded AES-256 key
    local transport_key_is_valid_hex=true
    if [[ -z "$transport_key" ]] || [[ "$transport_key" == "your-32-byte-key-here-change-me!" ]] || [[ "$transport_key" == "your-64-hex-chars-key-here-change-me!" ]]; then
        transport_key_is_valid_hex=false
    elif [[ ! "$transport_key" =~ ^[0-9a-fA-F]+$ ]]; then
        transport_key_is_valid_hex=false
    elif (( ${#transport_key} < 64 )); then
        transport_key_is_valid_hex=false
    elif (( ${#transport_key} % 2 != 0 )); then
        transport_key_is_valid_hex=false
    fi

    if [[ "$transport_key_is_valid_hex" != "true" ]]; then
        log_info "Генерация ключа CREDENTIALS_TRANSPORT_KEY..."

        local new_transport_key
        if command -v openssl &>/dev/null; then
            new_transport_key=$(openssl rand -hex 32)
        else
            # Fallback: использовать /dev/urandom (hex)
            if command -v xxd &>/dev/null; then
                new_transport_key=$(head -c 32 /dev/urandom | xxd -p -c 256 | tr -d '\n')
            else
                new_transport_key=$(od -An -tx1 -N32 /dev/urandom | tr -d ' \n')
            fi
        fi

        if [[ -z "$new_transport_key" ]]; then
            log_error "Не удалось сгенерировать CREDENTIALS_TRANSPORT_KEY"
            return 1
        fi

        # Заменить placeholder или добавить ключ
        if grep -q "^CREDENTIALS_TRANSPORT_KEY=" "$env_file" 2>/dev/null; then
            sed -i "s|^CREDENTIALS_TRANSPORT_KEY=.*|CREDENTIALS_TRANSPORT_KEY=$new_transport_key|" "$env_file"
        else
            echo "CREDENTIALS_TRANSPORT_KEY=$new_transport_key" >> "$env_file"
        fi

        log_success "CREDENTIALS_TRANSPORT_KEY сгенерирован"
    else
        log_verbose "CREDENTIALS_TRANSPORT_KEY уже установлен"
    fi

    # Настроить PLATFORM_1C_BIN_PATH в зависимости от платформы
    local platform_path
    platform_path=$(grep -E "^PLATFORM_1C_BIN_PATH=" "$env_file" 2>/dev/null | cut -d'=' -f2- | tr -d '"')

    # Проверяем, нужно ли обновить путь (placeholder или неправильный формат для платформы)
    local needs_update=false
    local default_path=""

    if is_wsl; then
        # WSL: путь должен быть в формате /mnt/c/...
        default_path="/mnt/c/Program Files/1cv8/8.3.27.1786/bin"
        if [[ "$platform_path" == "C:\\"* ]] || [[ "$platform_path" == "C:/"* ]] || [[ -z "$platform_path" ]]; then
            needs_update=true
        fi
    else
        # Native Windows (Git Bash / MSYS2): путь в формате C:\...
        default_path="C:\\Program Files\\1cv8\\8.3.27.1786\\bin"
        if [[ "$platform_path" == "/mnt/"* ]] || [[ -z "$platform_path" ]]; then
            needs_update=true
        fi
    fi

    if [[ "$needs_update" == "true" ]]; then
        log_info "Настройка PLATFORM_1C_BIN_PATH для $(detect_platform)..."

        if grep -q "^PLATFORM_1C_BIN_PATH=" "$env_file" 2>/dev/null; then
            sed -i "s|^PLATFORM_1C_BIN_PATH=.*|PLATFORM_1C_BIN_PATH=\"$default_path\"|" "$env_file"
        else
            echo "PLATFORM_1C_BIN_PATH=\"$default_path\"" >> "$env_file"
        fi

        log_success "PLATFORM_1C_BIN_PATH установлен: $default_path"
        log_info "Проверьте версию платформы 1С и измените путь при необходимости"
    else
        log_verbose "PLATFORM_1C_BIN_PATH уже настроен: $platform_path"
    fi

    return 0
}

##############################################################################
# DEPENDENCIES INSTALLATION
##############################################################################

# install_python_deps - установка Python зависимостей
install_python_deps() {
    local orchestrator_dir="$PROJECT_ROOT/orchestrator"

    if [[ ! -d "$orchestrator_dir" ]]; then
        log_warning "Директория orchestrator не найдена"
        return 0
    fi

    local python_cmd="python"
    command -v python3 &>/dev/null && python_cmd="python3"

    # Создать venv если нет
    if [[ ! -d "$orchestrator_dir/venv" ]]; then
        log_info "Создание виртуального окружения Python..."
        (cd "$orchestrator_dir" && $python_cmd -m venv venv)
    fi

    log_info "Установка Python зависимостей (может занять 2-5 минут)..."
    show_spinner "pip install requirements.txt"

    # Используем subshell для изоляции cd и venv
    (
        cd "$orchestrator_dir" || exit 1

        # Активировать venv и установить зависимости
        # shellcheck source=/dev/null
        source "venv/$VENV_BIN_DIR/activate" || exit 1

        pip install --upgrade pip -q
        pip install -r requirements.txt -q

        # Установка инструментов для генерации API клиентов
        pip install openapi-python-client -q 2>/dev/null || true

        deactivate 2>/dev/null || true
    )

    local result=$?
    hide_spinner "success"

    if [[ $result -eq 0 ]]; then
        log_success "Python зависимости установлены"
    else
        log_error "Ошибка установки Python зависимостей"
        return 1
    fi
}

# install_node_deps - установка Node.js зависимостей
install_node_deps() {
    local frontend_dir="$PROJECT_ROOT/frontend"

    if [[ ! -d "$frontend_dir" ]] || [[ ! -f "$frontend_dir/package.json" ]]; then
        log_warning "Frontend директория или package.json не найдены"
        return 0
    fi

    log_info "Установка Node.js зависимостей (может занять 1-2 минуты)..."

    show_spinner "npm install"
    # Используем subshell для изоляции cd
    (
        cd "$frontend_dir" || exit 1

        if [[ -f "package-lock.json" ]]; then
            npm ci --silent
        else
            npm install --silent
        fi
    )
    local npm_result=$?
    hide_spinner "success"

    if [[ $npm_result -eq 0 ]]; then
        log_success "Node.js зависимости установлены"
        if command -v npx &>/dev/null; then
            log_info "Установка браузеров Playwright..."
            if (cd "$frontend_dir" && npx playwright install >/dev/null 2>&1); then
                log_success "Playwright браузеры установлены"
            else
                log_warning "Не удалось установить Playwright браузеры"
            fi
        else
            log_warning "npx не найден, пропуск установки Playwright браузеров"
        fi
    else
        log_error "Ошибка установки Node.js зависимостей"
        return 1
    fi
}

# install_go_deps - загрузка Go зависимостей
install_go_deps() {
    local go_services_dir="$PROJECT_ROOT/go-services"

    if [[ ! -d "$go_services_dir" ]]; then
        log_warning "Директория go-services не найдена"
        return 0
    fi

    log_info "Загрузка Go зависимостей..."

    for service_dir in "$go_services_dir"/*/; do
        if [[ -f "$service_dir/go.mod" ]]; then
            local service_name
            service_name=$(basename "$service_dir")
            log_verbose "  go mod download: $service_name"
            (cd "$service_dir" && go mod download 2>/dev/null) || true
        fi
    done

    log_success "Go зависимости загружены"

    # Установка Go инструментов для разработки
    install_go_tools
}

# install_go_tools - установка Go инструментов (oapi-codegen, etc.)
install_go_tools() {
    log_info "Проверка Go инструментов..."

    # oapi-codegen - генерация кода из OpenAPI спецификаций
    if ! command -v oapi-codegen &>/dev/null; then
        log_info "Установка oapi-codegen..."
        if go install github.com/oapi-codegen/oapi-codegen/v2/cmd/oapi-codegen@latest 2>/dev/null; then
            log_success "oapi-codegen установлен"
        else
            log_warning "Не удалось установить oapi-codegen"
        fi
    else
        log_verbose "oapi-codegen уже установлен"
    fi
}

##############################################################################
# DOCKER INFRASTRUCTURE
##############################################################################

# start_docker_infrastructure - запуск PostgreSQL и Redis
start_docker_infrastructure() {
    log_info "Запуск Docker инфраструктуры (PostgreSQL, Redis)..."

    # Проверить docker-compose.yml
    if [[ ! -f "$PROJECT_ROOT/docker-compose.yml" ]]; then
        log_error "docker-compose.yml не найден"
        return 1
    fi

    # Проверить что Docker запущен
    if ! docker info &>/dev/null 2>&1; then
        log_error "Docker daemon не запущен"
        return 1
    fi

    # Запустить только postgres и redis (используем subshell)
    (
        cd "$PROJECT_ROOT" || exit 1
        docker compose up -d postgres redis
    )

    if [[ $? -ne 0 ]]; then
        log_error "Не удалось запустить Docker контейнеры"
        return 1
    fi

    # Ожидать готовности
    if ! wait_for_postgres; then
        log_error "PostgreSQL не запустился в течение $POSTGRES_TIMEOUT секунд"
        return 1
    fi

    if ! wait_for_redis; then
        log_error "Redis не запустился в течение $REDIS_TIMEOUT секунд"
        return 1
    fi

    log_success "Docker инфраструктура запущена"
}

# wait_for_postgres - ожидание готовности PostgreSQL
wait_for_postgres() {
    log_info "Ожидание готовности PostgreSQL..."

    # Получить имя пользователя из .env.local или использовать default
    local pg_user="${POSTGRES_USER:-commandcenter}"

    local count=0
    while [[ $count -lt $POSTGRES_TIMEOUT ]]; do
        if (cd "$PROJECT_ROOT" && docker compose exec -T postgres pg_isready -U "$pg_user" &>/dev/null); then
            log_success "PostgreSQL готов"
            return 0
        fi
        ((count++))
        sleep 1
    done

    return 1
}

# wait_for_redis - ожидание готовности Redis
wait_for_redis() {
    log_info "Ожидание готовности Redis..."

    local count=0
    while [[ $count -lt $REDIS_TIMEOUT ]]; do
        if (cd "$PROJECT_ROOT" && docker compose exec -T redis redis-cli ping &>/dev/null); then
            log_success "Redis готов"
            return 0
        fi
        ((count++))
        sleep 1
    done

    return 1
}

##############################################################################
# DJANGO MIGRATIONS
##############################################################################

# run_django_migrations - применение миграций Django
run_django_migrations() {
    local orchestrator_dir="$PROJECT_ROOT/orchestrator"

    if [[ ! -d "$orchestrator_dir" ]]; then
        log_warning "Директория orchestrator не найдена"
        return 0
    fi

    log_info "Применение миграций Django..."

    # Используем subshell для изоляции cd и venv
    # Важно: subshell возвращает exit code последней команды
    (
        cd "$orchestrator_dir" || exit 1

        # Активировать venv
        if [[ -d "venv" ]]; then
            # shellcheck source=/dev/null
            source "venv/$VENV_BIN_DIR/activate" || exit 1
        fi

        # Выполнить миграции и сохранить результат
        python manage.py migrate --noinput
        migrate_result=$?

        if [[ $migrate_result -eq 0 ]]; then
            # Собрать статические файлы (требуется для Daphne/ASGI с whitenoise)
            python manage.py collectstatic --noinput -v 0
            migrate_result=$?
        fi

        deactivate 2>/dev/null || true

        # Явно вернуть результат миграции
        exit $migrate_result
    )

    local result=$?
    if [[ $result -eq 0 ]]; then
        log_success "Миграции и статика применены"
    else
        log_error "Ошибка применения миграций/статики (код: $result)"
        return 1
    fi

    # Создать суперпользователя если не существует
    create_django_superuser
}

# create_django_superuser - создание суперпользователя Django
# Использует переменные окружения или значения по умолчанию
create_django_superuser() {
    local orchestrator_dir="$PROJECT_ROOT/orchestrator"

    # Значения по умолчанию для разработки
    local admin_user="${DJANGO_SUPERUSER_USERNAME:-admin}"
    local admin_email="${DJANGO_SUPERUSER_EMAIL:-admin@localhost}"
    local admin_pass="${DJANGO_SUPERUSER_PASSWORD:-p-123456}"

    log_info "Проверка суперпользователя Django..."

    # Проверить существует ли пользователь
    local user_exists
    user_exists=$(
        cd "$orchestrator_dir" 2>/dev/null || exit 1
        source "venv/$VENV_BIN_DIR/activate" 2>/dev/null || true
        python -c "
import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.development')
import django
django.setup()
from django.contrib.auth import get_user_model
User = get_user_model()
print('yes' if User.objects.filter(username='$admin_user').exists() else 'no')
" 2>/dev/null
        deactivate 2>/dev/null || true
    )

    if [[ "$user_exists" == "yes" ]]; then
        log_info "Суперпользователь '$admin_user' уже существует"
        return 0
    fi

    # Создать суперпользователя
    log_info "Создание суперпользователя '$admin_user'..."

    local create_result
    create_result=$(
        cd "$orchestrator_dir" 2>/dev/null || exit 1
        source "venv/$VENV_BIN_DIR/activate" 2>/dev/null || true
        DJANGO_SUPERUSER_PASSWORD="$admin_pass" python manage.py createsuperuser \
            --noinput \
            --username "$admin_user" \
            --email "$admin_email" 2>&1 && echo "OK" || echo "FAIL"
        deactivate 2>/dev/null || true
    )

    if [[ "$create_result" == *"OK"* ]]; then
        log_success "Суперпользователь создан: $admin_user / $admin_pass"
    else
        log_warning "Не удалось создать суперпользователя: $create_result"
    fi
}

##############################################################################
# REPORT
##############################################################################

# print_bootstrap_report - итоговый отчет
print_bootstrap_report() {
    echo ""
    echo -e "${BOLD}================================================================${NC}"
    echo -e "${BOLD}  Bootstrap завершен!${NC}"
    echo -e "${BOLD}================================================================${NC}"
    echo ""

    # Статус этапов
    echo -e "${BLUE}Статус этапов:${NC}"

    local stages=("prerequisites" "deps" "build" "docker" "migrations")
    local labels=("Prerequisites" "Dependencies" "Build" "Docker" "Migrations")

    for i in "${!stages[@]}"; do
        local stage="${stages[$i]}"
        local label="${labels[$i]}"

        if is_stage_done "$stage"; then
            echo -e "  ${GREEN}[OK]${NC} $label"
        else
            echo -e "  ${YELLOW}[--]${NC} $label"
        fi
    done

    echo ""

    if [[ "$ONLY_CHECK" == "true" ]]; then
        echo -e "${YELLOW}Режим --only-check: сервисы не запущены${NC}"
        echo ""
        echo "Для запуска сервисов выполните:"
        echo "  ./scripts/dev/start-all.sh --no-rebuild"
    else
        echo -e "${GREEN}Все сервисы должны быть запущены!${NC}"
        echo ""
        echo "Проверить статус:"
        echo "  ./scripts/dev/health-check.sh"
        echo ""
        echo "Доступные endpoints:"
        echo "  Frontend:      http://localhost:15173"
        echo "  API Gateway:   http://localhost:8180/health"
        echo "  Orchestrator:  http://localhost:8200/api/docs"
    fi

    echo ""
}

##############################################################################
# End of bootstrap-lib.sh
##############################################################################
