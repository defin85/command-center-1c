#!/bin/bash

##############################################################################
# Install Prometheus Exporters for PostgreSQL and Redis
##############################################################################
# For Arch Linux (WSL)
# Run with: sudo ./install-exporters.sh
##############################################################################

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
SYSTEMD_DIR="$PROJECT_ROOT/infrastructure/systemd"

echo "=== Installing Prometheus Exporters ==="

# Check if running as root for systemd operations
if [ "$EUID" -ne 0 ]; then
    echo "Note: Run with sudo to install systemd services"
    echo "      Without sudo, only checking availability"
fi

# Function to check if package is installed
check_package() {
    if command -v "$1" &> /dev/null; then
        echo "[OK] $1 is installed: $(which $1)"
        return 0
    else
        echo "[MISSING] $1 not found"
        return 1
    fi
}

# Check for postgres_exporter
echo ""
echo "--- PostgreSQL Exporter ---"
if ! check_package postgres_exporter; then
    echo "Install with: yay -S prometheus-postgres-exporter"
    echo "Or download from: https://github.com/prometheus-community/postgres_exporter/releases"
fi

# Check for redis_exporter
echo ""
echo "--- Redis Exporter ---"
if ! check_package redis_exporter; then
    echo "Install with: yay -S prometheus-redis-exporter"
    echo "Or: go install github.com/oliver006/redis_exporter@latest"
fi

# Install systemd services if running as root
if [ "$EUID" -eq 0 ]; then
    echo ""
    echo "--- Installing systemd services ---"

    # Copy service files
    if [ -f "$SYSTEMD_DIR/postgres-exporter.service" ]; then
        cp "$SYSTEMD_DIR/postgres-exporter.service" /etc/systemd/system/
        echo "[OK] Installed postgres-exporter.service"
    fi

    if [ -f "$SYSTEMD_DIR/redis-exporter.service" ]; then
        cp "$SYSTEMD_DIR/redis-exporter.service" /etc/systemd/system/
        echo "[OK] Installed redis-exporter.service"
    fi

    # Reload systemd
    systemctl daemon-reload
    echo "[OK] systemd daemon reloaded"

    echo ""
    echo "To enable and start services:"
    echo "  sudo systemctl enable --now postgres-exporter"
    echo "  sudo systemctl enable --now redis-exporter"
fi

echo ""
echo "=== Setup complete ==="
echo ""
echo "Manual verification:"
echo "  curl http://localhost:9187/metrics  # PostgreSQL"
echo "  curl http://localhost:9121/metrics  # Redis"
