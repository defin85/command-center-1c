#!/bin/bash
# Stop MCP DAP Server

set -e

PID_FILE="pids/mcp-dap-server.pid"

echo "=========================================="
echo "  Stopping MCP DAP Server"
echo "=========================================="

if [ ! -f "$PID_FILE" ]; then
    echo "⚠️  PID файл не найден, сервер не запущен"
    exit 0
fi

PID=$(cat "$PID_FILE")

if ps -p "$PID" > /dev/null 2>&1; then
    echo "🛑 Останавливаем MCP DAP Server (PID: $PID)..."
    kill $PID

    # Wait for process to stop
    for i in {1..10}; do
        if ! ps -p "$PID" > /dev/null 2>&1; then
            echo "✅ MCP DAP Server остановлен"
            rm -f "$PID_FILE"
            exit 0
        fi
        sleep 0.5
    done

    # Force kill if still running
    echo "⚠️  Процесс не останавливается, принудительное завершение..."
    kill -9 $PID 2>/dev/null || true
    rm -f "$PID_FILE"
    echo "✅ MCP DAP Server остановлен (force)"
else
    echo "⚠️  Процесс с PID $PID не найден"
    rm -f "$PID_FILE"
fi
