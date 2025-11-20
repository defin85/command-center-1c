#!/bin/bash
# Integration tests runner for RAS Adapter
# Tests real RAS protocol integration and system behavior

set -e

echo "========================================="
echo "  RAS Adapter Integration Tests"
echo "========================================="
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
RAS_SERVER="${RAS_SERVER:-localhost:1545}"
REDIS_HOST="${REDIS_HOST:-localhost}"
REDIS_PORT="${REDIS_PORT:-6379}"

# Check prerequisites
echo "Checking prerequisites..."
echo ""

# Check RAS server
echo "Checking RAS server (${RAS_SERVER})..."
if timeout 5 bash -c "exec 3<>/dev/tcp/${RAS_SERVER%:*}/${RAS_SERVER##*:}" 2>/dev/null; then
    echo -e "${GREEN}✓${NC} RAS server available (${RAS_SERVER})"
else
    echo -e "${RED}✗${NC} RAS server not available on ${RAS_SERVER}"
    echo "Please start 1C RAS server first or set RAS_SERVER environment variable"
    exit 1
fi

# Check Redis
echo "Checking Redis (${REDIS_HOST}:${REDIS_PORT})..."
if timeout 5 bash -c "exec 3<>/dev/tcp/${REDIS_HOST}/${REDIS_PORT}" 2>/dev/null; then
    echo -e "${GREEN}✓${NC} Redis available (${REDIS_HOST}:${REDIS_PORT})"
else
    echo -e "${RED}✗${NC} Redis not available on ${REDIS_HOST}:${REDIS_PORT}"
    echo "Please start Redis first: docker-compose up -d redis"
    exit 1
fi

echo ""
echo "All prerequisites satisfied!"
echo ""

# Run integration tests
echo "Running integration tests..."
echo ""

cd "$(dirname "$0")/.."

# Export environment for tests
export RAS_SERVER
export REDIS_HOST

# Run tests with verbose output
go test \
    -tags=integration \
    -v \
    -count=1 \
    -timeout=60s \
    ./tests/integration/... \
    2>&1 | tee integration_test_results.txt

# Check test results
TEST_EXIT_CODE=${PIPESTATUS[0]}

echo ""
echo "========================================="
if [ $TEST_EXIT_CODE -eq 0 ]; then
    echo -e "${GREEN}✓ Integration Tests PASSED${NC}"
else
    echo -e "${RED}✗ Integration Tests FAILED${NC}"
fi
echo "========================================="
echo ""
echo "Results saved to: integration_test_results.txt"
echo ""

exit $TEST_EXIT_CODE
