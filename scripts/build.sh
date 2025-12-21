#!/bin/bash

##############################################################################
# CommandCenter1C - Go Services Build Script
##############################################################################
#
# Универсальный скрипт сборки всех Go микросервисов с поддержкой:
# - Версионирования через git tags
# - Cross-compilation для Linux/Windows
# - Параллельной сборки
# - Цветного вывода
#
# Использование:
#   ./scripts/build.sh                    # Собрать все для текущей ОС
#   ./scripts/build.sh --service=worker   # Собрать только worker
#   ./scripts/build.sh --os=linux         # Cross-compile для Linux
#   ./scripts/build.sh --parallel         # Параллельная сборка
#   ./scripts/build.sh --help             # Показать помощь
#
##############################################################################

set -e

# Цвета для вывода
BLUE='\033[0;34m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Директории
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
BIN_DIR="$PROJECT_ROOT/bin"
GO_SERVICES_DIR="$PROJECT_ROOT/go-services"

# Build metadata
VERSION=$(git describe --tags --always --dirty 2>/dev/null || echo "dev")
COMMIT=$(git rev-parse --short HEAD 2>/dev/null || echo "unknown")
BUILD_TIME=$(date -u '+%Y-%m-%d_%H:%M:%S')

# Default параметры
TARGET_OS="${GOOS:-$(go env GOOS)}"
TARGET_ARCH="${GOARCH:-$(go env GOARCH)}"
BUILD_PARALLEL=false
SPECIFIC_SERVICE=""

# Список всех сервисов
declare -A SERVICES
SERVICES[api-gateway]="API Gateway"
SERVICES[worker]="Worker"

##############################################################################
# Функции
##############################################################################

show_help() {
    echo -e "${BLUE}CommandCenter1C - Go Services Build Script${NC}"
    echo ""
    echo "Usage: $0 [OPTIONS]"
    echo ""
    echo "Options:"
    echo "  --service=<name>    Собрать только указанный сервис (api-gateway, worker)"
    echo "  --os=<os>           Целевая ОС (linux, windows, darwin). Default: $(go env GOOS)"
    echo "  --arch=<arch>       Целевая архитектура (amd64, arm64). Default: $(go env GOARCH)"
    echo "  --parallel          Собрать все сервисы параллельно"
    echo "  --clean             Очистить bin/ перед сборкой"
    echo "  --help              Показать эту справку"
    echo ""
    echo "Examples:"
    echo "  $0                           # Собрать все для текущей ОС"
    echo "  $0 --service=worker          # Собрать только worker"
    echo "  $0 --os=linux --arch=amd64   # Cross-compile для Linux amd64"
    echo "  $0 --parallel                # Параллельная сборка всех сервисов"
    echo "  $0 --clean --parallel        # Очистить + собрать параллельно"
    echo ""
}

clean_binaries() {
    echo -e "${YELLOW}Cleaning binaries...${NC}"
    rm -rf "$BIN_DIR"
    echo -e "${GREEN}✓ Binaries cleaned${NC}"
    echo ""
}

get_binary_name() {
    local service=$1
    local bin_ext=""

    if [ "$TARGET_OS" = "windows" ]; then
        bin_ext=".exe"
    fi

    echo "cc1c-${service}${bin_ext}"
}

build_service() {
    local service=$1
    local service_name=${SERVICES[$service]}
    local service_dir="$GO_SERVICES_DIR/$service"
    local binary_name=$(get_binary_name "$service")
    local output_path="$BIN_DIR/$binary_name"

    if [ ! -d "$service_dir" ]; then
        echo -e "${RED}✗ Service directory not found: $service_dir${NC}"
        return 1
    fi

    if [ ! -f "$service_dir/cmd/main.go" ]; then
        echo -e "${RED}✗ Main file not found: $service_dir/cmd/main.go${NC}"
        return 1
    fi

    echo -e "${BLUE}Building $service_name...${NC}"
    echo "  Service: $service"
    echo "  Output: $binary_name"
    echo "  OS/Arch: $TARGET_OS/$TARGET_ARCH"
    echo "  Version: $VERSION"
    echo "  Commit: $COMMIT"

    # Создать bin/ если не существует
    mkdir -p "$BIN_DIR"

    # Build с version injection
    LDFLAGS="-X main.Version=$VERSION -X main.Commit=$COMMIT -X main.BuildTime=$BUILD_TIME"

    # Save current directory and return to it after build
    local current_dir=$(pwd)

    cd "$service_dir"
    GOOS=$TARGET_OS GOARCH=$TARGET_ARCH go build \
        -ldflags "$LDFLAGS" \
        -o "$output_path" \
        cmd/main.go

    local build_status=$?

    # Return to original directory
    cd "$current_dir"

    if [ $build_status -eq 0 ]; then
        local size=$(du -h "$output_path" | cut -f1)
        echo -e "${GREEN}✓ $service_name built successfully ($size)${NC}"
        echo ""
        return 0
    else
        echo -e "${RED}✗ Failed to build $service_name${NC}"
        echo ""
        return 1
    fi
}

build_all_sequential() {
    echo -e "${BLUE}========================================${NC}"
    echo -e "${BLUE}  Building All Services (Sequential)${NC}"
    echo -e "${BLUE}========================================${NC}"
    echo ""

    local count=0
    local total=${#SERVICES[@]}
    local failed=0

    # Temporarily disable exit on error for loop
    set +e

    for service in "${!SERVICES[@]}"; do
        ((count++))
        echo -e "${BLUE}[$count/$total]${NC}"

        build_service "$service"
        if [ $? -ne 0 ]; then
            ((failed++))
        fi
    done

    # Re-enable exit on error
    set -e

    echo -e "${BLUE}========================================${NC}"
    echo -e "${BLUE}  Build Summary${NC}"
    echo -e "${BLUE}========================================${NC}"
    echo ""
    echo "Total: $total"
    echo "Success: $((total - failed))"
    echo "Failed: $failed"
    echo ""

    if [ $failed -eq 0 ]; then
        echo -e "${GREEN}✓ All services built successfully!${NC}"
        echo ""
        echo "Binaries in $BIN_DIR:"
        ls -lh "$BIN_DIR"/cc1c-* 2>/dev/null || true
        return 0
    else
        echo -e "${RED}✗ Some services failed to build${NC}"
        return 1
    fi
}

build_all_parallel() {
    echo -e "${BLUE}========================================${NC}"
    echo -e "${BLUE}  Building All Services (Parallel)${NC}"
    echo -e "${BLUE}========================================${NC}"
    echo ""

    local pids=()
    local results=()

    # Temporarily disable exit on error for parallel builds
    set +e

    for service in "${!SERVICES[@]}"; do
        build_service "$service" &
        pids+=($!)
    done

    # Ждать завершения всех
    local failed=0
    for pid in "${pids[@]}"; do
        wait $pid
        if [ $? -ne 0 ]; then
            ((failed++))
        fi
    done

    # Re-enable exit on error
    set -e

    echo -e "${BLUE}========================================${NC}"
    echo -e "${BLUE}  Build Summary${NC}"
    echo -e "${BLUE}========================================${NC}"
    echo ""

    local total=${#SERVICES[@]}
    echo "Total: $total"
    echo "Success: $((total - failed))"
    echo "Failed: $failed"
    echo ""

    if [ $failed -eq 0 ]; then
        echo -e "${GREEN}✓ All services built successfully!${NC}"
        echo ""
        echo "Binaries in $BIN_DIR:"
        ls -lh "$BIN_DIR"/cc1c-* 2>/dev/null || true
        return 0
    else
        echo -e "${RED}✗ Some services failed to build${NC}"
        return 1
    fi
}

##############################################################################
# Парсинг аргументов
##############################################################################

CLEAN=false

for arg in "$@"; do
    case $arg in
        --help)
            show_help
            exit 0
            ;;
        --service=*)
            SPECIFIC_SERVICE="${arg#*=}"
            ;;
        --os=*)
            TARGET_OS="${arg#*=}"
            ;;
        --arch=*)
            TARGET_ARCH="${arg#*=}"
            ;;
        --parallel)
            BUILD_PARALLEL=true
            ;;
        --clean)
            CLEAN=true
            ;;
        *)
            echo -e "${RED}Unknown option: $arg${NC}"
            echo ""
            show_help
            exit 1
            ;;
    esac
done

##############################################################################
# Основная логика
##############################################################################

# Проверить что Go установлен
if ! command -v go &> /dev/null; then
    echo -e "${RED}Error: Go is not installed or not in PATH${NC}"
    exit 1
fi

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}  CommandCenter1C - Go Build${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""
echo "Go version: $(go version)"
echo "Target: $TARGET_OS/$TARGET_ARCH"
echo "Version: $VERSION"
echo "Commit: $COMMIT"
echo "Build time: $BUILD_TIME"
echo ""

# Очистка если требуется
if [ "$CLEAN" = true ]; then
    clean_binaries
fi

# Сборка
if [ -n "$SPECIFIC_SERVICE" ]; then
    # Один сервис
    if [ -z "${SERVICES[$SPECIFIC_SERVICE]}" ]; then
        echo -e "${RED}Error: Unknown service '$SPECIFIC_SERVICE'${NC}"
        echo ""
        echo "Available services:"
        for service in "${!SERVICES[@]}"; do
            echo "  - $service (${SERVICES[$service]})"
        done
        exit 1
    fi

    build_service "$SPECIFIC_SERVICE"
    exit $?
elif [ "$BUILD_PARALLEL" = true ]; then
    # Все параллельно
    build_all_parallel
    exit $?
else
    # Все последовательно
    build_all_sequential
    exit $?
fi
