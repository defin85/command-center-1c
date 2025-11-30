#!/bin/bash
# Debug Go service with Delve

set -e

SERVICE=$1
PORT=${2:-2345}  # Default port 2345

if [ -z "$SERVICE" ]; then
    echo "Usage: ./scripts/dev/debug-service.sh <service-name> [port]"
    echo ""
    echo "Available services:"
    echo "  api-gateway   (default port: 2345)"
    echo "  worker        (default port: 2346)"
    echo "  ras-adapter   (default port: 2347)"
    echo "  batch-service (default port: 2348)"
    echo ""
    echo "Example:"
    echo "  ./scripts/dev/debug-service.sh api-gateway 2345"
    exit 1
fi

# Set default ports based on service
case $SERVICE in
    api-gateway)   PORT=${2:-2345} ;;
    worker)        PORT=${2:-2346} ;;
    ras-adapter)   PORT=${2:-2347} ;;
    batch-service) PORT=${2:-2348} ;;
    *)
        echo "❌ Unknown service: $SERVICE"
        echo "Available: api-gateway, worker, ras-adapter, batch-service"
        exit 1
        ;;
esac

SERVICE_PATH="go-services/$SERVICE"

if [ ! -d "$SERVICE_PATH" ]; then
    echo "❌ Service directory not found: $SERVICE_PATH"
    exit 1
fi

if [ ! -f "$SERVICE_PATH/cmd/main.go" ]; then
    echo "❌ main.go not found: $SERVICE_PATH/cmd/main.go"
    exit 1
fi

echo "=========================================="
echo "  Debugging $SERVICE"
echo "=========================================="
echo ""
echo "🐛 Запускаем Delve debugger..."
echo "   Service: $SERVICE"
echo "   Port: $PORT"
echo "   Path: $SERVICE_PATH"
echo ""
echo "📝 Теперь используй MCP tools для отладки:"
echo "   1. start_debugger(port=$PORT)"
echo "   2. debug_program(path=\"$(pwd)/$SERVICE_PATH/cmd/main.go\")"
echo "   3. set_breakpoints(...)"
echo "   4. continue() / next() / step_in() / ..."
echo ""
echo "Для остановки нажми Ctrl+C"
echo ""

cd "$SERVICE_PATH"
dlv debug --headless --listen=:$PORT --api-version=2 --accept-multiclient cmd/main.go
