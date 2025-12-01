#!/bin/bash
# Fix routing for RAS server (bypass VPN tunnel)
# Run with: wsl.exe -u root -e /path/to/fix-wsl-routing.sh

# Windows host IP (where RAS is running)
RAS_HOST="192.168.0.27"
# WSL gateway (usually x.x.16.1 for WSL2)
WSL_GATEWAY="172.20.16.1"

# Add direct route bypassing tun0
ip route add ${RAS_HOST}/32 via ${WSL_GATEWAY} dev eth0 2>/dev/null || true
echo "Route to ${RAS_HOST} via ${WSL_GATEWAY} configured"
