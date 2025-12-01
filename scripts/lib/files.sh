#!/bin/bash

##############################################################################
# CommandCenter1C - File Utilities Library
##############################################################################
#
# Утилиты для работы с файлами: безопасное удаление, резервные копии,
# кросс-платформенные операции.
#
# Usage:
#   source scripts/lib/files.sh
#
# Dependencies:
#   - scripts/lib/core.sh
#   - scripts/lib/platform.sh (опционально, для is_macos)
#
# Exports:
#   Safe operations: safe_rm, sed_inplace
#   Backup: backup_file, create_backup_dir
#   Size: format_size, get_dir_size, get_dir_size_human
#   Time: get_file_mtime, find_newest_file, is_file_newer
#   Env: load_env_file
#
# Version: 1.0.0
##############################################################################

# Проверка зависимостей
if [[ -z "${CC1C_LIB_CORE_LOADED:-}" ]]; then
    echo "ERROR: files.sh requires core.sh to be loaded first" >&2
    return 1
fi

# Предотвращение повторного sourcing
if [[ -n "${CC1C_LIB_FILES_LOADED:-}" ]]; then
    return 0
fi
CC1C_LIB_FILES_LOADED=true

##############################################################################
# SAFE FILE OPERATIONS
##############################################################################

# safe_rm - безопасное удаление с проверкой пути
# Usage:
#   safe_rm "/path/to/dir"         # обычное удаление
#   safe_rm "/path/to/dir" "true"  # принудительное удаление (rm -rf)
# Returns: 0 on success, 1 on error
safe_rm() {
    local path="$1"
    local force="${2:-false}"

    # Проверка что путь не пустой
    if [[ -z "$path" ]]; then
        log_error "safe_rm: пустой путь"
        return 1
    fi

    # Проверка что путь не содержит только пробелы
    if [[ "$path" =~ ^[[:space:]]*$ ]]; then
        log_error "safe_rm: путь содержит только пробелы"
        return 1
    fi

    # Запрещенные пути (защита от случайного удаления)
    local -a forbidden_paths=(
        "/"
        "/home"
        "/root"
        "/etc"
        "/usr"
        "/var"
        "/bin"
        "/sbin"
        "/lib"
        "/lib64"
        "/boot"
        "/dev"
        "/proc"
        "/sys"
        "/tmp"
        "$HOME"
    )

    for forbidden in "${forbidden_paths[@]}"; do
        # Сравниваем и с оригинальным путем, и без trailing slash
        if [[ "$path" == "$forbidden" ]] || [[ "${path%/}" == "$forbidden" ]]; then
            log_error "safe_rm: отказ в удалении защищенного пути: $path"
            return 1
        fi
    done

    # Нормализация пути (убираем trailing slashes)
    path="${path%/}"

    # Проверка что путь существует
    if [[ ! -e "$path" ]]; then
        log_verbose "safe_rm: путь не существует: $path"
        return 0
    fi

    # Удаление
    if [[ "$force" == "true" ]]; then
        rm -rf "$path"
    else
        rm -r "$path"
    fi
}

# sed_inplace - портабельный sed -i (работает на Linux и macOS)
# Usage: sed_inplace "s/old/new/g" "/path/to/file"
sed_inplace() {
    local expression="$1"
    local file="$2"

    if [[ ! -f "$file" ]]; then
        log_error "sed_inplace: файл не найден: $file"
        return 1
    fi

    if [[ "$OSTYPE" == "darwin"* ]]; then
        sed -i '' "$expression" "$file"
    else
        sed -i "$expression" "$file"
    fi
}

# ensure_dir - создание директории если не существует
# Usage: ensure_dir "/path/to/dir"
ensure_dir() {
    local dir="$1"

    if [[ ! -d "$dir" ]]; then
        mkdir -p "$dir"
        log_verbose "Создана директория: $dir"
    fi
}

# copy_with_backup - копирование файла с созданием backup
# Usage: copy_with_backup "/source" "/dest"
copy_with_backup() {
    local source="$1"
    local dest="$2"

    if [[ ! -f "$source" ]]; then
        log_error "copy_with_backup: источник не найден: $source"
        return 1
    fi

    if [[ -f "$dest" ]]; then
        backup_file "$dest"
    fi

    cp "$source" "$dest"
}

##############################################################################
# BACKUP UTILITIES
##############################################################################

# backup_file - создание timestamped backup файла
# Usage:
#   backup_path=$(backup_file "/path/to/file")
# Returns: путь к backup файлу
backup_file() {
    local file=$1
    local timestamp
    timestamp=$(date +%Y%m%d_%H%M%S)
    local backup="${file}.backup_${timestamp}"

    if [[ -f "$file" ]]; then
        cp "$file" "$backup"
        echo "$backup"
    fi
}

# create_backup_dir - создание директории для backups
# Usage:
#   backup_dir=$(create_backup_dir "cc1c-setup")
# Returns: путь к backup директории
create_backup_dir() {
    local prefix=${1:-"backup"}
    local timestamp
    timestamp=$(date +%Y%m%d_%H%M%S)
    local backup_dir="$HOME/.cc1c-backups/${prefix}_${timestamp}"

    mkdir -p "$backup_dir"
    echo "$backup_dir"
}

# cleanup_old_backups - удаление старых backups
# Usage: cleanup_old_backups "$HOME/.cc1c-backups" 7  # оставить последние 7 дней
cleanup_old_backups() {
    local backup_dir="$1"
    local days=${2:-7}

    if [[ ! -d "$backup_dir" ]]; then
        return 0
    fi

    # Удалить файлы старше N дней
    find "$backup_dir" -type f -mtime +"$days" -delete 2>/dev/null || true

    # Удалить пустые директории
    find "$backup_dir" -type d -empty -delete 2>/dev/null || true
}

##############################################################################
# FILE SIZE UTILITIES
##############################################################################

# format_size - форматирование размера в человекочитаемый вид
# Usage: format_size 1073741824  # Output: "1 GB"
format_size() {
    local bytes=$1

    if [[ $bytes -ge 1073741824 ]]; then
        echo "$(( bytes / 1073741824 )) GB"
    elif [[ $bytes -ge 1048576 ]]; then
        echo "$(( bytes / 1048576 )) MB"
    elif [[ $bytes -ge 1024 ]]; then
        echo "$(( bytes / 1024 )) KB"
    else
        echo "$bytes B"
    fi
}

# get_dir_size - получение размера директории в байтах
# Usage: size=$(get_dir_size "/path/to/dir")
# Note: кросс-платформенная реализация (Linux/macOS)
get_dir_size() {
    local dir=$1

    if [[ -d "$dir" ]]; then
        # macOS du не поддерживает -b, используем -k и умножаем на 1024
        if [[ "$OSTYPE" == "darwin"* ]]; then
            local kb
            kb=$(du -sk "$dir" 2>/dev/null | cut -f1)
            echo $((kb * 1024))
        else
            du -sb "$dir" 2>/dev/null | cut -f1
        fi
    else
        echo "0"
    fi
}

# get_dir_size_human - получение размера директории в человекочитаемом виде
# Usage: get_dir_size_human "/path/to/dir"  # Output: "125 MB"
get_dir_size_human() {
    local dir=$1
    local bytes
    bytes=$(get_dir_size "$dir")
    format_size "$bytes"
}

# get_file_size - получение размера файла в байтах
# Usage: size=$(get_file_size "/path/to/file")
get_file_size() {
    local file=$1

    if [[ -f "$file" ]]; then
        if [[ "$OSTYPE" == "darwin"* ]]; then
            stat -f%z "$file" 2>/dev/null
        else
            stat -c%s "$file" 2>/dev/null
        fi
    else
        echo "0"
    fi
}

##############################################################################
# FILE TIME UTILITIES
##############################################################################

# get_file_mtime - получение mtime файла (Unix timestamp)
# Usage: mtime=$(get_file_mtime "/path/to/file")
# Note: кросс-платформенная реализация
get_file_mtime() {
    local file_path=$1

    if [[ ! -f "$file_path" ]]; then
        echo ""
        return 1
    fi

    if [[ "$OSTYPE" == "darwin"* ]]; then
        # BSD stat: -f %m returns modification time as Unix timestamp
        stat -f %m "$file_path" 2>/dev/null
    else
        # GNU stat (Linux, WSL): -c %Y
        stat -c %Y "$file_path" 2>/dev/null
    fi
}

# find_newest_file - поиск самого нового файла по паттерну
# Usage: newest=$(find_newest_file "/path/to/dir" "*.go")
# Returns: путь к самому новому файлу
find_newest_file() {
    local search_dir=$1
    local pattern=$2
    local newest_file=""
    local newest_time=0

    # Используем find + while read для кросс-платформенности
    while IFS= read -r -d '' file; do
        local file_time
        file_time=$(get_file_mtime "$file")
        if [[ -n "$file_time" ]] && [[ "$file_time" -gt "$newest_time" ]]; then
            newest_time="$file_time"
            newest_file="$file"
        fi
    done < <(find "$search_dir" -name "$pattern" -type f -print0 2>/dev/null)

    echo "$newest_file"
}

# is_file_newer - проверка "файл A новее файла B"
# Usage: if is_file_newer "/path/a" "/path/b"; then ...
is_file_newer() {
    local file_a=$1
    local file_b=$2

    # Используем встроенную проверку bash -nt (newer than)
    [[ "$file_a" -nt "$file_b" ]]
}

# is_file_older - проверка "файл A старше файла B"
# Usage: if is_file_older "/path/a" "/path/b"; then ...
is_file_older() {
    local file_a=$1
    local file_b=$2

    [[ "$file_a" -ot "$file_b" ]]
}

##############################################################################
# TEMP FILE UTILITIES
##############################################################################

# create_temp_file - создание временного файла
# Usage:
#   tmp=$(create_temp_file "prefix")
#   # использовать $tmp
#   rm -f "$tmp"
create_temp_file() {
    local prefix=${1:-"cc1c"}
    mktemp "/tmp/${prefix}.XXXXXX"
}

# create_temp_dir - создание временной директории
# Usage:
#   tmpdir=$(create_temp_dir "prefix")
#   # использовать $tmpdir
#   rm -rf "$tmpdir"
create_temp_dir() {
    local prefix=${1:-"cc1c"}
    mktemp -d "/tmp/${prefix}.XXXXXX"
}

##############################################################################
# PATH UTILITIES
##############################################################################

# normalize_path - нормализация пути (убирает .., ., лишние слеши)
# Usage: path=$(normalize_path "/foo//bar/../baz")
normalize_path() {
    local path=$1

    # Используем realpath если доступен (более надежно)
    if command -v realpath &>/dev/null; then
        realpath -m "$path" 2>/dev/null || echo "$path"
    else
        # Fallback: базовая нормализация
        # Убираем двойные слеши
        path="${path//\/\//\/}"
        # Убираем trailing slash (кроме корня)
        [[ "$path" != "/" ]] && path="${path%/}"
        echo "$path"
    fi
}

# get_relative_path - получение относительного пути
# Usage: rel=$(get_relative_path "/base/path" "/base/path/to/file")
get_relative_path() {
    local base=$1
    local target=$2

    # Используем realpath если доступен
    if command -v realpath &>/dev/null; then
        realpath --relative-to="$base" "$target" 2>/dev/null
    else
        # Fallback: простое удаление базового пути
        echo "${target#$base/}"
    fi
}

##############################################################################
# ENV FILE UTILITIES
##############################################################################

# load_env_file - загрузка переменных окружения из .env файлов
# Usage:
#   load_env_file                       # загружает PROJECT_ROOT/.env.local
#   load_env_file "/path/to/.env"       # загружает указанный файл
# Гарантирует что Go сервисы получают те же настройки что и Django
load_env_file() {
    local env_file="${1:-$PROJECT_ROOT/.env.local}"

    if [[ -f "$env_file" ]]; then
        log_info "Загрузка переменных окружения из $(basename "$env_file")..."

        # Export variables from env file
        # - Skip comments (lines starting with #)
        # - Skip empty lines
        # - Remove Windows line endings (\r)
        # - Use set -a to automatically export all variables
        set -a
        # shellcheck source=/dev/null
        source <(grep -v '^#' "$env_file" | grep -v '^[[:space:]]*$' | sed 's/\r$//')
        set +a

        log_success "Переменные окружения загружены"

        # Verify critical variables are set
        if [[ -z "${JWT_SECRET:-}" ]]; then
            log_warning "JWT_SECRET не найден в $env_file"
        fi
    else
        log_warning ".env файл не найден: $env_file"
        log_info "Сервисы будут использовать значения по умолчанию"
    fi

    # Load generated service configuration (ports, URLs)
    local generated_env="${PROJECT_ROOT:-}/generated/.env.services"
    if [[ -f "$generated_env" ]]; then
        set -a
        # shellcheck source=/dev/null
        source <(grep -v '^#' "$generated_env" | grep -v '^[[:space:]]*$' | grep -v '^=' | sed 's/\r$//')
        set +a
        log_verbose "Сгенерированная конфигурация портов загружена"
    fi
}

##############################################################################
# End of files.sh
##############################################################################
