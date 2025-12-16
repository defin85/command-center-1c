#!/bin/bash

##############################################################################
# CommandCenter1C - SLO / Latency / Error-rate Check (Prometheus)
##############################################################################
# Checks p95/p99 latency + 5xx error ratio for key services using Prometheus.
# Usage:
#   ./scripts/dev/slo-check.sh
#   PROM_URL=http://localhost:9090 LOOKBACK=5m ./scripts/dev/slo-check.sh
##############################################################################

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$PROJECT_ROOT"

# Source unified library (colors + helpers)
source "$PROJECT_ROOT/scripts/lib/init.sh"

PROM_URL="${PROM_URL:-http://localhost:9090}"
LOOKBACK="${LOOKBACK:-5m}"

P95_MS_THRESHOLD="${P95_MS_THRESHOLD:-500}"
P99_MS_THRESHOLD="${P99_MS_THRESHOLD:-1500}"
ERR_RATIO_THRESHOLD="${ERR_RATIO_THRESHOLD:-0.01}" # 1%

query_prom() {
  local query="$1"
  curl -sS --fail "$PROM_URL/api/v1/query" --get --data-urlencode "query=$query"
}

extract_scalar() {
  python -c 'import json,math,sys
data=json.load(sys.stdin)
result=data.get("data", {}).get("result", [])
if not result:
  print("NA"); raise SystemExit(0)
val=result[0].get("value")
if not val or len(val) < 2:
  print("NA"); raise SystemExit(0)
try:
  f=float(val[1])
except Exception:
  print("NA"); raise SystemExit(0)
if math.isnan(f) or math.isinf(f):
  print("NA"); raise SystemExit(0)
print(f"{f:.6f}")'
}

cmp_float() {
  python - <<PY
import sys
a=float(sys.argv[1]); b=float(sys.argv[2])
sys.exit(0 if a <= b else 1)
PY
}

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}  CommandCenter1C - SLO Check${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""
echo -e "${BLUE}Prometheus:${NC} $PROM_URL"
echo -e "${BLUE}Lookback:${NC}   $LOOKBACK"
echo -e "${BLUE}Thresholds:${NC} p95<=${P95_MS_THRESHOLD}ms, p99<=${P99_MS_THRESHOLD}ms, 5xx<=${ERR_RATIO_THRESHOLD}"
echo ""

# job label patterns used across exporters/services
declare -a JOBS=(
  "api_gateway|api-gateway|apigateway"
  "orchestrator"
  "worker"
  "ras_adapter|ras-adapter|rasadapter"
  "batch_service|batch-service|batchservice"
)

overall_ok=1

for pattern in "${JOBS[@]}"; do
  p95_q="histogram_quantile(0.95, sum(rate(cc1c_request_duration_seconds_bucket{job=~\"$pattern\"}[$LOOKBACK])) by (le)) * 1000"
  p99_q="histogram_quantile(0.99, sum(rate(cc1c_request_duration_seconds_bucket{job=~\"$pattern\"}[$LOOKBACK])) by (le)) * 1000"
  err_q="sum(rate(cc1c_requests_total{job=~\"$pattern\",status=~\"5..\"}[$LOOKBACK])) / sum(rate(cc1c_requests_total{job=~\"$pattern\"}[$LOOKBACK]))"
  rps_q="sum(rate(cc1c_requests_total{job=~\"$pattern\"}[$LOOKBACK]))"

  p95="$(query_prom "$p95_q" | extract_scalar)"
  p99="$(query_prom "$p99_q" | extract_scalar)"
  err="$(query_prom "$err_q" | extract_scalar)"
  rps="$(query_prom "$rps_q" | extract_scalar)"

  name="$pattern"
  echo -e "${BLUE}Service(job=~\"$name\")${NC}"
  echo "  rps:      $rps"
  echo "  p95_ms:   $p95"
  echo "  p99_ms:   $p99"
  echo "  err_5xx:  $err"

  # No traffic / missing metrics: do not fail, but warn.
  if [[ "$rps" == "NA" ]] || [[ "$p95" == "NA" ]] || [[ "$p99" == "NA" ]] || [[ "$err" == "NA" ]]; then
    echo -e "  ${YELLOW}⚠️  insufficient data (no series / no traffic)${NC}"
    echo ""
    continue
  fi

  ok=0
  if cmp_float "$p95" "$P95_MS_THRESHOLD"; then ok=$((ok+1)); fi
  if cmp_float "$p99" "$P99_MS_THRESHOLD"; then ok=$((ok+1)); fi
  if cmp_float "$err" "$ERR_RATIO_THRESHOLD"; then ok=$((ok+1)); fi

  if [[ "$ok" -eq 3 ]]; then
    echo -e "  ${GREEN}✓ SLO OK${NC}"
  else
    echo -e "  ${RED}✗ SLO FAIL${NC}"
    overall_ok=0
  fi
  echo ""
done

if [[ "$overall_ok" -eq 1 ]]; then
  echo -e "${GREEN}Overall: OK${NC}"
  exit 0
fi

echo -e "${RED}Overall: FAIL${NC}"
exit 2
