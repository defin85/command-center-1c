#!/bin/bash

##############################################################################
# CommandCenter1C - PostgreSQL Helper Functions
##############################################################################
#
# Вспомогательные функции для работы с PostgreSQL.
# Используется из install.sh и других setup скриптов.
#
# Поддерживаемые платформы:
#   - Arch Linux (pacman): /var/lib/postgres/data
#   - Ubuntu/Debian (apt): /var/lib/postgresql/XX/main
#   - Fedora (dnf): /var/lib/pgsql/data
#
# Dependencies:
#   - scripts/lib/core.sh (log_info, log_error, etc.)
#   - scripts/lib/platform.sh (detect_platform, is_arch, etc.)
#
# Usage:
#   source scripts/lib/init.sh
#   source scripts/setup/lib/postgres.sh
#
# Version: 1.0.0
##############################################################################

# Предотвращение повторного sourcing
if [[ -n "${POSTGRES_MODULE_LOADED:-}" ]]; then
    return 0
fi
POSTGRES_MODULE_LOADED=true

# Проверка зависимостей
if [[ -z "${CC1C_LIB_CORE_LOADED:-}" ]]; then
    echo "ERROR: postgres.sh requires core.sh to be loaded first" >&2
    return 1
fi

if [[ -z "${CC1C_LIB_PLATFORM_LOADED:-}" ]]; then
    echo "ERROR: postgres.sh requires platform.sh to be loaded first" >&2
    return 1
fi

##############################################################################
# PATH DETECTION
##############################################################################

# pg_get_data_dir - получить путь к data directory PostgreSQL
# Usage: data_dir=$(pg_get_data_dir)
# Returns: /var/lib/postgres/data (Arch) или /var/lib/postgresql/XX/main (Ubuntu)
pg_get_data_dir() {
    local platform
    platform=$(detect_platform)

    case "$platform" in
        *-pacman)
            # Arch Linux
            echo "/var/lib/postgres/data"
            ;;
        *-apt)
            # Ubuntu/Debian - ищем версию PostgreSQL
            local pg_version
            pg_version=$(_pg_detect_version)
            if [[ -n "$pg_version" ]]; then
                echo "/var/lib/postgresql/${pg_version}/main"
            else
                # Fallback - попробуем найти
                local found_dir
                found_dir=$(find /var/lib/postgresql -maxdepth 2 -name "main" -type d 2>/dev/null | head -1)
                if [[ -n "$found_dir" ]]; then
                    echo "$found_dir"
                else
                    echo "/var/lib/postgresql/15/main"  # Стандартное значение
                fi
            fi
            ;;
        *-dnf)
            # Fedora/RHEL
            echo "/var/lib/pgsql/data"
            ;;
        *)
            # Универсальный fallback
            if [[ -d "/var/lib/postgres/data" ]]; then
                echo "/var/lib/postgres/data"
            elif [[ -d "/var/lib/pgsql/data" ]]; then
                echo "/var/lib/pgsql/data"
            else
                # Попытка найти postgresql директорию
                local found_dir
                found_dir=$(find /var/lib -maxdepth 3 -name "postgresql.conf" -type f 2>/dev/null | head -1 | xargs dirname 2>/dev/null)
                if [[ -n "$found_dir" ]]; then
                    echo "$found_dir"
                else
                    echo "/var/lib/postgres/data"  # Default
                fi
            fi
            ;;
    esac
}

# pg_get_hba_path - получить путь к pg_hba.conf
# Usage: hba_path=$(pg_get_hba_path)
pg_get_hba_path() {
    local data_dir
    data_dir=$(pg_get_data_dir)
    echo "${data_dir}/pg_hba.conf"
}

# pg_get_conf_path - получить путь к postgresql.conf
# Usage: conf_path=$(pg_get_conf_path)
pg_get_conf_path() {
    local data_dir
    data_dir=$(pg_get_data_dir)
    echo "${data_dir}/postgresql.conf"
}

# _pg_detect_version - определить установленную версию PostgreSQL
# Internal function
_pg_detect_version() {
    local version=""

    # Метод 1: через psql
    if command -v psql &>/dev/null; then
        version=$(psql --version 2>/dev/null | grep -oE '[0-9]+' | head -1)
    fi

    # Метод 2: через pg_config
    if [[ -z "$version" ]] && command -v pg_config &>/dev/null; then
        version=$(pg_config --version 2>/dev/null | grep -oE '[0-9]+' | head -1)
    fi

    # Метод 3: поиск в /usr/lib
    if [[ -z "$version" ]]; then
        version=$(ls -d /usr/lib/postgresql/*/ 2>/dev/null | grep -oE '[0-9]+' | sort -rn | head -1)
    fi

    echo "$version"
}

##############################################################################
# STATUS CHECKS
##############################################################################

# pg_cluster_exists - проверка инициализирован ли кластер PostgreSQL
# Usage: if pg_cluster_exists; then ...
# Returns: 0 если кластер существует, 1 если нет
pg_cluster_exists() {
    local data_dir
    data_dir=$(pg_get_data_dir)

    # Проверяем наличие PG_VERSION файла (признак инициализированного кластера)
    if [[ -f "${data_dir}/PG_VERSION" ]]; then
        log_debug "PostgreSQL cluster exists at ${data_dir}"
        return 0
    fi

    log_debug "PostgreSQL cluster not found at ${data_dir}"
    return 1
}

# pg_is_running - проверка запущен ли PostgreSQL
# Usage: if pg_is_running; then ...
# Returns: 0 если запущен, 1 если нет
pg_is_running() {
    # Метод 1: через systemctl (если доступен)
    if command -v systemctl &>/dev/null; then
        if systemctl is-active --quiet postgresql 2>/dev/null; then
            return 0
        fi
    fi

    # Метод 2: через pg_isready
    if command -v pg_isready &>/dev/null; then
        if pg_isready -q 2>/dev/null; then
            return 0
        fi
    fi

    # Метод 3: проверка процесса postgres
    if pgrep -x "postgres" &>/dev/null || pgrep -x "postmaster" &>/dev/null; then
        return 0
    fi

    return 1
}

# pg_user_exists - проверка существует ли пользователь PostgreSQL
# Usage: if pg_user_exists "username"; then ...
# Returns: 0 если существует, 1 если нет
pg_user_exists() {
    local username=$1

    if [[ -z "$username" ]]; then
        log_error "pg_user_exists: username is required"
        return 1
    fi

    # Проверка через psql от пользователя postgres
    local result
    result=$(sudo -u postgres psql -tAc "SELECT 1 FROM pg_roles WHERE rolname='${username}'" 2>/dev/null)

    if [[ "$result" == "1" ]]; then
        log_debug "PostgreSQL user '${username}' exists"
        return 0
    fi

    log_debug "PostgreSQL user '${username}' does not exist"
    return 1
}

# pg_database_exists - проверка существует ли база данных
# Usage: if pg_database_exists "dbname"; then ...
# Returns: 0 если существует, 1 если нет
pg_database_exists() {
    local dbname=$1

    if [[ -z "$dbname" ]]; then
        log_error "pg_database_exists: dbname is required"
        return 1
    fi

    # Проверка через psql от пользователя postgres
    local result
    result=$(sudo -u postgres psql -tAc "SELECT 1 FROM pg_database WHERE datname='${dbname}'" 2>/dev/null)

    if [[ "$result" == "1" ]]; then
        log_debug "PostgreSQL database '${dbname}' exists"
        return 0
    fi

    log_debug "PostgreSQL database '${dbname}' does not exist"
    return 1
}

##############################################################################
# CLUSTER MANAGEMENT
##############################################################################

# pg_init_cluster - инициализация кластера PostgreSQL
# Usage: pg_init_cluster
# Note: Требуется только для Arch Linux, Ubuntu делает это автоматически
pg_init_cluster() {
    local data_dir
    data_dir=$(pg_get_data_dir)

    # Проверка: уже инициализирован?
    if pg_cluster_exists; then
        log_info "PostgreSQL cluster already initialized at ${data_dir}"
        return 0
    fi

    log_info "Initializing PostgreSQL cluster at ${data_dir}..."

    local platform
    platform=$(detect_platform)

    case "$platform" in
        *-pacman)
            # Arch Linux - требуется ручная инициализация
            # Создаем директорию если не существует
            if [[ ! -d "$data_dir" ]]; then
                sudo mkdir -p "$data_dir"
                sudo chown postgres:postgres "$data_dir"
            fi

            # Инициализация от пользователя postgres
            sudo -u postgres initdb -D "$data_dir" --locale=en_US.UTF-8 --encoding=UTF8
            ;;

        *-apt)
            # Ubuntu/Debian - обычно автоматически, но проверим
            local pg_version
            pg_version=$(_pg_detect_version)

            if [[ -n "$pg_version" ]]; then
                sudo pg_ctlcluster "$pg_version" main start 2>/dev/null || \
                    sudo pg_createcluster "$pg_version" main --start
            else
                log_error "Cannot detect PostgreSQL version for cluster creation"
                return 1
            fi
            ;;

        *-dnf)
            # Fedora/RHEL
            sudo postgresql-setup --initdb
            ;;

        *)
            log_warning "Unknown platform, attempting generic initdb..."
            sudo -u postgres initdb -D "$data_dir" --locale=en_US.UTF-8 --encoding=UTF8
            ;;
    esac

    if pg_cluster_exists; then
        log_success "PostgreSQL cluster initialized at ${data_dir}"
        return 0
    else
        log_error "Failed to initialize PostgreSQL cluster"
        return 1
    fi
}

##############################################################################
# USER & DATABASE MANAGEMENT
##############################################################################

# pg_create_user - создание пользователя PostgreSQL (если не существует)
# Usage: pg_create_user "username" "password"
pg_create_user() {
    local username=$1
    local password=$2

    if [[ -z "$username" ]]; then
        log_error "pg_create_user: username is required"
        return 1
    fi

    if [[ -z "$password" ]]; then
        log_error "pg_create_user: password is required"
        return 1
    fi

    # Проверка: уже существует?
    if pg_user_exists "$username"; then
        log_info "PostgreSQL user '${username}' already exists"
        return 0
    fi

    log_info "Creating PostgreSQL user '${username}'..."

    # Создание пользователя с правами CREATEDB
    sudo -u postgres psql -c "CREATE USER ${username} WITH PASSWORD '${password}' CREATEDB;" 2>/dev/null

    if pg_user_exists "$username"; then
        log_success "PostgreSQL user '${username}' created"
        return 0
    else
        log_error "Failed to create PostgreSQL user '${username}'"
        return 1
    fi
}

# pg_create_database - создание базы данных (если не существует)
# Usage: pg_create_database "dbname" "owner"
pg_create_database() {
    local dbname=$1
    local owner=${2:-postgres}

    if [[ -z "$dbname" ]]; then
        log_error "pg_create_database: dbname is required"
        return 1
    fi

    # Проверка: уже существует?
    if pg_database_exists "$dbname"; then
        log_info "PostgreSQL database '${dbname}' already exists"
        return 0
    fi

    log_info "Creating PostgreSQL database '${dbname}' with owner '${owner}'..."

    # Создание базы данных
    sudo -u postgres psql -c "CREATE DATABASE ${dbname} OWNER ${owner};" 2>/dev/null

    if pg_database_exists "$dbname"; then
        log_success "PostgreSQL database '${dbname}' created"
        return 0
    else
        log_error "Failed to create PostgreSQL database '${dbname}'"
        return 1
    fi
}

##############################################################################
# HBA CONFIGURATION
##############################################################################

# pg_configure_hba - настройка pg_hba.conf для локальной разработки
# Usage: pg_configure_hba
# Добавляет правила для пользователя commandcenter
pg_configure_hba() {
    local hba_path
    hba_path=$(pg_get_hba_path)

    if [[ ! -f "$hba_path" ]]; then
        log_error "pg_hba.conf not found at ${hba_path}"
        log_info "Ensure PostgreSQL cluster is initialized first"
        return 1
    fi

    log_info "Configuring pg_hba.conf for local development..."

    # Проверяем, есть ли уже конфигурация для commandcenter
    if sudo grep -q "commandcenter" "$hba_path" 2>/dev/null; then
        log_info "pg_hba.conf already configured for commandcenter"
        return 0
    fi

    # Создаем backup
    local backup_path="${hba_path}.backup.$(date +%Y%m%d_%H%M%S)"
    sudo cp "$hba_path" "$backup_path"
    log_info "Created backup: ${backup_path}"

    # Добавляем конфигурацию для разработки
    # Вставляем перед первой строкой host/local (чтобы наши правила имели приоритет)
    local tmp_file
    tmp_file=$(mktemp)

    # Читаем файл и добавляем наши правила в начало (после комментариев)
    {
        # Копируем комментарии из начала файла
        sudo grep -E "^#|^$" "$hba_path" | head -20

        # Добавляем наши правила
        echo ""
        echo "# CommandCenter1C development configuration"
        echo "# Added by setup script on $(date +%Y-%m-%d)"
        echo "# TYPE  DATABASE        USER            ADDRESS                 METHOD"
        echo "local   all             postgres                                peer"
        echo "local   all             commandcenter                           trust"
        echo "host    all             commandcenter   127.0.0.1/32            md5"
        echo "host    all             commandcenter   ::1/128                 md5"
        echo ""

        # Копируем оставшиеся строки (не комментарии, которые уже скопированы)
        sudo grep -vE "^#|^$" "$hba_path"
    } > "$tmp_file"

    # Применяем изменения
    sudo cp "$tmp_file" "$hba_path"
    sudo chown postgres:postgres "$hba_path"
    sudo chmod 640 "$hba_path"
    rm -f "$tmp_file"

    log_success "pg_hba.conf configured for local development"

    # Предупреждение о перезагрузке
    log_warning "PostgreSQL needs to reload configuration:"
    log_info "  sudo systemctl reload postgresql"

    return 0
}

# pg_reload_config - перезагрузка конфигурации PostgreSQL
# Usage: pg_reload_config
pg_reload_config() {
    log_info "Reloading PostgreSQL configuration..."

    if command -v systemctl &>/dev/null; then
        sudo systemctl reload postgresql
    else
        sudo -u postgres pg_ctl reload -D "$(pg_get_data_dir)"
    fi

    if [[ $? -eq 0 ]]; then
        log_success "PostgreSQL configuration reloaded"
        return 0
    else
        log_error "Failed to reload PostgreSQL configuration"
        return 1
    fi
}

##############################################################################
# SERVICE MANAGEMENT
##############################################################################

# pg_start - запуск PostgreSQL
# Usage: pg_start
pg_start() {
    if pg_is_running; then
        log_info "PostgreSQL is already running"
        return 0
    fi

    log_info "Starting PostgreSQL..."

    if command -v systemctl &>/dev/null; then
        sudo systemctl start postgresql
    else
        sudo -u postgres pg_ctl start -D "$(pg_get_data_dir)" -l /var/log/postgresql/postgresql.log
    fi

    # Ждем запуска
    local retries=10
    while [[ $retries -gt 0 ]]; do
        if pg_is_running; then
            log_success "PostgreSQL started"
            return 0
        fi
        sleep 1
        ((retries--))
    done

    log_error "Failed to start PostgreSQL"
    return 1
}

# pg_stop - остановка PostgreSQL
# Usage: pg_stop
pg_stop() {
    if ! pg_is_running; then
        log_info "PostgreSQL is not running"
        return 0
    fi

    log_info "Stopping PostgreSQL..."

    if command -v systemctl &>/dev/null; then
        sudo systemctl stop postgresql
    else
        sudo -u postgres pg_ctl stop -D "$(pg_get_data_dir)" -m fast
    fi

    if ! pg_is_running; then
        log_success "PostgreSQL stopped"
        return 0
    else
        log_error "Failed to stop PostgreSQL"
        return 1
    fi
}

# pg_enable_autostart - включение автозапуска PostgreSQL
# Usage: pg_enable_autostart
pg_enable_autostart() {
    log_info "Enabling PostgreSQL autostart..."

    if command -v systemctl &>/dev/null; then
        sudo systemctl enable postgresql
        log_success "PostgreSQL autostart enabled"
        return 0
    else
        log_warning "systemctl not available, cannot enable autostart"
        return 1
    fi
}

##############################################################################
# UTILITY FUNCTIONS
##############################################################################

# pg_print_info - вывод информации о PostgreSQL
# Usage: pg_print_info
pg_print_info() {
    echo ""
    echo "PostgreSQL Information:"
    echo "  Data directory: $(pg_get_data_dir)"
    echo "  pg_hba.conf:    $(pg_get_hba_path)"
    echo "  Cluster exists: $(pg_cluster_exists && echo 'yes' || echo 'no')"
    echo "  Running:        $(pg_is_running && echo 'yes' || echo 'no')"

    if command -v psql &>/dev/null; then
        echo "  Version:        $(psql --version 2>/dev/null | head -1)"
    else
        echo "  Version:        psql not found"
    fi
    echo ""
}

# pg_test_connection - тестирование подключения к PostgreSQL
# Usage: pg_test_connection "username" "dbname"
pg_test_connection() {
    local username=${1:-postgres}
    local dbname=${2:-postgres}

    log_info "Testing PostgreSQL connection as '${username}' to '${dbname}'..."

    if sudo -u postgres psql -U "$username" -d "$dbname" -c "SELECT 1;" &>/dev/null; then
        log_success "Connection successful"
        return 0
    else
        log_error "Connection failed"
        return 1
    fi
}

##############################################################################
# End of postgres.sh
##############################################################################
