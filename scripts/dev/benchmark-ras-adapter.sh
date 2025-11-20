#!/bin/bash
# Week 4 Day 2: RAS Adapter Performance Benchmarking
# Measures latency, throughput, and performs load testing

set -e

echo "========================================"
echo "  RAS Adapter Performance Benchmarks"
echo "========================================"
echo ""

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
RAS_ADAPTER_URL="${RAS_ADAPTER_URL:-http://localhost:8088}"
RAS_SERVER="${RAS_SERVER:-localhost:1545}"
NUM_REQUESTS="${NUM_REQUESTS:-100}"
CONCURRENCY="${CONCURRENCY:-10}"

# Results file
RESULTS_FILE="benchmark_results_$(date +%Y%m%d_%H%M%S).txt"

echo "Configuration:"
echo "  RAS Adapter URL: $RAS_ADAPTER_URL"
echo "  RAS Server: $RAS_SERVER"
echo "  Requests: $NUM_REQUESTS"
echo "  Concurrency: $CONCURRENCY"
echo "  Results: $RESULTS_FILE"
echo ""

# Function to calculate statistics
calculate_stats() {
    local values="$1"
    echo "$values" | awk '
    BEGIN { sum=0; count=0; min=999999; max=0 }
    {
        sum+=$1
        count++
        if ($1 < min) min=$1
        if ($1 > max) max=$1
        values[count]=$1
    }
    END {
        avg = sum/count
        # Sort for percentiles
        asort(values)
        p50 = values[int(count * 0.5)]
        p95 = values[int(count * 0.95)]
        p99 = values[int(count * 0.99)]
        printf "Min: %.0fms, Max: %.0fms, Avg: %.0fms, P50: %.0fms, P95: %.0fms, P99: %.0fms\n",
               min, max, avg, p50, p95, p99
    }'
}

# Benchmark 1: Health Check Latency
echo -e "${BLUE}Benchmark 1: Health Check Latency${NC}"
echo "Running $NUM_REQUESTS requests..."

health_latencies=""
for i in $(seq 1 $NUM_REQUESTS); do
    latency=$(curl -o /dev/null -s -w '%{time_total}\n' "$RAS_ADAPTER_URL/health" | awk '{print $1 * 1000}')
    health_latencies="$health_latencies$latency\n"

    # Progress indicator
    if [ $((i % 20)) -eq 0 ]; then
        echo -n "."
    fi
done
echo ""

health_stats=$(echo -e "$health_latencies" | calculate_stats)
echo "Health Check: $health_stats"
echo ""

# Benchmark 2: GET /clusters Latency
echo -e "${BLUE}Benchmark 2: GET /clusters Latency${NC}"
echo "Running $NUM_REQUESTS requests..."

clusters_latencies=""
for i in $(seq 1 $NUM_REQUESTS); do
    latency=$(curl -o /dev/null -s -w '%{time_total}\n' "$RAS_ADAPTER_URL/api/v1/clusters?server=$RAS_SERVER" | awk '{print $1 * 1000}')
    clusters_latencies="$clusters_latencies$latency\n"

    # Progress indicator
    if [ $((i % 20)) -eq 0 ]; then
        echo -n "."
    fi
done
echo ""

clusters_stats=$(echo -e "$clusters_latencies" | calculate_stats)
echo "GET /clusters: $clusters_stats"
echo ""

# Benchmark 3: Throughput Test (concurrent requests)
echo -e "${BLUE}Benchmark 3: Throughput Test (Concurrent)${NC}"
echo "Running $NUM_REQUESTS requests with concurrency=$CONCURRENCY..."

start_time=$(date +%s.%N)

# Use xargs for parallel requests (GNU parallel alternative)
seq 1 $NUM_REQUESTS | xargs -P $CONCURRENCY -I {} curl -s -o /dev/null "$RAS_ADAPTER_URL/health"

end_time=$(date +%s.%N)
duration=$(awk "BEGIN {print $end_time - $start_time}")
throughput=$(awk "BEGIN {print $NUM_REQUESTS / $duration}")

echo "Duration: ${duration}s"
echo "Throughput: $(printf '%.2f' $throughput) requests/second"
echo ""

# Benchmark 4: Success Rate Test
echo -e "${BLUE}Benchmark 4: Success Rate Test${NC}"
echo "Running $NUM_REQUESTS requests..."

success_count=0
for i in $(seq 1 $NUM_REQUESTS); do
    if curl -sf "$RAS_ADAPTER_URL/health" > /dev/null 2>&1; then
        success_count=$((success_count + 1))
    fi

    # Progress indicator
    if [ $((i % 20)) -eq 0 ]; then
        echo -n "."
    fi
done
echo ""

success_rate=$(awk "BEGIN {printf \"%.2f\", $success_count * 100 / $NUM_REQUESTS}")
echo "Success Rate: ${success_rate}% ($success_count/$NUM_REQUESTS)"
echo ""

# Save results to file
{
    echo "========================================"
    echo "  RAS Adapter Performance Benchmarks"
    echo "========================================"
    echo ""
    echo "Date: $(date)"
    echo "Configuration:"
    echo "  RAS Adapter URL: $RAS_ADAPTER_URL"
    echo "  RAS Server: $RAS_SERVER"
    echo "  Requests: $NUM_REQUESTS"
    echo "  Concurrency: $CONCURRENCY"
    echo ""
    echo "Results:"
    echo ""
    echo "1. Health Check Latency:"
    echo "   $health_stats"
    echo ""
    echo "2. GET /clusters Latency:"
    echo "   $clusters_stats"
    echo ""
    echo "3. Throughput Test:"
    echo "   Duration: ${duration}s"
    echo "   Throughput: $(printf '%.2f' $throughput) requests/second"
    echo ""
    echo "4. Success Rate:"
    echo "   Success Rate: ${success_rate}% ($success_count/$NUM_REQUESTS)"
    echo ""
} > "$RESULTS_FILE"

echo -e "${GREEN}✓ Benchmarks complete!${NC}"
echo "Results saved to: $RESULTS_FILE"
echo ""

# Summary with color coding
echo "========================================"
echo "  Summary"
echo "========================================"

# Health Check evaluation
health_p95=$(echo -e "$health_latencies" | awk '{sum+=$1; a[NR]=$1} END{asort(a); print a[int(NR*0.95)]}')
if [ $(awk "BEGIN {print ($health_p95 < 100) ? 1 : 0}") -eq 1 ]; then
    echo -e "Health Check P95: ${GREEN}✓ EXCELLENT${NC} ($(printf '%.0f' $health_p95)ms < 100ms target)"
else
    echo -e "Health Check P95: ${YELLOW}⚠ ACCEPTABLE${NC} ($(printf '%.0f' $health_p95)ms)"
fi

# Clusters evaluation
clusters_p95=$(echo -e "$clusters_latencies" | awk '{sum+=$1; a[NR]=$1} END{asort(a); print a[int(NR*0.95)]}')
if [ $(awk "BEGIN {print ($clusters_p95 < 500) ? 1 : 0}") -eq 1 ]; then
    echo -e "GET /clusters P95: ${GREEN}✓ EXCELLENT${NC} ($(printf '%.0f' $clusters_p95)ms < 500ms target)"
else
    echo -e "GET /clusters P95: ${YELLOW}⚠ ACCEPTABLE${NC} ($(printf '%.0f' $clusters_p95)ms)"
fi

# Throughput evaluation
if [ $(awk "BEGIN {print ($throughput > 100) ? 1 : 0}") -eq 1 ]; then
    echo -e "Throughput: ${GREEN}✓ EXCELLENT${NC} ($(printf '%.2f' $throughput) > 100 req/s target)"
else
    echo -e "Throughput: ${YELLOW}⚠ ACCEPTABLE${NC} ($(printf '%.2f' $throughput) req/s)"
fi

# Success Rate evaluation
if [ $(awk "BEGIN {print ($success_rate > 99) ? 1 : 0}") -eq 1 ]; then
    echo -e "Success Rate: ${GREEN}✓ EXCELLENT${NC} (${success_rate}% > 99% target)"
else
    echo -e "Success Rate: ${YELLOW}⚠ NEEDS IMPROVEMENT${NC} (${success_rate}%)"
fi

echo ""
