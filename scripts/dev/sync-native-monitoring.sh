#!/bin/bash

##############################################################################
# CommandCenter1C - Sync Native Monitoring Config
##############################################################################
# Best-effort sync of repository monitoring configs into system paths for
# native mode (USE_DOCKER=false):
# - Prometheus config (/etc/prometheus/prometheus.yml)
# - Blackbox exporter config (/etc/blackbox_exporter/config.yml)
# - Prometheus blackbox targets (/etc/prometheus/targets/blackbox_tcp.yml, blackbox_http.yml)
# - Blackbox exporter stderr suppression override for noisy distro packages
#
# This exists because native Prometheus reads /etc/*, while docker mode uses
# bind-mounts from the repo.
##############################################################################

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

source "$PROJECT_ROOT/scripts/lib/init.sh"

cd "$PROJECT_ROOT"
STRICT=false
ENV_FILE="${CC1C_ENV_FILE:-$PROJECT_ROOT/.env.local}"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --strict)
      STRICT=true
      shift
      ;;
    --env-file)
      if [[ $# -lt 2 ]]; then
        log_warning "Missing value for --env-file"
        $STRICT && exit 1 || exit 0
      fi
      ENV_FILE="$2"
      shift 2
      ;;
    *)
      log_warning "Unknown arg: $1"
      shift
      ;;
  esac
done

load_env_file "$ENV_FILE"

if is_docker_mode; then
  log_info "Docker mode: native monitoring sync skipped"
  exit 0
fi

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
BLACKBOX_OVERRIDE_SRC="$PROJECT_ROOT/infrastructure/systemd/blackbox-exporter.override.conf"
TARGETS_TCP_SRC="$PROJECT_ROOT/infrastructure/monitoring/prometheus/targets/blackbox_tcp.yml"
TARGETS_HTTP_SRC="$PROJECT_ROOT/infrastructure/monitoring/prometheus/targets/blackbox_http.yml"
BLACKBOX_DESTINATIONS=(
  "/etc/blackbox_exporter/config.yml"
  "/etc/prometheus/blackbox.yml"
)
BLACKBOX_SERVICES=(
  "blackbox-exporter.service"
  "prometheus-blackbox-exporter.service"
)

if ! sudo -n mkdir -p /etc/prometheus /etc/prometheus/targets /etc/blackbox_exporter; then
  log_warning "Failed to create /etc/prometheus/targets"
  $STRICT && exit 1 || exit 0
fi

if [[ -f "$TARGETS_TCP_SRC" ]]; then
  if ! sudo -n cp "$TARGETS_TCP_SRC" /etc/prometheus/targets/blackbox_tcp.yml; then
    log_warning "Failed to update /etc/prometheus/targets/blackbox_tcp.yml"
    $STRICT && exit 1
  fi
  log_success "Updated /etc/prometheus/targets/blackbox_tcp.yml"
else
  log_warning "Missing repo targets file: $TARGETS_TCP_SRC"
  $STRICT && exit 1
fi

if [[ -f "$TARGETS_HTTP_SRC" ]]; then
  if ! sudo -n cp "$TARGETS_HTTP_SRC" /etc/prometheus/targets/blackbox_http.yml; then
    log_warning "Failed to update /etc/prometheus/targets/blackbox_http.yml"
    $STRICT && exit 1
  fi
  log_success "Updated /etc/prometheus/targets/blackbox_http.yml"
else
  log_warning "Missing repo targets file: $TARGETS_HTTP_SRC"
  $STRICT && exit 1
fi

if [[ -f "$BLACKBOX_SRC" ]]; then
  for destination in "${BLACKBOX_DESTINATIONS[@]}"; do
    if ! sudo -n mkdir -p "$(dirname "$destination")"; then
      log_warning "Failed to create $(dirname "$destination")"
      $STRICT && exit 1
    fi
    if ! sudo -n cp "$BLACKBOX_SRC" "$destination"; then
      log_warning "Failed to update $destination"
      $STRICT && exit 1
    fi
    log_success "Updated $destination"
  done
else
  log_warning "Missing repo blackbox config: $BLACKBOX_SRC"
  $STRICT && exit 1
fi

if [[ -f "$BLACKBOX_OVERRIDE_SRC" ]]; then
  for service_name in "${BLACKBOX_SERVICES[@]}"; do
    override_dir="/etc/systemd/system/${service_name}.d"
    override_dest="$override_dir/override.conf"
    if ! sudo -n mkdir -p "$override_dir"; then
      log_warning "Failed to create $override_dir"
      $STRICT && exit 1
    fi
    if ! sudo -n cp "$BLACKBOX_OVERRIDE_SRC" "$override_dest"; then
      log_warning "Failed to update $override_dest"
      $STRICT && exit 1
    fi
    log_success "Updated $override_dest"
  done
else
  log_warning "Missing repo blackbox override: $BLACKBOX_OVERRIDE_SRC"
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

sudo -n systemctl daemon-reload || true

blackbox_service_found=false
for service_name in "${BLACKBOX_SERVICES[@]}"; do
  if systemctl show -p LoadState "$service_name" 2>/dev/null | grep -q 'LoadState=loaded'; then
    blackbox_service_found=true
    if ! sudo -n systemctl restart "$service_name"; then
      log_warning "Failed to restart $service_name"
      $STRICT && exit 1
    fi
    log_success "Restarted $service_name"
  fi
done

if [[ "$blackbox_service_found" != "true" ]]; then
  log_warning "No blackbox exporter systemd service found (skip restart)"
fi

sudo -n systemctl restart prometheus || true

log_success "Native monitoring sync done"
