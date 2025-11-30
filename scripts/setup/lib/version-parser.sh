#!/bin/bash

##############################################################################
# CommandCenter1C - Version Parser
##############################################################################
# Автоматическое определение требуемых версий из файлов проекта
#
# Usage:
#   source scripts/setup/lib/version-parser.sh
#   go_ver=$(get_required_go_version)
##############################################################################

# Предотвращение повторного sourcing
if [ -n "$VERSION_PARSER_LOADED" ]; then
    return 0
fi
VERSION_PARSER_LOADED=true

# Загрузить common.sh если не загружен
PARSER_SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [ -z "$SETUP_COMMON_LOADED" ]; then
    source "$PARSER_SCRIPT_DIR/common.sh"
fi

##############################################################################
# TOOL-VERSIONS FILE (приоритетный источник)
##############################################################################

# get_tool_version - получение версии из .tool-versions
# Usage: ver=$(get_tool_version "go")
get_tool_version() {
    local tool=$1
    local tool_versions="$PROJECT_ROOT/.tool-versions"

    if [ -f "$tool_versions" ]; then
        grep "^${tool} " "$tool_versions" 2>/dev/null | awk '{print $2}'
    fi
}

##############################################################################
# GO VERSION
##############################################################################

# get_required_go_version - определение требуемой версии Go
# Приоритет: .tool-versions > go.mod (максимальная из всех)
get_required_go_version() {
    # Приоритет 1: .tool-versions
    local tv_version=$(get_tool_version "go")
    if [ -n "$tv_version" ]; then
        echo "$tv_version"
        return
    fi

    # Приоритет 2: Найти максимальную версию из всех go.mod
    local max_version="0.0.0"

    # Поиск всех go.mod файлов
    while IFS= read -r -d '' mod_file; do
        # Извлечь версию Go из go.mod (строка "go 1.24" или "go 1.24.0")
        local version=$(grep "^go " "$mod_file" 2>/dev/null | head -1 | awk '{print $2}')

        if [ -n "$version" ]; then
            # Нормализовать версию (добавить .0 если нужно)
            if [[ "$version" =~ ^[0-9]+\.[0-9]+$ ]]; then
                version="${version}.0"
            fi

            # Сравнить с максимальной
            if version_gt "$version" "$max_version"; then
                max_version="$version"
            fi
        fi
    done < <(find "$PROJECT_ROOT/go-services" -name "go.mod" -type f -print0 2>/dev/null)

    # Если найдена версия > 0.0.0
    if [ "$max_version" != "0.0.0" ]; then
        echo "$max_version"
        return
    fi

    # Fallback: минимальная рекомендуемая версия
    echo "1.21.0"
}

##############################################################################
# PYTHON VERSION
##############################################################################

# get_required_python_version - определение требуемой версии Python
# Приоритет: .tool-versions > pyproject.toml > requirements.txt (по Django)
get_required_python_version() {
    # Приоритет 1: .tool-versions
    local tv_version=$(get_tool_version "python")
    if [ -n "$tv_version" ]; then
        echo "$tv_version"
        return
    fi

    # Приоритет 2: pyproject.toml
    local pyproject="$PROJECT_ROOT/orchestrator/pyproject.toml"
    if [ -f "$pyproject" ]; then
        # Ищем python_requires = ">=3.11" или requires-python = ">=3.11"
        local version=$(grep -E '(python_requires|requires-python)\s*=' "$pyproject" 2>/dev/null | \
                       grep -oE '[0-9]+\.[0-9]+' | head -1)
        if [ -n "$version" ]; then
            echo "$version"
            return
        fi
    fi

    # Приоритет 3: Определение по версии Django в requirements.txt
    local requirements="$PROJECT_ROOT/orchestrator/requirements.txt"
    if [ -f "$requirements" ]; then
        local django_ver=$(grep -E "^Django==" "$requirements" 2>/dev/null | \
                          grep -oE '[0-9]+\.[0-9]+' | head -1)

        if [ -n "$django_ver" ]; then
            local major=$(echo "$django_ver" | cut -d'.' -f1)

            case "$major" in
                5) echo "3.12" ;;  # Django 5.x требует Python 3.10+, рекомендуем 3.12
                4) echo "3.11" ;;  # Django 4.x требует Python 3.8+, рекомендуем 3.11
                3) echo "3.9" ;;   # Django 3.x
                *) echo "3.11" ;;  # Default
            esac
            return
        fi
    fi

    # Fallback
    echo "3.11"
}

##############################################################################
# NODE.JS VERSION
##############################################################################

# get_required_nodejs_version - определение требуемой версии Node.js
# Приоритет: .tool-versions > package.json engines > .nvmrc > по Vite версии
get_required_nodejs_version() {
    # Приоритет 1: .tool-versions
    local tv_version=$(get_tool_version "nodejs")
    if [ -n "$tv_version" ]; then
        echo "$tv_version"
        return
    fi

    local package_json="$PROJECT_ROOT/frontend/package.json"

    # Приоритет 2: engines.node в package.json (требует jq)
    if [ -f "$package_json" ] && command_exists jq; then
        local engines_node=$(jq -r '.engines.node // empty' "$package_json" 2>/dev/null)
        if [ -n "$engines_node" ]; then
            # Парсим ">=18.0.0" или "^20" → извлекаем major версию
            local major=$(echo "$engines_node" | grep -oE '[0-9]+' | head -1)
            if [ -n "$major" ]; then
                echo "$major"
                return
            fi
        fi
    fi

    # Приоритет 3: .nvmrc
    local nvmrc="$PROJECT_ROOT/frontend/.nvmrc"
    if [ -f "$nvmrc" ]; then
        local version=$(cat "$nvmrc" | tr -d 'v' | grep -oE '[0-9]+' | head -1)
        if [ -n "$version" ]; then
            echo "$version"
            return
        fi
    fi

    # Приоритет 4: По версии Vite в package.json
    if [ -f "$package_json" ]; then
        local vite_ver=""
        if command_exists jq; then
            vite_ver=$(jq -r '.devDependencies.vite // empty' "$package_json" 2>/dev/null | tr -d '^~')
        else
            # Без jq - grep
            vite_ver=$(grep -oE '"vite"\s*:\s*"[^"]+' "$package_json" | grep -oE '[0-9]+' | head -1)
        fi

        if [ -n "$vite_ver" ]; then
            local vite_major=$(echo "$vite_ver" | grep -oE '^[0-9]+')
            case "$vite_major" in
                6) echo "22" ;;   # Vite 6.x требует Node 20+
                5) echo "20" ;;   # Vite 5.x требует Node 18+
                4) echo "18" ;;   # Vite 4.x требует Node 14.18+
                *) echo "20" ;;   # Default LTS
            esac
            return
        fi
    fi

    # Fallback: текущая LTS версия
    echo "20"
}

##############################################################################
# DOCKER VERSION
##############################################################################

# get_required_docker_version - минимальная версия Docker
get_required_docker_version() {
    # Приоритет 1: .tool-versions
    local tv_version=$(get_tool_version "docker")
    if [ -n "$tv_version" ]; then
        echo "$tv_version"
        return
    fi

    # Для docker compose v2 требуется Docker 20.10+
    echo "20.10"
}

# get_required_compose_version - минимальная версия Docker Compose
get_required_compose_version() {
    echo "2.0"
}

##############################################################################
# INFRASTRUCTURE VERSIONS (из docker-compose.yml)
##############################################################################

# get_postgres_version - версия PostgreSQL из docker-compose.yml
get_postgres_version() {
    local compose="$PROJECT_ROOT/docker-compose.yml"
    if [ -f "$compose" ]; then
        grep -E 'image:\s*postgres:' "$compose" | \
            grep -oE '[0-9]+(\.[0-9]+)?' | head -1
    else
        echo "15"
    fi
}

# get_redis_version - версия Redis из docker-compose.yml
get_redis_version() {
    local compose="$PROJECT_ROOT/docker-compose.yml"
    if [ -f "$compose" ]; then
        grep -E 'image:\s*redis:' "$compose" | \
            grep -oE '[0-9]+(\.[0-9]+)?' | head -1
    else
        echo "7"
    fi
}

##############################################################################
# SUMMARY FUNCTION
##############################################################################

# print_required_versions - вывод всех требуемых версий
print_required_versions() {
    log_subsection "Требуемые версии (из файлов проекта)"

    local go_ver=$(get_required_go_version)
    local py_ver=$(get_required_python_version)
    local node_ver=$(get_required_nodejs_version)
    local docker_ver=$(get_required_docker_version)
    local pg_ver=$(get_postgres_version)
    local redis_ver=$(get_redis_version)

    echo "  Go:         $go_ver  (из go-services/*/go.mod)"
    echo "  Python:     $py_ver  (из Django версии)"
    echo "  Node.js:    $node_ver  (из frontend/package.json)"
    echo "  Docker:     $docker_ver+  (для docker compose v2)"
    echo "  PostgreSQL: $pg_ver  (из docker-compose.yml)"
    echo "  Redis:      $redis_ver  (из docker-compose.yml)"
    echo ""
}

# get_all_required_versions - получить все версии как ассоциативный массив
# Usage: declare -A versions; get_all_required_versions versions
get_all_required_versions() {
    local -n _versions=$1

    _versions[go]=$(get_required_go_version)
    _versions[python]=$(get_required_python_version)
    _versions[nodejs]=$(get_required_nodejs_version)
    _versions[docker]=$(get_required_docker_version)
    _versions[compose]=$(get_required_compose_version)
    _versions[postgres]=$(get_postgres_version)
    _versions[redis]=$(get_redis_version)
}

##############################################################################
# End of version-parser.sh
##############################################################################
