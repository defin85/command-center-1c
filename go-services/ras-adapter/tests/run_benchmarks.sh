#!/bin/bash
# Performance benchmarks runner for RAS Adapter
# Measures lock/unlock latency, throughput, and system performance

set -e

echo "========================================="
echo "  RAS Adapter Performance Benchmarks"
echo "========================================="
echo ""

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
RAS_SERVER="${RAS_SERVER:-localhost:1545}"
REDIS_HOST="${REDIS_HOST:-localhost}"
REDIS_PORT="${REDIS_PORT:-6379}"

echo "Configuration:"
echo "  RAS Server: ${RAS_SERVER}"
echo "  Redis: ${REDIS_HOST}:${REDIS_PORT}"
echo ""

# Run benchmarks
echo "Running performance benchmarks..."
echo ""
echo "Note: Benchmarks measure:"
echo "  - Lock/Unlock latency (P50, P95, P99)"
echo "  - Cluster/Infobase discovery latency"
echo "  - Session listing latency"
echo "  - Throughput (operations/second)"
echo "  - Concurrent operation performance"
echo ""

cd "$(dirname "$0")/.."

# Export environment for tests
export RAS_SERVER
export REDIS_HOST

# Run benchmarks with statistics
go test \
    -tags=integration \
    -bench=. \
    -benchmem \
    -benchtime=10s \
    -count=3 \
    -timeout=600s \
    -v \
    ./tests/integration/... \
    2>&1 | tee benchmark_results.txt

BENCH_EXIT_CODE=${PIPESTATUS[0]}

echo ""
echo "========================================="
echo -e "${GREEN}✓${NC} Benchmarks Complete"
echo "========================================="
echo ""
echo "Results saved to: benchmark_results.txt"
echo ""

# Print summary if benchmarks succeeded
if [ $BENCH_EXIT_CODE -eq 0 ]; then
    echo "Benchmark Summary:"
    echo ""
    echo "Run the following command to analyze results:"
    echo "  go test -tags=integration -bench=. -benchstat benchmark_results.txt ./tests/integration/..."
    echo ""
    echo "Or view raw results:"
    echo "  cat benchmark_results.txt | grep -E 'Benchmark|ns/op|bytes/op|allocs/op'"
fi

exit $BENCH_EXIT_CODE
