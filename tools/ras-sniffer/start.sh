#!/bin/bash
# Запуск RAS Protocol Proxy Sniffer

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Цвета для вывода
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${GREEN}Starting RAS Protocol Proxy Sniffer...${NC}"

# Проверить что бинарник существует
if [ ! -f "ras-sniffer.exe" ]; then
    echo -e "${YELLOW}Binary not found. Building...${NC}"
    go build -o ras-sniffer.exe main.go
    echo -e "${GREEN}Build complete${NC}"
fi

# Проверить что порт свободен
if netstat -ano | grep -q ":1546"; then
    echo -e "${RED}ERROR: Port 1546 already in use!${NC}"
    echo "Kill the existing process first:"
    echo "  netstat -ano | findstr :1546"
    exit 1
fi

# Создать чистый лог файл
rm -f ras-protocol-capture.log
touch ras-protocol-capture.log

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  RAS Protocol Proxy Sniffer${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo "Proxy: localhost:1546"
echo "Target: localhost:1545"
echo "Log: $(pwd)/ras-protocol-capture.log"
echo ""
echo -e "${YELLOW}Usage in another terminal:${NC}"
echo "  rac.exe cluster list localhost:1546"
echo ""
echo -e "${YELLOW}View log in real-time:${NC}"
echo "  tail -f $(pwd)/ras-protocol-capture.log"
echo ""
echo -e "${GREEN}Press Ctrl+C to stop${NC}"
echo ""

# Запустить proxy
./ras-sniffer.exe
