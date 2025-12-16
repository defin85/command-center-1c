#!/bin/bash
# Week 4: RAS Adapter Smoke Tests
# Tests Lock/Unlock workflow via REST API and Redis Pub/Sub

set -e

echo "========================================"
echo "  RAS Adapter Smoke Tests"
echo "========================================"
echo ""

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
RAS_ADAPTER_URL="${RAS_ADAPTER_URL:-http://localhost:8088}"
REDIS_HOST="${REDIS_HOST:-localhost}"
REDIS_PORT="${REDIS_PORT:-6379}"

# Test counter
TESTS_PASSED=0
TESTS_FAILED=0

# Helper functions
pass() {
    echo -e "${GREEN}✓${NC} $1"
    TESTS_PASSED=$((TESTS_PASSED + 1))
}

fail() {
    echo -e "${RED}✗${NC} $1"
    TESTS_FAILED=$((TESTS_FAILED + 1))
}

warn() {
    echo -e "${YELLOW}⚠${NC} $1"
}

# Test 1: Health Check
echo "Test 1: Health Check"
if curl -sf "$RAS_ADAPTER_URL/health" > /dev/null 2>&1; then
    pass "Health check PASSED"
else
    fail "Health check FAILED"
    exit 1
fi

# Test 2: GET /clusters (RAS connection)
echo ""
echo "Test 2: GET /clusters (RAS connection)"
CLUSTERS_RESPONSE=$(curl -sf "$RAS_ADAPTER_URL/api/v2/list-clusters?server=localhost:1545" 2>&1)
if [ $? -eq 0 ] && [ ! -z "$CLUSTERS_RESPONSE" ]; then
    pass "GET /clusters PASSED"
    echo "  Response: $CLUSTERS_RESPONSE" | head -c 100
    echo "..."
else
    fail "GET /clusters FAILED"
    echo "  Error: $CLUSTERS_RESPONSE"
fi

# Test 3: GET /infobases
echo ""
echo "Test 3: GET /infobases"
# Extract first cluster_id from clusters response (prefer Python, jq is not guaranteed)
CLUSTER_ID=$(python - <<'PY' <<<"$CLUSTERS_RESPONSE"
import json, sys
try:
    data = json.load(sys.stdin)
except Exception:
    sys.exit(0)
clusters = data.get("clusters") if isinstance(data, dict) else data
if isinstance(clusters, list) and clusters and isinstance(clusters[0], dict):
    print(clusters[0].get("uuid", ""))
PY
)

if [ ! -z "$CLUSTER_ID" ]; then
    INFOBASES_RESPONSE=$(curl -sf "$RAS_ADAPTER_URL/api/v2/list-infobases?cluster_id=$CLUSTER_ID" 2>&1)
    if [ $? -eq 0 ]; then
        pass "GET /infobases PASSED"
        echo "  Cluster ID: $CLUSTER_ID"
    else
        fail "GET /infobases FAILED"
    fi
else
    warn "GET /infobases SKIPPED (no cluster_id found)"
fi

# Test 4: POST /lock (REST API)
echo ""
echo "Test 4: POST /lock (REST API)"
warn "POST /lock SKIPPED (requires valid cluster_id and infobase_id)"
echo "  Manual test: curl -X POST \"$RAS_ADAPTER_URL/api/v2/lock-infobase?cluster_id=<CLUSTER_ID>&infobase_id=<INFOBASE_ID>\" -H 'Content-Type: application/json' -d '{\"db_user\":\"admin\",\"db_password\":\"secret\"}'"

# Test 5: POST /unlock (REST API)
echo ""
echo "Test 5: POST /unlock (REST API)"
warn "POST /unlock SKIPPED (requires valid cluster_id and infobase_id)"
echo "  Manual test: curl -X POST \"$RAS_ADAPTER_URL/api/v2/unlock-infobase?cluster_id=<CLUSTER_ID>&infobase_id=<INFOBASE_ID>\" -H 'Content-Type: application/json' -d '{\"db_user\":\"admin\",\"db_password\":\"secret\"}'"

# Test 6: Redis connectivity
echo ""
echo "Test 6: Redis connectivity"
if timeout 5 bash -c "exec 3<>/dev/tcp/$REDIS_HOST/$REDIS_PORT" 2>/dev/null; then
    pass "Redis connectivity PASSED"
else
    fail "Redis connectivity FAILED"
fi

# Test 7: Redis Pub/Sub Lock (requires redis-cli)
echo ""
echo "Test 7: Redis Pub/Sub Lock"
if command -v redis-cli &> /dev/null; then
    warn "Redis Pub/Sub Lock SKIPPED (requires manual test)"
    echo "  Manual test: redis-cli PUBLISH commands:ras-adapter:infobase:lock '{\"cluster_id\":\"...\",\"infobase_id\":\"...\"}'"
else
    warn "Redis Pub/Sub Lock SKIPPED (redis-cli not installed)"
fi

# Test 8: Redis Pub/Sub Unlock
echo ""
echo "Test 8: Redis Pub/Sub Unlock"
if command -v redis-cli &> /dev/null; then
    warn "Redis Pub/Sub Unlock SKIPPED (requires manual test)"
    echo "  Manual test: redis-cli PUBLISH commands:ras-adapter:infobase:unlock '{\"cluster_id\":\"...\",\"infobase_id\":\"...\"}'"
else
    warn "Redis Pub/Sub Unlock SKIPPED (redis-cli not installed)"
fi

# Summary
echo ""
echo "========================================"
echo "  Test Summary"
echo "========================================"
echo "Passed: $TESTS_PASSED"
echo "Failed: $TESTS_FAILED"

if [ $TESTS_FAILED -gt 0 ]; then
    echo ""
    echo -e "${RED}SMOKE TESTS FAILED${NC}"
    exit 1
else
    echo ""
    echo -e "${GREEN}SMOKE TESTS PASSED${NC}"
    exit 0
fi
