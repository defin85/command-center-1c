#!/bin/bash

##############################################################################
# CommandCenter1C - Development Environment Uninstaller
##############################################################################
#
# Удаляет компоненты окружения разработки, установленные install.sh
#
# Usage:
#   ./scripts/setup/uninstall.sh [OPTIONS]
#
# Options:
#   --all                 Удалить всё (mise, Docker, зависимости)
#   --only-mise           Только mise и runtime'ы
#   --only-deps           Только зависимости проекта (venv, node_modules)
#   --only-docker         Только Docker
#   --keep-docker         Удалить всё КРОМЕ Docker (default если нет флагов)
#   --dry-run             Показать что будет удалено
#   --force               Без подтверждения
#   --backup              Создать backup конфигурации перед удалением
#   --remove-volumes      Также удалить Docker volumes (требует подтверждения)
#   --verbose, -v         Подробный вывод
#   --help, -h            Справка
#
# Examples:
#   ./scripts/setup/uninstall.sh                   # Удалить всё кроме Docker
#   ./scripts/setup/uninstall.sh --all             # Удалить полностью всё
#   ./scripts/setup/uninstall.sh --dry-run         # Показать план удаления
#   ./scripts/setup/uninstall.sh --only-deps       # Только venv и node_modules
#   ./scripts/setup/uninstall.sh --backup --all    # Backup + полное удаление
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

# Загрузка общих функций (с проверкой)
if [[ -f "$SCRIPT_DIR/lib/common.sh" ]]; then
    source "$SCRIPT_DIR/lib/common.sh"
else
    echo "FATAL: lib/common.sh не найден в $SCRIPT_DIR/lib/" >&2
    exit 1
fi

##############################################################################
# CLI ARGUMENTS
##############################################################################

DRY_RUN=false
VERBOSE=false
FORCE=false
BACKUP=false
REMOVE_VOLUMES=false

# Режимы удаления
REMOVE_ALL=false
ONLY_MISE=false
ONLY_DEPS=false
ONLY_DOCKER=false
KEEP_DOCKER=false

parse_args() {
    while [[ $# -gt 0 ]]; do
        case $1 in
            --all)            REMOVE_ALL=true; shift ;;
            --only-mise)      ONLY_MISE=true; shift ;;
            --only-deps)      ONLY_DEPS=true; shift ;;
            --only-docker)    ONLY_DOCKER=true; shift ;;
            --keep-docker)    KEEP_DOCKER=true; shift ;;
            --dry-run)        DRY_RUN=true; shift ;;
            --force)          FORCE=true; shift ;;
            --backup)         BACKUP=true; shift ;;
            --remove-volumes) REMOVE_VOLUMES=true; shift ;;
            --verbose|-v)     VERBOSE=true; shift ;;
            --help|-h)        show_help; exit 0 ;;
            *)
                log_error "Неизвестный параметр: $1"
                show_help
                exit 1
                ;;
        esac
    done

    # Валидация конфликтующих флагов
    validate_flags

    # Если нет явных флагов - default: keep-docker
    if ! $REMOVE_ALL && ! $ONLY_MISE && ! $ONLY_DEPS && ! $ONLY_DOCKER; then
        KEEP_DOCKER=true
    fi
}

validate_flags() {
    # Проверка конфликтов --all и --only-X
    if [[ "$REMOVE_ALL" == "true" ]]; then
        if [[ "$ONLY_MISE" == "true" || "$ONLY_DEPS" == "true" || "$ONLY_DOCKER" == "true" || "$KEEP_DOCKER" == "true" ]]; then
            log_error "Конфликтующие флаги: --all нельзя использовать с --only-X или --keep-docker"
            exit 1
        fi
    fi

    # Проверка множественных --only-X флагов
    local only_count=0
    [[ "$ONLY_MISE" == "true" ]] && only_count=$((only_count + 1))
    [[ "$ONLY_DEPS" == "true" ]] && only_count=$((only_count + 1))
    [[ "$ONLY_DOCKER" == "true" ]] && only_count=$((only_count + 1))

    if [[ $only_count -gt 1 ]]; then
        log_error "Можно указать только один --only-X флаг"
        exit 1
    fi

    # Проверка конфликта --keep-docker и --only-X
    if [[ "$KEEP_DOCKER" == "true" ]]; then
        if [[ "$ONLY_MISE" == "true" || "$ONLY_DEPS" == "true" || "$ONLY_DOCKER" == "true" ]]; then
            log_error "Конфликтующие флаги: --keep-docker нельзя использовать с --only-X"
            exit 1
        fi
    fi
}

show_help() {
    cat << 'EOF'
CommandCenter1C - Development Environment Uninstaller

Usage:
  ./scripts/setup/uninstall.sh [OPTIONS]

Options:
  --all                 Удалить всё (mise, Docker, зависимости)
  --only-mise           Только mise и runtime'ы
  --only-deps           Только зависимости проекта (venv, node_modules)
  --only-docker         Только Docker
  --keep-docker         Удалить всё КРОМЕ Docker (default если нет флагов)
  --dry-run             Показать что будет удалено (без изменений)
  --force               Без подтверждения
  --backup              Создать backup конфигурации перед удалением
  --remove-volumes      Также удалить Docker volumes (требует подтверждения)
  --verbose, -v         Подробный вывод
  --help, -h            Показать эту справку

Порядок удаления (от безопасного к опасному):
  1. Project dependencies (venv, node_modules) - безопасно
  2. mise runtimes - восстанавливается через mise install
  3. mise itself + shell config - требует переустановки
  4. Docker - критично, может затронуть другие проекты

Examples:
  ./scripts/setup/uninstall.sh                   # Удалить всё кроме Docker
  ./scripts/setup/uninstall.sh --all             # Удалить полностью всё
  ./scripts/setup/uninstall.sh --dry-run         # Показать план удаления
  ./scripts/setup/uninstall.sh --only-deps       # Только venv и node_modules
  ./scripts/setup/uninstall.sh --backup --all    # Backup + полное удаление
EOF
}

##############################################################################
# COMPONENT DETECTION
##############################################################################

declare -A INSTALLED_COMPONENTS
declare -A COMPONENT_SIZES

detect_installed_components() {
    log_step "Определение установленных компонентов..."

    # Python venv
    if has_python_venv; then
        INSTALLED_COMPONENTS[venv]=true
        COMPONENT_SIZES[venv]=$(get_dir_size "$PROJECT_ROOT/orchestrator/venv")
        log_verbose "  venv: $(get_dir_size_human "$PROJECT_ROOT/orchestrator/venv")"
    fi

    # Node modules
    if has_node_modules; then
        INSTALLED_COMPONENTS[node_modules]=true
        COMPONENT_SIZES[node_modules]=$(get_dir_size "$PROJECT_ROOT/frontend/node_modules")
        log_verbose "  node_modules: $(get_dir_size_human "$PROJECT_ROOT/frontend/node_modules")"
    fi

    # Go modules cache (global)
    local go_mod_cache="$HOME/go/pkg/mod"
    if [[ -d "$go_mod_cache" ]] && [[ -n "$(ls -A "$go_mod_cache" 2>/dev/null)" ]]; then
        INSTALLED_COMPONENTS[go_modules]=true
        COMPONENT_SIZES[go_modules]=$(get_dir_size "$go_mod_cache")
        log_verbose "  go_modules: $(get_dir_size_human "$go_mod_cache")"
    fi

    # mise
    if is_mise_installed; then
        INSTALLED_COMPONENTS[mise]=true

        local mise_data=$(get_mise_data_dir)
        if [[ -n "$mise_data" && -d "$mise_data" ]]; then
            COMPONENT_SIZES[mise]=$(get_dir_size "$mise_data")
            log_verbose "  mise: $(get_dir_size_human "$mise_data")"
        fi
    fi

    # mise runtimes (installs directory)
    local mise_data=$(get_mise_data_dir)
    if [[ -n "$mise_data" && -d "$mise_data/installs" ]]; then
        INSTALLED_COMPONENTS[mise_runtimes]=true
        COMPONENT_SIZES[mise_runtimes]=$(get_dir_size "$mise_data/installs")
        log_verbose "  mise_runtimes: $(get_dir_size_human "$mise_data/installs")"
    fi

    # Docker
    if is_docker_installed; then
        INSTALLED_COMPONENTS[docker]=true
        # Docker size сложно определить точно
        COMPONENT_SIZES[docker]=0
        log_verbose "  docker: установлен"
    fi

    # Docker volumes для проекта
    if is_docker_running; then
        local project_volumes=$(docker volume ls -q --filter "name=command-center" 2>/dev/null | wc -l)
        if [[ $project_volumes -gt 0 ]]; then
            INSTALLED_COMPONENTS[docker_volumes]=true
            log_verbose "  docker_volumes: $project_volumes volumes"
        fi
    fi

    echo ""
}

##############################################################################
# REMOVAL PLAN
##############################################################################

should_remove() {
    local component=$1

    case $component in
        venv|node_modules|go_modules)
            $REMOVE_ALL || $ONLY_DEPS || $KEEP_DOCKER
            ;;
        mise|mise_runtimes)
            $REMOVE_ALL || $ONLY_MISE || $KEEP_DOCKER
            ;;
        docker|docker_volumes)
            $REMOVE_ALL || $ONLY_DOCKER
            ;;
        *)
            return 1
            ;;
    esac
}

show_removal_plan() {
    echo ""
    echo -e "${BOLD}План удаления:${NC}"
    echo ""

    local total_size=0
    local has_items=false

    # 1. Project dependencies
    if should_remove "venv" && [[ "${INSTALLED_COMPONENTS[venv]:-}" == "true" ]]; then
        echo -e "  ${CYAN}[1]${NC} Python venv          $(format_size ${COMPONENT_SIZES[venv]:-0})"
        total_size=$((total_size + ${COMPONENT_SIZES[venv]:-0}))
        has_items=true
    fi

    if should_remove "node_modules" && [[ "${INSTALLED_COMPONENTS[node_modules]:-}" == "true" ]]; then
        echo -e "  ${CYAN}[2]${NC} Node modules         $(format_size ${COMPONENT_SIZES[node_modules]:-0})"
        total_size=$((total_size + ${COMPONENT_SIZES[node_modules]:-0}))
        has_items=true
    fi

    if should_remove "go_modules" && [[ "${INSTALLED_COMPONENTS[go_modules]:-}" == "true" ]]; then
        echo -e "  ${CYAN}[3]${NC} Go modules cache     $(format_size ${COMPONENT_SIZES[go_modules]:-0})"
        total_size=$((total_size + ${COMPONENT_SIZES[go_modules]:-0}))
        has_items=true
    fi

    # 2. mise
    if should_remove "mise_runtimes" && [[ "${INSTALLED_COMPONENTS[mise_runtimes]:-}" == "true" ]]; then
        echo -e "  ${CYAN}[4]${NC} mise runtimes        $(format_size ${COMPONENT_SIZES[mise_runtimes]:-0})"
        total_size=$((total_size + ${COMPONENT_SIZES[mise_runtimes]:-0}))
        has_items=true
    fi

    if should_remove "mise" && [[ "${INSTALLED_COMPONENTS[mise]:-}" == "true" ]]; then
        echo -e "  ${CYAN}[5]${NC} mise + shell config  $(format_size ${COMPONENT_SIZES[mise]:-0})"
        total_size=$((total_size + ${COMPONENT_SIZES[mise]:-0}))
        has_items=true
    fi

    # 3. Docker (последний, с предупреждением)
    if should_remove "docker" && [[ "${INSTALLED_COMPONENTS[docker]:-}" == "true" ]]; then
        echo -e "  ${RED}[6]${NC} Docker               ${YELLOW}(системный компонент)${NC}"
        has_items=true

        if $REMOVE_VOLUMES && [[ "${INSTALLED_COMPONENTS[docker_volumes]:-}" == "true" ]]; then
            echo -e "  ${RED}[7]${NC} Docker volumes       ${YELLOW}(ДАННЫЕ БУДУТ ПОТЕРЯНЫ!)${NC}"
        fi
    fi

    if ! $has_items; then
        echo "  (нечего удалять)"
        return 1
    fi

    echo ""
    echo -e "  ${BOLD}Итого:${NC} $(format_size $total_size) будет освобождено"
    echo ""

    return 0
}

##############################################################################
# BACKUP
##############################################################################

create_backup() {
    log_step "Создание backup..."

    local backup_dir=$(create_backup_dir "uninstall")
    log_info "Директория backup: $backup_dir"

    # Backup shell configs
    local shell_config
    shell_config=$(get_shell_config)
    if [[ -f "$shell_config" ]]; then
        cp "$shell_config" "$backup_dir/"
        log_verbose "  Сохранен: $(basename "$shell_config")"
    fi

    # Backup .bashrc и .zshrc (если отличаются от текущего shell)
    for rc in "$HOME/.bashrc" "$HOME/.zshrc" "$HOME/.profile"; do
        if [[ -f "$rc" && "$rc" != "$shell_config" ]]; then
            cp "$rc" "$backup_dir/"
            log_verbose "  Сохранен: $(basename "$rc")"
        fi
    done

    # Backup mise config
    local mise_config=$(get_mise_config_dir)
    if [[ -n "$mise_config" && -d "$mise_config" ]]; then
        cp -r "$mise_config" "$backup_dir/mise_config"
        log_verbose "  Сохранен: mise config"
    fi

    # Backup .tool-versions
    if [[ -f "$PROJECT_ROOT/.tool-versions" ]]; then
        cp "$PROJECT_ROOT/.tool-versions" "$backup_dir/"
        log_verbose "  Сохранен: .tool-versions"
    fi

    # Backup requirements.txt
    if [[ -f "$PROJECT_ROOT/orchestrator/requirements.txt" ]]; then
        cp "$PROJECT_ROOT/orchestrator/requirements.txt" "$backup_dir/"
        log_verbose "  Сохранен: requirements.txt"
    fi

    # Backup package.json
    if [[ -f "$PROJECT_ROOT/frontend/package.json" ]]; then
        cp "$PROJECT_ROOT/frontend/package.json" "$backup_dir/"
        log_verbose "  Сохранен: package.json"
    fi

    log_success "Backup создан: $backup_dir"
    echo ""

    # Сохранить путь для финального отчета
    BACKUP_PATH="$backup_dir"
}

##############################################################################
# REMOVAL FUNCTIONS
##############################################################################

remove_project_deps() {
    log_step "Удаление зависимостей проекта..."

    # Python venv
    if [[ "${INSTALLED_COMPONENTS[venv]:-}" == "true" ]]; then
        local venv_path="$PROJECT_ROOT/orchestrator/venv"
        if $DRY_RUN; then
            log_info "[DRY-RUN] Будет удален: $venv_path"
        else
            safe_rm "$venv_path" true
            log_success "Удален Python venv"
        fi
    fi

    # Node modules
    if [[ "${INSTALLED_COMPONENTS[node_modules]:-}" == "true" ]]; then
        local nm_path="$PROJECT_ROOT/frontend/node_modules"
        if $DRY_RUN; then
            log_info "[DRY-RUN] Будет удален: $nm_path"
        else
            safe_rm "$nm_path" true
            log_success "Удален node_modules"
        fi
    fi

    # Go modules cache (опционально, так как глобальный)
    if [[ "${INSTALLED_COMPONENTS[go_modules]:-}" == "true" ]]; then
        local go_cache="$HOME/go/pkg/mod"
        if $DRY_RUN; then
            log_info "[DRY-RUN] Будет удален: $go_cache"
        else
            # Используем go clean для корректной очистки
            if command -v go &>/dev/null; then
                go clean -modcache 2>/dev/null || safe_rm "$go_cache" true
            else
                safe_rm "$go_cache" true
            fi
            log_success "Удален Go modules cache"
        fi
    fi
}

remove_mise_runtimes() {
    log_step "Удаление mise runtimes..."

    local mise_data=$(get_mise_data_dir)

    if [[ -z "$mise_data" || ! -d "$mise_data/installs" ]]; then
        log_info "mise runtimes не найдены"
        return 0
    fi

    if $DRY_RUN; then
        log_info "[DRY-RUN] Будет удален: $mise_data/installs"
        return 0
    fi

    # Используем mise для удаления если доступен
    if command -v mise &>/dev/null; then
        # Удаляем все установленные версии
        log_verbose "Удаление через mise uninstall..."

        # Получаем список установленных инструментов
        local tools=$(mise list 2>/dev/null | awk '{print $1"@"$2}' | grep -v "^@$" || true)

        for tool in $tools; do
            log_verbose "  Удаление: $tool"
            mise uninstall "$tool" 2>/dev/null || true
        done
    fi

    # Удаляем директорию installs напрямую (на случай если mise недоступен)
    safe_rm "$mise_data/installs" true

    log_success "mise runtimes удалены"
}

remove_mise() {
    log_step "Удаление mise..."

    if ! is_mise_installed; then
        log_info "mise не установлен"
        return 0
    fi

    if $DRY_RUN; then
        log_info "[DRY-RUN] Будет удален mise и его конфигурация"
        return 0
    fi

    local platform=$(detect_platform)

    # Удаление через пакетный менеджер
    case "$platform" in
        linux-pacman|wsl-pacman)
            if pacman -Qi mise &>/dev/null 2>&1; then
                log_info "Удаление mise через pacman..."
                sudo pacman -Rns --noconfirm mise 2>/dev/null || true
            fi
            ;;
        linux-apt|wsl-apt)
            if dpkg -l mise &>/dev/null 2>&1; then
                log_info "Удаление mise через apt..."
                sudo apt-get remove -y mise 2>/dev/null || true
                sudo apt-get autoremove -y 2>/dev/null || true
                # Удаление репозитория
                sudo rm -f /etc/apt/sources.list.d/mise.list
                sudo rm -f /etc/apt/keyrings/mise-archive-keyring.gpg
            fi
            ;;
        linux-dnf)
            if rpm -q mise &>/dev/null 2>&1; then
                log_info "Удаление mise через dnf..."
                sudo dnf remove -y mise 2>/dev/null || true
            fi
            ;;
        macos)
            if command -v brew &>/dev/null && brew list mise &>/dev/null 2>&1; then
                log_info "Удаление mise через brew..."
                brew uninstall mise 2>/dev/null || true
            fi
            ;;
    esac

    # Удаление бинарника из ~/.local/bin (если установлен через curl)
    if [[ -x "$HOME/.local/bin/mise" ]]; then
        rm -f "$HOME/.local/bin/mise"
        log_verbose "Удален ~/.local/bin/mise"
    fi

    # Удаление data директории
    local mise_data
    mise_data=$(get_mise_data_dir)
    if [[ -n "$mise_data" && -d "$mise_data" ]]; then
        safe_rm "$mise_data" true
        log_verbose "Удален $mise_data"
    fi

    # Удаление config директории
    local mise_config
    mise_config=$(get_mise_config_dir)
    if [[ -n "$mise_config" && -d "$mise_config" ]]; then
        safe_rm "$mise_config" true
        log_verbose "Удален $mise_config"
    fi

    # Удаление legacy ~/.mise директории
    if [[ -d "$HOME/.mise" ]]; then
        safe_rm "$HOME/.mise" true
        log_verbose "Удален ~/.mise"
    fi

    # Cleanup shell config
    cleanup_shell_config

    log_success "mise удален"
}

cleanup_shell_config() {
    log_step "Очистка shell конфигурации..."

    # Список файлов для очистки
    local configs=("$HOME/.bashrc" "$HOME/.zshrc" "$HOME/.profile")

    # Добавляем fish config если существует
    if [[ -f "$HOME/.config/fish/config.fish" ]]; then
        configs+=("$HOME/.config/fish/config.fish")
    fi

    for config in "${configs[@]}"; do
        if [[ ! -f "$config" ]]; then
            continue
        fi

        if $DRY_RUN; then
            if grep -q "mise activate" "$config" 2>/dev/null; then
                log_info "[DRY-RUN] Будет очищен: $config"
            fi
            continue
        fi

        # Удаляем строки связанные с mise
        if grep -q "mise" "$config" 2>/dev/null; then
            log_verbose "Очистка: $config"

            # Создаем временный файл
            local tmp_file
            tmp_file=$(mktemp)
            register_temp_file "$tmp_file"

            # Удаляем строки с mise (включая комментарии)
            grep -v -E "(mise activate|mise hook|# mise)" "$config" > "$tmp_file" 2>/dev/null || true

            # Удаляем пустые строки в конце файла (портабельно)
            sed_inplace -e ':a' -e '/^\n*$/{$d;N;ba' -e '}' "$tmp_file" 2>/dev/null || true

            # Заменяем оригинал
            mv "$tmp_file" "$config"
        fi
    done

    if ! $DRY_RUN; then
        log_success "Shell конфигурация очищена"
    fi
}

remove_docker() {
    log_step "Удаление Docker..."

    if ! is_docker_installed; then
        log_info "Docker не установлен"
        return 0
    fi

    local platform=$(detect_platform)

    # WSL - особый случай
    if is_wsl; then
        echo ""
        log_warning "В WSL Docker управляется через Docker Desktop для Windows"
        echo ""
        echo "Для удаления Docker Desktop:"
        echo "  1. Откройте Windows Settings → Apps → Installed Apps"
        echo "  2. Найдите 'Docker Desktop' и удалите"
        echo ""
        return 0
    fi

    # macOS - особый случай
    if is_macos; then
        echo ""
        log_warning "На macOS Docker управляется через Docker Desktop"
        echo ""
        if command -v brew &>/dev/null; then
            echo "Для удаления через Homebrew:"
            echo "  brew uninstall --cask docker"
        else
            echo "Для удаления:"
            echo "  1. Откройте Applications"
            echo "  2. Перетащите Docker в корзину"
        fi
        echo ""
        return 0
    fi

    if $DRY_RUN; then
        log_info "[DRY-RUN] Будет удален Docker"
        if $REMOVE_VOLUMES; then
            log_info "[DRY-RUN] Будут удалены Docker volumes"
        fi
        return 0
    fi

    # Остановка Docker daemon
    if command -v systemctl &>/dev/null; then
        sudo systemctl stop docker 2>/dev/null || true
        sudo systemctl disable docker 2>/dev/null || true
    fi

    # Удаление volumes если запрошено
    if $REMOVE_VOLUMES && [[ "${INSTALLED_COMPONENTS[docker_volumes]:-}" == "true" ]]; then
        log_warning "Удаление Docker volumes..."

        # Предупреждение о потере данных
        if ! $FORCE; then
            echo ""
            echo -e "${RED}ВНИМАНИЕ: Все данные в Docker volumes будут БЕЗВОЗВРАТНО удалены!${NC}"
            echo "Это включает:"
            echo "  - Базы данных PostgreSQL"
            echo "  - Данные Redis"
            echo "  - Другие persistent данные"
            echo ""
            if ! confirm_action "Вы уверены что хотите удалить все Docker volumes?" "n"; then
                log_info "Удаление volumes отменено"
                REMOVE_VOLUMES=false
            fi
        fi

        if $REMOVE_VOLUMES; then
            # Сначала остановить контейнеры связанные с проектом
            local containers
            containers=$(docker ps -aq --filter "name=command-center" 2>/dev/null || true)
            if [[ -n "$containers" ]]; then
                log_verbose "Остановка контейнеров проекта..."
                echo "$containers" | xargs docker stop 2>/dev/null || true
                echo "$containers" | xargs docker rm 2>/dev/null || true
            fi

            # Затем удалить volumes по одному с обработкой ошибок
            log_verbose "Удаление Docker volumes..."
            docker volume ls -q --filter "name=command-center" 2>/dev/null | while read -r vol; do
                if [[ -n "$vol" ]]; then
                    if ! docker volume rm "$vol" 2>/dev/null; then
                        log_warning "Не удалось удалить volume: $vol (возможно используется)"
                    fi
                fi
            done
            log_success "Docker volumes удалены"
        fi
    fi

    # Удаление Docker через пакетный менеджер
    case "$platform" in
        linux-pacman)
            log_info "Удаление Docker через pacman..."
            sudo pacman -Rns --noconfirm docker docker-compose 2>/dev/null || true
            ;;
        linux-apt)
            log_info "Удаление Docker через apt..."
            sudo apt-get remove -y docker-ce docker-ce-cli containerd.io \
                docker-buildx-plugin docker-compose-plugin 2>/dev/null || true
            sudo apt-get autoremove -y 2>/dev/null || true
            # Удаление репозитория
            sudo rm -f /etc/apt/sources.list.d/docker.list
            sudo rm -f /etc/apt/keyrings/docker.gpg
            ;;
        linux-dnf)
            log_info "Удаление Docker через dnf..."
            sudo dnf remove -y docker-ce docker-ce-cli containerd.io \
                docker-buildx-plugin docker-compose-plugin 2>/dev/null || true
            ;;
    esac

    # Удаление Docker данных (если не удалены volumes)
    if ! $REMOVE_VOLUMES; then
        log_info "Docker данные сохранены в /var/lib/docker"
        log_info "Для полного удаления выполните: sudo rm -rf /var/lib/docker"
    else
        sudo rm -rf /var/lib/docker 2>/dev/null || true
        sudo rm -rf /var/lib/containerd 2>/dev/null || true
    fi

    # Удаление группы docker
    if getent group docker &>/dev/null; then
        sudo groupdel docker 2>/dev/null || true
    fi

    log_success "Docker удален"
}

##############################################################################
# FINAL REPORT
##############################################################################

print_report() {
    echo ""
    echo -e "${BOLD}============================================================${NC}"
    echo -e "${BOLD}  Удаление завершено${NC}"
    echo -e "${BOLD}============================================================${NC}"
    echo ""

    if [[ -n "${BACKUP_PATH:-}" ]]; then
        echo -e "Backup сохранен: ${GREEN}$BACKUP_PATH${NC}"
        echo ""
    fi

    echo "Удалено:"

    if should_remove "venv" && [[ "${INSTALLED_COMPONENTS[venv]:-}" == "true" ]]; then
        echo -e "  ${GREEN}[OK]${NC} Python venv"
    fi

    if should_remove "node_modules" && [[ "${INSTALLED_COMPONENTS[node_modules]:-}" == "true" ]]; then
        echo -e "  ${GREEN}[OK]${NC} Node modules"
    fi

    if should_remove "go_modules" && [[ "${INSTALLED_COMPONENTS[go_modules]:-}" == "true" ]]; then
        echo -e "  ${GREEN}[OK]${NC} Go modules cache"
    fi

    if should_remove "mise_runtimes" && [[ "${INSTALLED_COMPONENTS[mise_runtimes]:-}" == "true" ]]; then
        echo -e "  ${GREEN}[OK]${NC} mise runtimes"
    fi

    if should_remove "mise" && [[ "${INSTALLED_COMPONENTS[mise]:-}" == "true" ]]; then
        echo -e "  ${GREEN}[OK]${NC} mise + shell config"
    fi

    if should_remove "docker" && [[ "${INSTALLED_COMPONENTS[docker]:-}" == "true" ]]; then
        echo -e "  ${GREEN}[OK]${NC} Docker"
        if $REMOVE_VOLUMES; then
            echo -e "  ${GREEN}[OK]${NC} Docker volumes"
        fi
    fi

    echo ""

    # Рекомендации
    if should_remove "mise" && [[ "${INSTALLED_COMPONENTS[mise]:-}" == "true" ]]; then
        echo "Перезапустите терминал для применения изменений в shell config."
        echo ""
    fi

    echo "Для повторной установки выполните:"
    echo "  ./scripts/setup/install.sh"
    echo ""
}

##############################################################################
# MAIN
##############################################################################

main() {
    parse_args "$@"

    echo ""
    echo -e "${BOLD}============================================================${NC}"
    echo -e "${BOLD}  CommandCenter1C - Development Environment Uninstaller${NC}"
    echo -e "${BOLD}============================================================${NC}"
    echo ""

    local platform=$(detect_platform)
    log_info "Платформа: $platform"
    log_info "Проект: $PROJECT_ROOT"
    echo ""

    if $DRY_RUN; then
        log_warning "Режим DRY-RUN: изменения НЕ будут применены"
        echo ""
    fi

    # Определение установленных компонентов
    detect_installed_components

    # Показать план удаления
    if ! show_removal_plan; then
        log_info "Нет компонентов для удаления"
        exit 0
    fi

    # Запрос подтверждения
    if ! $DRY_RUN && ! $FORCE; then
        if ! confirm_action "Продолжить удаление?" "n"; then
            log_info "Удаление отменено"
            exit 0
        fi
    fi

    # Создание backup если запрошено
    if $BACKUP && ! $DRY_RUN; then
        create_backup
    fi

    # Порядок удаления: от безопасного к опасному
    # 1. Project dependencies (всегда безопасно)
    if should_remove "venv" || should_remove "node_modules" || should_remove "go_modules"; then
        remove_project_deps
        echo ""
    fi

    # 2. mise runtimes (можно переустановить)
    if should_remove "mise_runtimes" && [[ "${INSTALLED_COMPONENTS[mise_runtimes]:-}" == "true" ]]; then
        remove_mise_runtimes
        echo ""
    fi

    # 3. mise itself
    if should_remove "mise" && [[ "${INSTALLED_COMPONENTS[mise]:-}" == "true" ]]; then
        remove_mise
        echo ""
    fi

    # 4. Docker (последний, с предупреждениями)
    if should_remove "docker" && [[ "${INSTALLED_COMPONENTS[docker]:-}" == "true" ]]; then
        if ! $FORCE; then
            echo ""
            log_warning "Docker является системным компонентом и может использоваться другими проектами"
            if ! confirm_action "Удалить Docker?" "n"; then
                log_info "Удаление Docker пропущено"
            else
                remove_docker
            fi
        else
            remove_docker
        fi
        echo ""
    fi

    # Финальный отчет
    if ! $DRY_RUN; then
        print_report
    else
        echo ""
        log_info "DRY-RUN завершен. Для реального удаления уберите флаг --dry-run"
        echo ""
    fi
}

main "$@"
