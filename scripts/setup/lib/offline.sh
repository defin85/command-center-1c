#!/bin/bash

##############################################################################
# CommandCenter1C - Offline Installation Module
##############################################################################
#
# Модуль для подготовки и установки offline bundle.
# Позволяет развернуть окружение разработки без доступа к интернету.
#
# PREPARE PHASE (требует интернет):
#   prepare_offline_bundle [platform] [output_dir]
#
# INSTALL PHASE (offline):
#   install_from_offline_bundle [bundle_dir] [--skip-verify]
#
# Поддерживаемые платформы:
#   - linux-amd64 (x86_64)
#   - linux-arm64 (aarch64)
#
# Структура bundle:
#   offline-bundle/
#   ├── manifest.json           # Метаданные и версии
#   ├── checksums.sha256        # SHA256 для верификации
#   ├── mise/
#   │   └── mise-linux-*        # mise binary
#   ├── runtimes/
#   │   ├── go*.tar.gz          # Go runtime
#   │   ├── cpython-*.tar.zst   # Python prebuilt
#   │   └── node-*.tar.gz       # Node.js runtime
#   ├── python-deps/
#   │   └── *.whl               # Python wheels
#   └── npm-deps/
#       └── *.tgz               # npm tarballs
#
##############################################################################

# Предотвращение повторного sourcing
if [[ -n "$OFFLINE_MODULE_LOADED" ]]; then
    return 0
fi
OFFLINE_MODULE_LOADED=true

# Загрузить общие функции (если доступны)
OFFLINE_SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [[ -f "$OFFLINE_SCRIPT_DIR/common.sh" ]]; then
    source "$OFFLINE_SCRIPT_DIR/common.sh"
fi

# Fallback для logging функций (если common.sh не загружен)
if ! declare -f log_info &>/dev/null; then
    RED='\033[0;31m'
    GREEN='\033[0;32m'
    YELLOW='\033[1;33m'
    BLUE='\033[0;34m'
    CYAN='\033[0;36m'
    NC='\033[0m'
    log_info()    { echo -e "${BLUE}[INFO]${NC} $1"; }
    log_success() { echo -e "${GREEN}[OK]${NC} $1"; }
    log_warning() { echo -e "${YELLOW}[WARN]${NC} $1"; }
    log_error()   { echo -e "${RED}[ERROR]${NC} $1" >&2; }
    log_step()    { echo -e "${CYAN}[STEP]${NC} $1"; }
fi

##############################################################################
# CONSTANTS
##############################################################################

OFFLINE_BUNDLE_VERSION="1.0.0"

# mise download URLs
MISE_BASE_URL="https://mise.jdx.dev"

# Runtime download URLs
GO_DOWNLOAD_URL="https://go.dev/dl"
NODEJS_DOWNLOAD_URL="https://nodejs.org/dist"

# Python prebuilt (indygreg/python-build-standalone)
PYTHON_STANDALONE_URL="https://github.com/indygreg/python-build-standalone/releases/download"

##############################################################################
# UTILITY FUNCTIONS
##############################################################################

# Определение платформы для offline bundle
_detect_offline_platform() {
    local arch=$(uname -m)
    local os=$(uname -s | tr '[:upper:]' '[:lower:]')

    case "$arch" in
        x86_64|amd64)
            arch="amd64"
            ;;
        aarch64|arm64)
            arch="arm64"
            ;;
        *)
            log_error "Неподдерживаемая архитектура: $arch"
            return 1
            ;;
    esac

    case "$os" in
        linux)
            echo "linux-$arch"
            ;;
        darwin)
            echo "macos-$arch"
            ;;
        *)
            log_error "Неподдерживаемая ОС: $os"
            return 1
            ;;
    esac
}

# Парсинг версий из .tool-versions
_parse_tool_versions() {
    local tool_versions_file="$1"
    local tool_name="$2"

    if [[ ! -f "$tool_versions_file" ]]; then
        log_error "Файл .tool-versions не найден: $tool_versions_file"
        return 1
    fi

    grep "^$tool_name " "$tool_versions_file" | awk '{print $2}' | head -1
}

# Получение полной версии Python для standalone build
# ВНИМАНИЕ: Fallback версии в этой функции периодически устаревают.
# При проблемах с загрузкой Python обновите версии в case-блоке ниже.
# Актуальные версии: https://github.com/indygreg/python-build-standalone/releases
_get_python_full_version() {
    local short_version="$1"  # e.g., "3.11"

    # Получаем последнюю patch версию через GitHub API
    local api_url="https://api.github.com/repos/indygreg/python-build-standalone/releases/latest"
    local release_info

    release_info=$(curl -sL "$api_url" 2>/dev/null)
    if [[ -z "$release_info" ]]; then
        # Fallback: используем известную версию
        # MAINTAINER NOTE: Обновляйте эти версии при выходе новых релизов Python
        # Последнее обновление: 2024-10
        log_verbose "GitHub API недоступен, используем fallback версии Python"
        case "$short_version" in
            3.11) echo "3.11.10" ;;
            3.12) echo "3.12.7" ;;
            3.13) echo "3.13.0" ;;
            *)    echo "${short_version}.0" ;;
        esac
        return
    fi

    # Ищем версию в assets (POSIX-совместимо, без grep -P)
    local version
    version=$(echo "$release_info" | grep -o "cpython-${short_version}\.[0-9]*" | head -1 | sed 's/cpython-//')

    if [[ -n "$version" ]]; then
        echo "$version"
    else
        echo "${short_version}.0"
    fi
}

# Расчет размера директории
_get_dir_size() {
    local dir="$1"
    du -sh "$dir" 2>/dev/null | awk '{print $1}'
}

# Подсчет файлов в директории
_count_files() {
    local dir="$1"
    local pattern="${2:-*}"
    find "$dir" -maxdepth 1 -name "$pattern" -type f 2>/dev/null | wc -l
}

# Проверка наличия утилит
_check_required_tools() {
    local -a missing=()

    for tool in curl wget tar sha256sum jq; do
        if ! command -v "$tool" &>/dev/null; then
            missing+=("$tool")
        fi
    done

    if [[ ${#missing[@]} -gt 0 ]]; then
        log_error "Отсутствуют необходимые утилиты: ${missing[*]}"
        log_info "Установите их и повторите попытку"
        return 1
    fi

    return 0
}

# Проверка доступа к интернету
_check_internet() {
    if curl -s --connect-timeout 5 --max-time 10 "https://mise.jdx.dev" >/dev/null 2>&1; then
        return 0
    fi
    return 1
}

##############################################################################
# DOWNLOAD FUNCTIONS
##############################################################################

# Скачивание mise binary
download_mise_binary() {
    local platform="$1"
    local output_dir="$2"

    log_info "Скачивание mise binary..."

    local mise_arch
    case "$platform" in
        linux-amd64)  mise_arch="linux-x64" ;;
        linux-arm64)  mise_arch="linux-arm64" ;;
        macos-amd64)  mise_arch="macos-x64" ;;
        macos-arm64)  mise_arch="macos-arm64" ;;
        *)
            log_error "Неподдерживаемая платформа для mise: $platform"
            return 1
            ;;
    esac

    local mise_url="${MISE_BASE_URL}/mise-latest-${mise_arch}"
    local output_file="$output_dir/mise/mise-${platform}"

    mkdir -p "$output_dir/mise"

    log_info "URL: $mise_url"
    if curl -fSL "$mise_url" -o "$output_file"; then
        chmod +x "$output_file"
        log_success "mise скачан: $output_file"

        # Получаем версию
        local version
        version=$("$output_file" --version 2>/dev/null | head -1 || echo "unknown")
        echo "$version" > "$output_dir/mise/version.txt"

        return 0
    else
        log_error "Не удалось скачать mise"
        return 1
    fi
}

# Скачивание Go runtime
download_go_runtime() {
    local version="$1"
    local platform="$2"
    local output_dir="$3"

    log_info "Скачивание Go $version..."

    local go_platform
    case "$platform" in
        linux-amd64)  go_platform="linux-amd64" ;;
        linux-arm64)  go_platform="linux-arm64" ;;
        macos-amd64)  go_platform="darwin-amd64" ;;
        macos-arm64)  go_platform="darwin-arm64" ;;
        *)
            log_error "Неподдерживаемая платформа для Go: $platform"
            return 1
            ;;
    esac

    local filename="go${version}.${go_platform}.tar.gz"
    local url="${GO_DOWNLOAD_URL}/${filename}"
    local output_file="$output_dir/runtimes/$filename"

    mkdir -p "$output_dir/runtimes"

    log_info "URL: $url"
    if curl -fSL "$url" -o "$output_file"; then
        log_success "Go скачан: $filename ($(du -h "$output_file" | cut -f1))"
        return 0
    else
        log_error "Не удалось скачать Go"
        return 1
    fi
}

# Скачивание Python runtime (prebuilt from indygreg)
download_python_runtime() {
    local version="$1"        # short version, e.g., "3.11"
    local platform="$2"
    local output_dir="$3"

    log_info "Скачивание Python $version (prebuilt)..."

    # Получаем полную версию
    local full_version
    full_version=$(_get_python_full_version "$version")
    log_info "Полная версия: $full_version"

    local python_platform arch_suffix
    case "$platform" in
        linux-amd64)
            python_platform="x86_64-unknown-linux-gnu"
            arch_suffix="x86_64"
            ;;
        linux-arm64)
            python_platform="aarch64-unknown-linux-gnu"
            arch_suffix="aarch64"
            ;;
        macos-amd64)
            python_platform="x86_64-apple-darwin"
            arch_suffix="x86_64"
            ;;
        macos-arm64)
            python_platform="aarch64-apple-darwin"
            arch_suffix="aarch64"
            ;;
        *)
            log_error "Неподдерживаемая платформа для Python: $platform"
            return 1
            ;;
    esac

    # Определяем release tag (формат: YYYYMMDD)
    # Пробуем получить последний релиз (POSIX-совместимо)
    local release_tag
    release_tag=$(curl -sL "https://api.github.com/repos/indygreg/python-build-standalone/releases/latest" 2>/dev/null | \
                  grep -o '"tag_name":[^"]*"[^"]*"' | sed 's/.*"\([^"]*\)"$/\1/' | head -1)
    release_tag="${release_tag:-20241016}"

    local filename="cpython-${full_version}+${release_tag}-${python_platform}-install_only_stripped.tar.gz"
    local url="${PYTHON_STANDALONE_URL}/${release_tag}/${filename}"
    local output_file="$output_dir/runtimes/$filename"

    mkdir -p "$output_dir/runtimes"

    log_info "URL: $url"
    if curl -fSL "$url" -o "$output_file" 2>/dev/null; then
        log_success "Python скачан: $filename ($(du -h "$output_file" | cut -f1))"
        return 0
    fi

    # Fallback: пробуем без stripped
    filename="cpython-${full_version}+${release_tag}-${python_platform}-install_only.tar.gz"
    url="${PYTHON_STANDALONE_URL}/${release_tag}/${filename}"

    log_info "Пробуем альтернативный URL: $url"
    if curl -fSL "$url" -o "$output_file" 2>/dev/null; then
        log_success "Python скачан: $filename ($(du -h "$output_file" | cut -f1))"
        return 0
    fi

    # Fallback 2: zstd compression
    filename="cpython-${full_version}+${release_tag}-${python_platform}-install_only.tar.zst"
    url="${PYTHON_STANDALONE_URL}/${release_tag}/${filename}"
    output_file="$output_dir/runtimes/$filename"

    log_info "Пробуем zstd: $url"
    if curl -fSL "$url" -o "$output_file" 2>/dev/null; then
        log_success "Python скачан: $filename ($(du -h "$output_file" | cut -f1))"
        return 0
    fi

    log_error "Не удалось скачать Python. Проверьте доступность релизов на GitHub."
    return 1
}

# Скачивание Node.js runtime
download_nodejs_runtime() {
    local version="$1"        # major version, e.g., "20"
    local platform="$2"
    local output_dir="$3"

    log_info "Скачивание Node.js $version..."

    # Получаем последнюю LTS версию для major версии
    local full_version
    full_version=$(curl -sL "https://nodejs.org/dist/index.json" 2>/dev/null | \
                   jq -r ".[] | select(.version | startswith(\"v${version}.\")) | .version" | \
                   head -1 | sed 's/v//')

    if [[ -z "$full_version" ]]; then
        log_warning "Не удалось определить последнюю версию, используем ${version}.0.0"
        full_version="${version}.0.0"
    fi

    log_info "Полная версия: $full_version"

    local node_platform
    case "$platform" in
        linux-amd64)  node_platform="linux-x64" ;;
        linux-arm64)  node_platform="linux-arm64" ;;
        macos-amd64)  node_platform="darwin-x64" ;;
        macos-arm64)  node_platform="darwin-arm64" ;;
        *)
            log_error "Неподдерживаемая платформа для Node.js: $platform"
            return 1
            ;;
    esac

    local filename="node-v${full_version}-${node_platform}.tar.gz"
    local url="${NODEJS_DOWNLOAD_URL}/v${full_version}/${filename}"
    local output_file="$output_dir/runtimes/$filename"

    mkdir -p "$output_dir/runtimes"

    log_info "URL: $url"
    if curl -fSL "$url" -o "$output_file"; then
        log_success "Node.js скачан: $filename ($(du -h "$output_file" | cut -f1))"
        return 0
    else
        log_error "Не удалось скачать Node.js"
        return 1
    fi
}

# Скачивание Python зависимостей
download_python_deps() {
    local requirements_file="$1"
    local output_dir="$2"
    local platform="$3"

    log_info "Скачивание Python зависимостей..."

    if [[ ! -f "$requirements_file" ]]; then
        log_warning "Файл requirements.txt не найден: $requirements_file"
        return 0
    fi

    local deps_dir="$output_dir/python-deps"
    mkdir -p "$deps_dir"

    # Определяем platform tag для pip
    local pip_platform
    case "$platform" in
        linux-amd64)  pip_platform="manylinux2014_x86_64" ;;
        linux-arm64)  pip_platform="manylinux2014_aarch64" ;;
        macos-amd64)  pip_platform="macosx_10_9_x86_64" ;;
        macos-arm64)  pip_platform="macosx_11_0_arm64" ;;
        *)            pip_platform="any" ;;
    esac

    # Определяем Python версию из .tool-versions
    local py_version=""
    local project_root="${PROJECT_ROOT:-$(cd "$OFFLINE_SCRIPT_DIR/../../.." && pwd)}"
    if [[ -f "$project_root/.tool-versions" ]]; then
        py_version=$(grep "^python " "$project_root/.tool-versions" 2>/dev/null | awk '{print $2}' | tr -d '.')
    fi
    py_version="${py_version:-311}"

    # Скачиваем wheels
    log_info "Platform: $pip_platform, Python: $py_version"

    if pip download \
        -r "$requirements_file" \
        --dest "$deps_dir" \
        --platform "$pip_platform" \
        --python-version "$py_version" \
        --only-binary=:all: \
        --no-deps \
        2>/dev/null; then
        log_success "Binary wheels скачаны"
    else
        log_warning "Некоторые binary wheels недоступны, скачиваем source..."
    fi

    # Скачиваем source distributions для оставшихся
    pip download \
        -r "$requirements_file" \
        --dest "$deps_dir" \
        --no-binary=:none: \
        2>/dev/null || true

    local count=$(_count_files "$deps_dir" "*.whl")
    count=$((count + $(_count_files "$deps_dir" "*.tar.gz")))

    log_success "Python зависимости: $count пакетов ($(du -sh "$deps_dir" | cut -f1))"
    return 0
}

# Скачивание npm зависимостей
download_npm_deps() {
    local package_json_dir="$1"
    local output_dir="$2"

    log_info "Скачивание npm зависимостей..."

    if [[ ! -f "$package_json_dir/package.json" ]]; then
        log_warning "Файл package.json не найден: $package_json_dir"
        return 0
    fi

    local deps_dir="$output_dir/npm-deps"
    mkdir -p "$deps_dir"

    # Метод 1: npm pack каждого пакета
    # Это создает tarballs для всех зависимостей

    # Используем subshell для безопасной работы с cd
    (
        cd "$package_json_dir" || exit 1

        # Устанавливаем зависимости в временную директорию
        local temp_dir=$(mktemp -d)
        local cache_dir="$deps_dir/.npm-cache"
        mkdir -p "$cache_dir"

        log_info "Устанавливаем зависимости с кешированием..."

        # npm ci с кастомным cache
        if npm ci --cache "$cache_dir" --prefer-offline 2>/dev/null; then
            log_info "Зависимости установлены, копируем cache..."

            # Копируем tarballs из cache
            find "$cache_dir" -name "*.tgz" -exec cp {} "$deps_dir/" \; 2>/dev/null || true

            # Альтернативно: pack каждый пакет из node_modules
            if [[ -d "node_modules" ]]; then
                log_info "Создаем tarballs из node_modules..."

                for pkg_dir in node_modules/*/; do
                    if [[ -f "$pkg_dir/package.json" ]]; then
                        local pkg_name=$(basename "$pkg_dir")
                        (cd "$pkg_dir" && npm pack --pack-destination "$deps_dir" 2>/dev/null) || true
                    fi
                done

                # Scoped packages
                for scope_dir in node_modules/@*/; do
                    if [[ -d "$scope_dir" ]]; then
                        for pkg_dir in "$scope_dir"/*/; do
                            if [[ -f "$pkg_dir/package.json" ]]; then
                                (cd "$pkg_dir" && npm pack --pack-destination "$deps_dir" 2>/dev/null) || true
                            fi
                        done
                    fi
                done
            fi
        else
            log_warning "npm ci не удался, пробуем npm install..."
            npm install --cache "$cache_dir" --prefer-offline 2>/dev/null || true
            find "$cache_dir" -name "*.tgz" -exec cp {} "$deps_dir/" \; 2>/dev/null || true
        fi

        # Cleanup
        rm -rf "$temp_dir"
        rm -rf "$deps_dir/.npm-cache"
    )

    local count=$(_count_files "$deps_dir" "*.tgz")
    log_success "npm зависимости: $count пакетов ($(du -sh "$deps_dir" | cut -f1))"

    return 0
}

##############################################################################
# MANIFEST & CHECKSUMS
##############################################################################

# Генерация manifest.json
generate_manifest() {
    local bundle_dir="$1"
    local platform="$2"
    local tool_versions_file="$3"

    log_info "Генерация manifest.json..."

    local go_version python_version nodejs_version mise_version
    go_version=$(_parse_tool_versions "$tool_versions_file" "go")
    python_version=$(_parse_tool_versions "$tool_versions_file" "python")
    nodejs_version=$(_parse_tool_versions "$tool_versions_file" "nodejs")
    mise_version=$(cat "$bundle_dir/mise/version.txt" 2>/dev/null || echo "unknown")

    # Находим файлы
    local go_file python_file nodejs_file mise_file
    go_file=$(find "$bundle_dir/runtimes" -name "go${go_version}*.tar.gz" -printf "%f\n" 2>/dev/null | head -1)
    python_file=$(find "$bundle_dir/runtimes" -name "cpython-${python_version}*" -printf "%f\n" 2>/dev/null | head -1)
    nodejs_file=$(find "$bundle_dir/runtimes" -name "node-v${nodejs_version}*" -printf "%f\n" 2>/dev/null | head -1)
    mise_file=$(find "$bundle_dir/mise" -name "mise-*" -printf "%f\n" 2>/dev/null | head -1)

    # Подсчет зависимостей
    local python_deps_count npm_deps_count
    python_deps_count=$(_count_files "$bundle_dir/python-deps" "*")
    npm_deps_count=$(_count_files "$bundle_dir/npm-deps" "*.tgz")

    # Генерируем JSON
    cat > "$bundle_dir/manifest.json" << EOF
{
  "version": "${OFFLINE_BUNDLE_VERSION}",
  "created_at": "$(date -Iseconds)",
  "platform": "${platform}",
  "tools": {
    "mise": {
      "version": "${mise_version}",
      "path": "mise/${mise_file}"
    }
  },
  "runtimes": {
    "go": {
      "version": "${go_version}",
      "path": "runtimes/${go_file}"
    },
    "python": {
      "version": "${python_version}",
      "path": "runtimes/${python_file}"
    },
    "nodejs": {
      "version": "${nodejs_version}",
      "path": "runtimes/${nodejs_file}"
    }
  },
  "python_deps": {
    "count": ${python_deps_count},
    "directory": "python-deps/"
  },
  "npm_deps": {
    "count": ${npm_deps_count},
    "directory": "npm-deps/"
  },
  "total_size": "$(du -sh "$bundle_dir" | cut -f1)"
}
EOF

    log_success "manifest.json создан"
}

# Генерация checksums
generate_checksums() {
    local bundle_dir="$1"

    log_info "Генерация checksums.sha256..."

    local checksums_file="$bundle_dir/checksums.sha256"

    # Удаляем старый файл если есть
    rm -f "$checksums_file"

    # Генерируем checksums для всех файлов (используем subshell)
    (
        cd "$bundle_dir" || exit 1
        find . -type f \
            ! -name "checksums.sha256" \
            ! -name ".gitignore" \
            -exec sha256sum {} \; | sort > "checksums.sha256"
    )

    local count=$(wc -l < "$checksums_file")
    log_success "checksums.sha256 создан ($count файлов)"
}

##############################################################################
# PREPARE PHASE (MAIN FUNCTION)
##############################################################################

prepare_offline_bundle() {
    local platform="${1:-}"
    local output_dir="${2:-$OFFLINE_SCRIPT_DIR/../offline-bundle}"
    local project_root="${3:-}"

    echo ""
    log_step "=== ПОДГОТОВКА OFFLINE BUNDLE ==="
    echo ""

    # Auto-detect platform if not specified
    if [[ -z "$platform" ]]; then
        platform=$(_detect_offline_platform)
    fi

    # Auto-detect project root
    if [[ -z "$project_root" ]]; then
        project_root=$(cd "$OFFLINE_SCRIPT_DIR/../../.." && pwd)
    fi

    local tool_versions_file="$project_root/.tool-versions"
    local requirements_file="$project_root/orchestrator/requirements.txt"
    local frontend_dir="$project_root/frontend"

    log_info "Платформа: $platform"
    log_info "Output: $output_dir"
    log_info "Проект: $project_root"
    echo ""

    # Проверки
    if ! _check_required_tools; then
        return 1
    fi

    if ! _check_internet; then
        log_error "Нет доступа к интернету. Для подготовки bundle требуется интернет."
        return 1
    fi

    if [[ ! -f "$tool_versions_file" ]]; then
        log_error "Файл .tool-versions не найден: $tool_versions_file"
        return 1
    fi

    # Создание структуры директорий
    log_info "Создание структуры директорий..."
    mkdir -p "$output_dir"/{mise,runtimes,python-deps,npm-deps}

    # Парсинг версий
    local go_version python_version nodejs_version
    go_version=$(_parse_tool_versions "$tool_versions_file" "go")
    python_version=$(_parse_tool_versions "$tool_versions_file" "python")
    nodejs_version=$(_parse_tool_versions "$tool_versions_file" "nodejs")

    log_info "Версии из .tool-versions:"
    log_info "  Go: $go_version"
    log_info "  Python: $python_version"
    log_info "  Node.js: $nodejs_version"
    echo ""

    # Скачивание компонентов
    local errors=0

    # 1. mise binary
    if ! download_mise_binary "$platform" "$output_dir"; then
        ((errors++))
    fi
    echo ""

    # 2. Go runtime
    if ! download_go_runtime "$go_version" "$platform" "$output_dir"; then
        ((errors++))
    fi
    echo ""

    # 3. Python runtime
    if ! download_python_runtime "$python_version" "$platform" "$output_dir"; then
        ((errors++))
    fi
    echo ""

    # 4. Node.js runtime
    if ! download_nodejs_runtime "$nodejs_version" "$platform" "$output_dir"; then
        ((errors++))
    fi
    echo ""

    # 5. Python dependencies
    if [[ -f "$requirements_file" ]]; then
        if ! download_python_deps "$requirements_file" "$output_dir" "$platform"; then
            log_warning "Ошибка при скачивании Python зависимостей"
        fi
        echo ""
    fi

    # 6. npm dependencies
    if [[ -d "$frontend_dir" ]]; then
        if ! download_npm_deps "$frontend_dir" "$output_dir"; then
            log_warning "Ошибка при скачивании npm зависимостей"
        fi
        echo ""
    fi

    # Генерация manifest и checksums
    generate_manifest "$output_dir" "$platform" "$tool_versions_file"
    generate_checksums "$output_dir"

    # Создание .gitignore
    cat > "$output_dir/.gitignore" << 'EOF'
# Offline bundle - не коммитить (большие файлы)
*
!.gitignore
!README.md
EOF

    # Итоговый отчет
    echo ""
    log_step "=== OFFLINE BUNDLE ГОТОВ ==="
    echo ""
    log_info "Директория: $output_dir"
    log_info "Размер: $(du -sh "$output_dir" | cut -f1)"
    log_info "Платформа: $platform"
    echo ""

    if [[ $errors -gt 0 ]]; then
        log_warning "Завершено с $errors ошибками"
        return 1
    fi

    log_success "Bundle готов для offline установки!"
    echo ""
    log_info "Для установки на целевой машине:"
    echo "  1. Скопируйте директорию $output_dir"
    echo "  2. Запустите: ./scripts/setup/install.sh --offline"
    echo ""

    return 0
}

##############################################################################
# INSTALL PHASE FUNCTIONS
##############################################################################

# Верификация bundle
verify_offline_bundle() {
    local bundle_dir="$1"

    log_info "Верификация offline bundle..."

    # Проверка manifest.json
    if [[ ! -f "$bundle_dir/manifest.json" ]]; then
        log_error "manifest.json не найден в $bundle_dir"
        return 1
    fi

    # Проверка checksums.sha256
    if [[ ! -f "$bundle_dir/checksums.sha256" ]]; then
        log_error "checksums.sha256 не найден в $bundle_dir"
        return 1
    fi

    # Верификация checksums (используем subshell для безопасного cd)
    log_info "Проверка контрольных сумм..."

    local verify_result
    verify_result=$(
        cd "$bundle_dir" || exit 1
        if sha256sum -c checksums.sha256 --quiet 2>/dev/null; then
            echo "OK"
        else
            sha256sum -c checksums.sha256 2>&1 | grep -i "FAILED" || true
            echo "FAILED"
        fi
    )

    if [[ "$verify_result" == "OK" ]]; then
        log_success "Все контрольные суммы совпадают"
        return 0
    else
        log_error "Контрольные суммы не совпадают!"
        echo "$verify_result" | grep -v "^FAILED$" || true
        return 1
    fi
}

# Установка mise из bundle
install_mise_offline() {
    local bundle_dir="$1"

    log_info "Установка mise из bundle..."

    local platform=$(_detect_offline_platform)
    local mise_binary="$bundle_dir/mise/mise-$platform"

    if [[ ! -f "$mise_binary" ]]; then
        # Пробуем найти любой mise binary
        mise_binary=$(find "$bundle_dir/mise" -name "mise-*" -type f | head -1)
    fi

    if [[ ! -f "$mise_binary" ]]; then
        log_error "mise binary не найден в bundle"
        return 1
    fi

    local install_dir="$HOME/.local/bin"
    mkdir -p "$install_dir"

    cp "$mise_binary" "$install_dir/mise"
    chmod +x "$install_dir/mise"

    # Добавляем в PATH если нужно
    if [[ ":$PATH:" != *":$install_dir:"* ]]; then
        export PATH="$install_dir:$PATH"
    fi

    if command -v mise &>/dev/null; then
        log_success "mise установлен: $(mise --version | head -1)"
        return 0
    else
        log_error "Не удалось установить mise"
        return 1
    fi
}

# Установка runtime'ов из bundle
install_runtimes_offline() {
    local bundle_dir="$1"
    local project_root="$2"

    log_info "Установка runtime'ов из bundle..."

    # Проверяем наличие mise
    if ! command -v mise &>/dev/null; then
        log_error "mise не установлен. Сначала выполните install_mise_offline"
        return 1
    fi

    # Активируем mise
    eval "$(mise activate bash 2>/dev/null)" || true

    # Trust проекту
    mise trust --all 2>/dev/null || true

    # Находим архивы
    local go_archive python_archive nodejs_archive
    go_archive=$(find "$bundle_dir/runtimes" -name "go*.tar.gz" | head -1)
    python_archive=$(find "$bundle_dir/runtimes" -name "cpython-*" | head -1)
    nodejs_archive=$(find "$bundle_dir/runtimes" -name "node-*.tar.gz" | head -1)

    # Устанавливаем через mise с локальными архивами
    # mise поддерживает установку из локальных файлов через file:// URI

    local errors=0

    if [[ -f "$go_archive" ]]; then
        log_info "Установка Go из $go_archive..."
        # Извлекаем версию из имени файла (POSIX-совместимо)
        local go_version
        go_version=$(basename "$go_archive" | sed -n 's/^go\([0-9.]*\).*/\1/p')

        # Создаем директорию для mise
        local mise_go_dir="$HOME/.local/share/mise/installs/go/$go_version"
        mkdir -p "$mise_go_dir"

        # Распаковываем
        tar -xzf "$go_archive" -C "$mise_go_dir" --strip-components=1

        if [[ -x "$mise_go_dir/bin/go" ]]; then
            log_success "Go $go_version установлен"
        else
            log_error "Ошибка установки Go"
            ((errors++))
        fi
    fi

    if [[ -f "$nodejs_archive" ]]; then
        log_info "Установка Node.js из $nodejs_archive..."
        # Извлекаем версию из имени файла (POSIX-совместимо)
        local nodejs_version
        nodejs_version=$(basename "$nodejs_archive" | sed -n 's/^node-v\([0-9.]*\).*/\1/p')

        local mise_nodejs_dir="$HOME/.local/share/mise/installs/node/$nodejs_version"
        mkdir -p "$mise_nodejs_dir"

        tar -xzf "$nodejs_archive" -C "$mise_nodejs_dir" --strip-components=1

        if [[ -x "$mise_nodejs_dir/bin/node" ]]; then
            log_success "Node.js $nodejs_version установлен"
        else
            log_error "Ошибка установки Node.js"
            ((errors++))
        fi
    fi

    if [[ -f "$python_archive" ]]; then
        log_info "Установка Python из $python_archive..."
        # Извлекаем версию из имени файла (POSIX-совместимо)
        local python_version
        python_version=$(basename "$python_archive" | sed -n 's/^cpython-\([0-9.]*\).*/\1/p')

        local mise_python_dir="$HOME/.local/share/mise/installs/python/$python_version"
        mkdir -p "$mise_python_dir"

        # Определяем тип архива
        if [[ "$python_archive" == *.zst ]]; then
            if command -v zstd &>/dev/null; then
                zstd -d "$python_archive" -c | tar -xf - -C "$mise_python_dir" --strip-components=1
            else
                log_error "zstd не установлен. Установите: pacman -S zstd"
                ((errors++))
            fi
        else
            tar -xzf "$python_archive" -C "$mise_python_dir" --strip-components=1
        fi

        if [[ -x "$mise_python_dir/bin/python3" ]]; then
            log_success "Python $python_version установлен"
        else
            log_error "Ошибка установки Python"
            ((errors++))
        fi
    fi

    # Обновляем mise shims
    mise reshim 2>/dev/null || true

    return $errors
}

# Установка Python зависимостей из bundle
install_python_deps_offline() {
    local bundle_dir="$1"
    local project_root="$2"

    log_info "Установка Python зависимостей из bundle..."

    local deps_dir="$bundle_dir/python-deps"
    local requirements_file="$project_root/orchestrator/requirements.txt"
    local venv_dir="$project_root/orchestrator/venv"

    if [[ ! -d "$deps_dir" ]] || [[ -z "$(ls -A "$deps_dir" 2>/dev/null)" ]]; then
        log_warning "Python зависимости не найдены в bundle"
        return 0
    fi

    if [[ ! -f "$requirements_file" ]]; then
        log_warning "requirements.txt не найден"
        return 0
    fi

    # Активируем mise
    eval "$(mise activate bash 2>/dev/null)" || true

    # Создаем venv если нужно
    if [[ ! -d "$venv_dir" ]]; then
        log_info "Создание virtualenv..."
        python -m venv "$venv_dir"
    fi

    # Активируем venv
    local activate_script="$venv_dir/bin/activate"
    [[ -f "$venv_dir/Scripts/activate" ]] && activate_script="$venv_dir/Scripts/activate"
    source "$activate_script"

    # Устанавливаем зависимости
    log_info "Установка пакетов из локального кеша..."
    pip install --no-index --find-links="$deps_dir" -r "$requirements_file" -q

    deactivate

    log_success "Python зависимости установлены"
    return 0
}

# Установка npm зависимостей из bundle
install_npm_deps_offline() {
    local bundle_dir="$1"
    local project_root="$2"

    log_info "Установка npm зависимостей из bundle..."

    local deps_dir="$bundle_dir/npm-deps"
    local frontend_dir="$project_root/frontend"

    if [[ ! -d "$deps_dir" ]] || [[ -z "$(ls -A "$deps_dir" 2>/dev/null)" ]]; then
        log_warning "npm зависимости не найдены в bundle"
        return 0
    fi

    if [[ ! -f "$frontend_dir/package.json" ]]; then
        log_warning "package.json не найден"
        return 0
    fi

    # Активируем mise
    eval "$(mise activate bash 2>/dev/null)" || true

    # Создаем локальный npm cache из tarballs
    local cache_dir="$deps_dir/.npm-cache-temp"
    mkdir -p "$cache_dir"

    # Копируем tarballs в cache
    for tarball in "$deps_dir"/*.tgz; do
        if [[ -f "$tarball" ]]; then
            cp "$tarball" "$cache_dir/"
        fi
    done

    # Устанавливаем с offline режимом (используем subshell)
    log_info "Установка пакетов из локального кеша..."
    (
        cd "$frontend_dir" || exit 1
        npm install --offline --cache "$cache_dir" 2>/dev/null || \
        npm install --prefer-offline --cache "$cache_dir" 2>/dev/null || \
        log_warning "Некоторые пакеты могут быть недоступны offline"
    )

    # Cleanup
    rm -rf "$cache_dir"

    log_success "npm зависимости установлены"
    return 0
}

##############################################################################
# INSTALL PHASE (MAIN FUNCTION)
##############################################################################

install_from_offline_bundle() {
    local bundle_dir="${1:-$OFFLINE_SCRIPT_DIR/../offline-bundle}"
    local skip_verify="${2:-false}"
    local project_root="${3:-}"

    echo ""
    log_step "=== УСТАНОВКА ИЗ OFFLINE BUNDLE ==="
    echo ""

    # Проверка существования bundle
    if [[ ! -d "$bundle_dir" ]]; then
        log_error "Offline bundle не найден: $bundle_dir"
        return 1
    fi

    # Auto-detect project root
    if [[ -z "$project_root" ]]; then
        project_root=$(cd "$OFFLINE_SCRIPT_DIR/../../.." && pwd)
    fi

    log_info "Bundle: $bundle_dir"
    log_info "Проект: $project_root"
    echo ""

    # Верификация (если не пропущена)
    if [[ "$skip_verify" != "true" ]] && [[ "$skip_verify" != "--skip-verify" ]]; then
        if ! verify_offline_bundle "$bundle_dir"; then
            log_error "Верификация bundle не пройдена"
            return 1
        fi
        echo ""
    else
        log_warning "Верификация пропущена (--skip-verify)"
        echo ""
    fi

    # Показываем информацию из manifest
    if [[ -f "$bundle_dir/manifest.json" ]]; then
        log_info "Bundle info:"
        jq -r '
            "  Версия: \(.version)",
            "  Создан: \(.created_at)",
            "  Платформа: \(.platform)",
            "  Размер: \(.total_size)"
        ' "$bundle_dir/manifest.json" 2>/dev/null || true
        echo ""
    fi

    local errors=0

    # 1. Установка mise
    if ! install_mise_offline "$bundle_dir"; then
        ((errors++))
    fi
    echo ""

    # 2. Установка runtime'ов
    if ! install_runtimes_offline "$bundle_dir" "$project_root"; then
        ((errors++))
    fi
    echo ""

    # 3. Установка Python зависимостей
    if ! install_python_deps_offline "$bundle_dir" "$project_root"; then
        log_warning "Ошибка при установке Python зависимостей"
    fi
    echo ""

    # 4. Установка npm зависимостей
    if ! install_npm_deps_offline "$bundle_dir" "$project_root"; then
        log_warning "Ошибка при установке npm зависимостей"
    fi
    echo ""

    # Итоговый отчет
    log_step "=== OFFLINE УСТАНОВКА ЗАВЕРШЕНА ==="
    echo ""

    if [[ $errors -gt 0 ]]; then
        log_warning "Завершено с $errors ошибками"
        return 1
    fi

    log_success "Все компоненты установлены!"
    echo ""
    log_info "Следующие шаги:"
    echo "  1. Перезапустите терминал или выполните: source ~/.bashrc"
    echo "  2. Проверьте версии: mise current"
    echo "  3. Запустите инфраструктуру: docker compose up -d"
    echo ""

    return 0
}

##############################################################################
# CLI INTERFACE
##############################################################################

# Показать справку
_offline_show_help() {
    cat << 'EOF'
Offline Module - CommandCenter1C

Подготовка bundle (требует интернет):
  source scripts/setup/lib/offline.sh
  prepare_offline_bundle [platform] [output_dir]

  Параметры:
    platform    - linux-amd64 | linux-arm64 | macos-amd64 | macos-arm64
                  (по умолчанию: автоопределение)
    output_dir  - директория для bundle
                  (по умолчанию: scripts/setup/offline-bundle)

Установка из bundle (offline):
  source scripts/setup/lib/offline.sh
  install_from_offline_bundle [bundle_dir] [--skip-verify]

  Параметры:
    bundle_dir    - директория с bundle
    --skip-verify - пропустить проверку checksums

Примеры:
  # Подготовка bundle для linux-amd64
  prepare_offline_bundle

  # Подготовка для ARM64
  prepare_offline_bundle linux-arm64 /path/to/bundle

  # Установка из bundle
  install_from_offline_bundle

  # Установка без верификации
  install_from_offline_bundle ./offline-bundle --skip-verify

Отдельные функции:
  verify_offline_bundle <bundle_dir>     - проверить checksums
  download_mise_binary <platform> <dir>  - скачать mise
  download_go_runtime <ver> <plat> <dir> - скачать Go
  download_python_runtime <ver> <plat>   - скачать Python
  download_nodejs_runtime <ver> <plat>   - скачать Node.js
  download_python_deps <req.txt> <dir>   - скачать pip зависимости
  download_npm_deps <pkg_dir> <dir>      - скачать npm зависимости
EOF
}

# Если скрипт запущен напрямую (не sourced)
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    case "${1:-}" in
        prepare)
            shift
            prepare_offline_bundle "$@"
            ;;
        install)
            shift
            install_from_offline_bundle "$@"
            ;;
        verify)
            shift
            verify_offline_bundle "${1:-.}"
            ;;
        --help|-h|help)
            _offline_show_help
            ;;
        *)
            echo "Usage: $0 {prepare|install|verify|help}"
            echo "Run '$0 help' for more information"
            exit 1
            ;;
    esac
fi
