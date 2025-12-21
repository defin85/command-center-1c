#!/bin/bash

##############################################################################
# CommandCenter1C - Build and Start All Services
##############################################################################
# Универсальный скрипт для:
# 1. Сборки всех Go сервисов
# 2. Запуска всех сервисов локально
#
# Usage:
#   ./scripts/dev/build-and-start.sh           # Build + Start
#   ./scripts/dev/build-and-start.sh --clean   # Clean + Build + Start
##############################################################################

set -e

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

# Цвета для вывода
BLUE='\033[0;34m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

CLEAN_BINARIES=false

# Парсинг аргументов
for arg in "$@"; do
    case $arg in
        --clean)
            CLEAN_BINARIES=true
            ;;
        --help)
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --clean    Очистить бинарники перед сборкой"
            echo "  --help     Показать эту справку"
            echo ""
            exit 0
            ;;
        *)
            echo -e "${RED}Unknown option: $arg${NC}"
            exit 1
            ;;
    esac
done

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}  CommandCenter1C${NC}"
echo -e "${BLUE}  Build + Start All Services${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

##############################################################################
# Фаза 1: Сборка Go сервисов
##############################################################################
echo -e "${BLUE}[1/2] Building Go Services${NC}"
echo ""

if [ "$CLEAN_BINARIES" = true ]; then
    echo -e "${YELLOW}Cleaning old binaries...${NC}"
    rm -rf "$PROJECT_ROOT/bin"
    echo -e "${GREEN}✓ Binaries cleaned${NC}"
    echo ""
fi

# Проверить наличие build.sh
if [ -f "$PROJECT_ROOT/scripts/build.sh" ]; then
    "$PROJECT_ROOT/scripts/build.sh"
else
    # Fallback на прямую сборку если build.sh отсутствует
    echo -e "${YELLOW}Warning: scripts/build.sh not found, using direct go build${NC}"

    mkdir -p "$PROJECT_ROOT/bin"

    cd "$PROJECT_ROOT/go-services/api-gateway"
    go build -o "$PROJECT_ROOT/bin/cc1c-api-gateway.exe" cmd/main.go

    cd "$PROJECT_ROOT/go-services/worker"
    go build -o "$PROJECT_ROOT/bin/cc1c-worker.exe" cmd/main.go


    echo -e "${GREEN}✓ All binaries built${NC}"
fi

echo ""

##############################################################################
# Фаза 2: Запуск всех сервисов
##############################################################################
echo -e "${BLUE}[2/2] Starting All Services${NC}"
echo ""

cd "$PROJECT_ROOT"
"$PROJECT_ROOT/scripts/dev/start-all.sh"

##############################################################################
# Финал
##############################################################################
echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  ✓ Build and Start Completed!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo -e "${BLUE}Services are running with compiled binaries from:${NC}"
echo -e "  $PROJECT_ROOT/bin/"
echo ""
echo -e "${YELLOW}Next steps:${NC}"
echo -e "  Check health:   ${GREEN}./scripts/dev/health-check.sh${NC}"
echo -e "  View logs:      ${GREEN}./scripts/dev/logs.sh <service>${NC}"
echo -e "  Stop all:       ${GREEN}./scripts/dev/stop-all.sh${NC}"
echo ""
