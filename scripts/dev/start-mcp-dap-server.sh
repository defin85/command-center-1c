#!/bin/bash
# Start MCP DAP Server for AI-powered debugging

set -e

MCP_DAP_SERVER_PATH="/c/Users/Egor/Documents/GitHub/mcp-dap-server"
PID_FILE="pids/mcp-dap-server.pid"
PORT=8080

echo "=========================================="
echo "  Starting MCP DAP Server"
echo "=========================================="

# Check if already running
if [ -f "$PID_FILE" ]; then
    PID=$(cat "$PID_FILE")
    if ps -p "$PID" > /dev/null 2>&1; then
        echo "⚠️  MCP DAP Server уже запущен (PID: $PID)"
        echo "   Для перезапуска выполните: ./scripts/dev/stop-mcp-dap-server.sh"
        exit 0
    else
        echo "⚠️  Найден старый PID файл, удаляем..."
        rm -f "$PID_FILE"
    fi
fi

# Check if binary exists
if [ ! -f "$MCP_DAP_SERVER_PATH/bin/mcp-dap-server" ]; then
    echo "❌ Бинарник не найден: $MCP_DAP_SERVER_PATH/bin/mcp-dap-server"
    echo "   Соберите его командой: cd $MCP_DAP_SERVER_PATH && go build -o bin/mcp-dap-server"
    exit 1
fi

# Start server
echo "🚀 Запускаем MCP DAP Server на порту $PORT..."
cd "$MCP_DAP_SERVER_PATH"
nohup ./bin/mcp-dap-server > /c/1CProject/command-center-1c/logs/mcp-dap-server.log 2>&1 &
SERVER_PID=$!

# Save PID
mkdir -p /c/1CProject/command-center-1c/pids
echo $SERVER_PID > "/c/1CProject/command-center-1c/$PID_FILE"

# Wait for server to start
echo "⏳ Ждём запуска сервера..."
sleep 2

# Check if server is responding
if curl -s http://localhost:$PORT/health > /dev/null 2>&1; then
    echo "✅ MCP DAP Server успешно запущен!"
    echo "   PID: $SERVER_PID"
    echo "   URL: http://localhost:$PORT"
    echo "   Logs: logs/mcp-dap-server.log"
    echo ""
    echo "Подключено к Claude Code через: claude mcp add --transport sse mcp-dap-server http://localhost:$PORT"
else
    echo "❌ Не удалось запустить MCP DAP Server"
    echo "   Проверьте логи: tail -f logs/mcp-dap-server.log"
    kill $SERVER_PID 2>/dev/null || true
    rm -f "$PID_FILE"
    exit 1
fi
