#!/bin/bash

##############################################################################
# CommandCenter1C - Sync Prometheus Config (Native/systemd)
##############################################################################
# Copies Prometheus config + rules from repo into /etc/prometheus and (optionally)
# restarts Prometheus service.
#
# Usage:
#   ./scripts/dev/sync-prometheus-config.sh --apply --restart
#   ./scripts/dev/sync-prometheus-config.sh --validate-only
#   ./scripts/dev/sync-prometheus-config.sh --dry-run
##############################################################################

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

source "$PROJECT_ROOT/scripts/lib/init.sh"

SRC_CONFIG="$PROJECT_ROOT/infrastructure/monitoring/prometheus/prometheus-native.yml"
SRC_RULES="$PROJECT_ROOT/infrastructure/monitoring/prometheus/recording_rules.yml"
SRC_ALERTS_DIR="$PROJECT_ROOT/infrastructure/monitoring/prometheus/alerts"

DST_DIR="/etc/prometheus"
DST_CONFIG="$DST_DIR/prometheus.yml"
DST_RULES="$DST_DIR/recording_rules.yml"
DST_ALERTS_DIR="$DST_DIR/alerts"

MODE="apply"         # apply | validate-only | dry-run
RESTART=false

show_help() {
  echo "Usage: $0 [--apply|--validate-only|--dry-run] [--restart]"
  echo ""
  echo "Options:"
  echo "  --apply           Copy files to /etc/prometheus (default)"
  echo "  --validate-only   Only run promtool check (no copy)"
  echo "  --dry-run         Show planned actions (no copy)"
  echo "  --restart         Restart prometheus via systemctl after успешной проверки"
  echo "  --help            Show help"
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --apply) MODE="apply"; shift ;;
    --validate-only) MODE="validate-only"; shift ;;
    --dry-run) MODE="dry-run"; shift ;;
    --restart) RESTART=true; shift ;;
    --help) show_help; exit 0 ;;
    *)
      log_error "Unknown option: $1"
      show_help
      exit 1
      ;;
  esac
done

if [[ ! -f "$SRC_CONFIG" ]]; then
  log_error "Source config not found: $SRC_CONFIG"
  exit 1
fi
if [[ ! -f "$SRC_RULES" ]]; then
  log_error "Source rules not found: $SRC_RULES"
  exit 1
fi
if [[ ! -d "$SRC_ALERTS_DIR" ]]; then
  log_error "Source alerts dir not found: $SRC_ALERTS_DIR"
  exit 1
fi

print_header "Sync Prometheus config (native)"
log_info "Source:"
echo "  $SRC_CONFIG"
echo "  $SRC_RULES"
echo "  $SRC_ALERTS_DIR/"
echo ""
log_info "Destination:"
echo "  $DST_CONFIG"
echo "  $DST_RULES"
echo "  $DST_ALERTS_DIR/"
echo ""

if [[ "$MODE" == "dry-run" ]]; then
  log_info "Dry run: no changes will be made"
  exit 0
fi

if [[ "$MODE" == "apply" ]]; then
  log_step "Copying files to $DST_DIR (sudo)..."
  sudo mkdir -p "$DST_ALERTS_DIR"
  sudo cp "$SRC_CONFIG" "$DST_CONFIG"
  sudo cp "$SRC_RULES" "$DST_RULES"
  sudo cp "$SRC_ALERTS_DIR"/*.yml "$DST_ALERTS_DIR"/
  sudo chmod 644 "$DST_CONFIG" "$DST_RULES" "$DST_ALERTS_DIR"/*.yml || true
  print_status "success" "Files copied"
  echo ""
fi

if ! command -v promtool &>/dev/null; then
  print_status "warning" "promtool not found, skipping validation"
  if [[ "$RESTART" == "true" ]]; then
    print_status "warning" "Cannot safely restart without promtool; run: sudo systemctl restart prometheus"
  fi
  exit 0
fi

log_step "Validating config with promtool..."
sudo promtool check config "$DST_CONFIG"
print_status "success" "Config valid"
echo ""

if [[ "$RESTART" == "true" ]]; then
  log_step "Restarting prometheus (systemd)..."
  sudo systemctl restart prometheus
  print_status "success" "prometheus restarted"
fi
