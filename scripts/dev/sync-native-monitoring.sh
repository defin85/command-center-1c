#!/bin/bash

##############################################################################
# CommandCenter1C - Sync Native Monitoring Config
##############################################################################
# Best-effort sync of repository monitoring configs into system paths for
# native mode (USE_DOCKER=false):
# - Prometheus config (/etc/prometheus/prometheus.yml)
# - Blackbox exporter config (/etc/blackbox_exporter/config.yml)
# - Prometheus blackbox targets (/etc/prometheus/targets/blackbox_tcp.yml)
#
# This exists because native Prometheus reads /etc/*, while docker mode uses
# bind-mounts from the repo.
##############################################################################

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

source "$PROJECT_ROOT/scripts/lib/init.sh"

cd "$PROJECT_ROOT"
load_env_file

if is_docker_mode; then
  log_info "Docker mode: native monitoring sync skipped"
  exit 0
fi

STRICT=false

while [[ $# -gt 0 ]]; do
  case "$1" in
    --strict)
      STRICT=true
      shift
      ;;
    *)
      log_warning "Unknown arg: $1"
      shift
      ;;
  esac
done

if ! command -v prometheus &>/dev/null; then
  log_warning "Prometheus not installed; native monitoring sync skipped"
  exit 0
fi

if ! command -v sudo &>/dev/null; then
  log_warning "sudo not installed; cannot sync /etc/* monitoring config"
  exit 0
fi

# Never prompt for password during dev scripts.
if ! sudo -n true 2>/dev/null; then
  log_warning "sudo password required; cannot sync /etc/* (run: sudo -v && ./scripts/dev/sync-native-monitoring.sh)"
  exit 0
fi

log_step "Sync native monitoring config (/etc)"

# Ensure repo-side targets are up to date with .env.local
if [[ -x "$PROJECT_ROOT/scripts/dev/generate-blackbox-targets.sh" ]]; then
  if ! "$PROJECT_ROOT/scripts/dev/generate-blackbox-targets.sh"; then
    log_warning "Failed to generate blackbox targets from .env.local"
    $STRICT && exit 1
  fi
fi

PROM_SRC="$PROJECT_ROOT/infrastructure/monitoring/prometheus/prometheus-native.yml"
BLACKBOX_SRC="$PROJECT_ROOT/infrastructure/monitoring/blackbox/blackbox.yml"
TARGETS_SRC="$PROJECT_ROOT/infrastructure/monitoring/prometheus/targets/blackbox_tcp.yml"

if ! sudo -n mkdir -p /etc/prometheus/targets; then
  log_warning "Failed to create /etc/prometheus/targets"
  $STRICT && exit 1 || exit 0
fi

if ! sudo -n mkdir -p /etc/blackbox_exporter; then
  log_warning "Failed to create /etc/blackbox_exporter"
  $STRICT && exit 1 || exit 0
fi

if [[ -f "$TARGETS_SRC" ]]; then
  if ! sudo -n cp "$TARGETS_SRC" /etc/prometheus/targets/blackbox_tcp.yml; then
    log_warning "Failed to update /etc/prometheus/targets/blackbox_tcp.yml"
    $STRICT && exit 1
  fi
  log_success "Updated /etc/prometheus/targets/blackbox_tcp.yml"
else
  log_warning "Missing repo targets file: $TARGETS_SRC"
  $STRICT && exit 1
fi

if [[ -f "$BLACKBOX_SRC" ]]; then
  if ! sudo -n cp "$BLACKBOX_SRC" /etc/blackbox_exporter/config.yml; then
    log_warning "Failed to update /etc/blackbox_exporter/config.yml"
    $STRICT && exit 1
  fi
  log_success "Updated /etc/blackbox_exporter/config.yml"
else
  log_warning "Missing repo blackbox config: $BLACKBOX_SRC"
  $STRICT && exit 1
fi

if [[ -f "$PROM_SRC" ]]; then
  if ! sudo -n mkdir -p /etc/prometheus; then
    log_warning "Failed to create /etc/prometheus"
    $STRICT && exit 1
  fi
  if ! sudo -n cp "$PROM_SRC" /etc/prometheus/prometheus.yml; then
    log_warning "Failed to update /etc/prometheus/prometheus.yml"
    $STRICT && exit 1
  fi
  log_success "Updated /etc/prometheus/prometheus.yml"
else
  log_warning "Missing repo Prometheus native config: $PROM_SRC"
  $STRICT && exit 1
fi

if systemctl list-unit-files | grep -q '^blackbox-exporter\\.service'; then
  sudo -n systemctl daemon-reload || true
  sudo -n systemctl restart blackbox-exporter || true
else
  log_warning "blackbox-exporter.service not installed (skip restart)"
fi

sudo -n systemctl restart prometheus || true

log_success "Native monitoring sync done"
