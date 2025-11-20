# RAS Adapter Test Suite - Week 3 Integration Tests

Comprehensive integration test suite for RAS Adapter real RAS protocol implementation.

---

## Quick Start

### Prerequisites

1. **RAS Server** running on localhost:1545
   ```bash
   # Or configure with environment variable
   export RAS_SERVER=192.168.1.100:1545
   ```

2. **Redis** running on localhost:6379
   ```bash
   # Or start with Docker
   docker-compose up -d redis

   # Or configure
   export REDIS_HOST=192.168.1.50
   ```

3. **Go** 1.21+ installed

### Run All Integration Tests

```bash
./run_integration_tests.sh
```

**Output:** `integration_test_results.txt`

### Run Performance Benchmarks

```bash
./run_benchmarks.sh
```

**Output:** `benchmark_results.txt`

### Run Specific Test

```bash
# Single test
go test -tags=integration -v -run TestLockUnlockIntegration ./integration/...

# Test pattern
go test -tags=integration -v -run TestLock ./integration/...

# With race detector
go test -tags=integration -v -race ./integration/...
```

---

## Test Organization

### 1. Setup Tests (`integration/setup_test.go`)

Environment setup and resource discovery.

```bash
go test -tags=integration -v -run TestEnvironmentSetup ./integration/...
```

**Tests:**
- RAS server availability
- Redis connectivity
- Auto-discovery of test cluster/infobase

---

### 2. Lock/Unlock Tests (`integration/lock_unlock_test.go`)

Lock/unlock operations against real RAS server.

```bash
go test -tags=integration -v -run TestLock ./integration/...
```

**Tests:**
- Basic lock/unlock
- Concurrent operations
- Idempotency validation
- Timeout handling

**Key Assertions:**
- `ScheduledJobsDeny` flag reflects lock state
- Operations are idempotent
- Concurrent calls succeed

---

### 3. Cluster & Session Tests (`integration/cluster_session_test.go`)

Cluster discovery and session management.

```bash
go test -tags=integration -v -run TestGetClusters ./integration/...
go test -tags=integration -v -run TestGetSessions ./integration/...
```

**Tests:**
- Cluster discovery (GetClusters)
- Infobase discovery (GetInfobases)
- Session listing (GetSessions)
- Infobase details (GetInfobaseInfo)
- Connection pool reuse
- Concurrent operations
- Latency measurement

---

### 4. Error Handling Tests (`integration/error_handling_test.go`)

Graceful error handling and resilience.

```bash
go test -tags=integration -v -run TestInvalid ./integration/...
```

**Tests:**
- Parameter validation
- Nonexistent resource handling
- Timeout behavior
- Context cancellation
- Pool exhaustion
- Health checks
- Concurrent error handling

---

### 5. Performance Tests (`integration/performance_test.go`)

Latency and throughput measurements.

```bash
# Benchmarks
go test -tags=integration -bench=Benchmark ./integration/... -benchtime=10s

# Latency percentiles
go test -tags=integration -v -run TestP50P95P99Latency ./integration/...

# Throughput
go test -tags=integration -v -run TestThroughputPerformance ./integration/...

# Concurrent performance
go test -tags=integration -v -run TestConcurrentLockPerformance ./integration/...
```

**Benchmarks:**
- LockUnlock (cycle latency)
- Lock (alone)
- Unlock (alone)
- GetClusters
- GetInfobases
- GetSessions

**Latency Tests:**
- P50, P95, P99 percentiles
- Throughput (ops/sec)
- Concurrent operation performance

---

### 6. Redis Integration Tests (`integration/redis_integration_test.go`)

Redis connectivity and event channel integration.

```bash
go test -tags=integration -v -run TestRedis ./integration/...
```

**Tests:**
- Redis connectivity (Ping)
- Key/value operations (Set/Get)
- Event envelope serialization
- Pub/Sub messaging
- Pattern subscriptions
- Concurrent publishers
- Full event channel workflow

---

## Environment Variables

### RAS Server Configuration

```bash
# Set custom RAS server
export RAS_SERVER=192.168.1.100:1545

# Run tests
./run_integration_tests.sh
```

### Redis Configuration

```bash
# Set custom Redis host
export REDIS_HOST=192.168.1.50

# Run tests (uses port 6379 by default)
./run_integration_tests.sh
```

### Test Execution

```bash
# Verbose output
go test -tags=integration -v ./integration/...

# Very verbose with race detector
go test -tags=integration -v -race ./integration/...

# Short timeout for quick validation
go test -tags=integration -timeout=30s ./integration/...
```

---

## Build Tag: `integration`

Tests require real RAS server and Redis. They use the `integration` build tag:

```go
// +build integration
```

**Run with tag:**
```bash
go test -tags=integration ./integration/...
```

**Run unit tests only (no integration):**
```bash
go test ./... # Skips integration tests
```

---

## Test Report

After running tests, review the generated test report:

**Template:** `RAS_ADAPTER_WEEK3_TEST_REPORT.md`

This document includes:
- Test results summary
- Performance metrics
- Issues found
- Recommendations
- Sign-off checklist

---

## Performance Targets

From architecture documentation:

| Operation | P50 | P95 | P99 |
|-----------|-----|-----|-----|
| Lock | <100ms | <500ms | <2s |
| Unlock | <100ms | <500ms | <2s |
| GetClusters | <100ms | <500ms | <2s |
| GetSessions | <100ms | <500ms | <2s |

**Throughput Target:**
- >100 operations/minute
- <1% error rate

---

## Troubleshooting

### RAS Server Not Available

```
Error: RAS server not available on localhost:1545
```

**Solution:**
1. Check RAS server is running
2. Verify localhost:1545 is accessible
3. Set custom address: `RAS_SERVER=192.168.1.100:1545`

### Redis Not Available

```
Error: Redis not available on localhost:6379
```

**Solution:**
1. Start Redis: `docker-compose up -d redis`
2. Verify port 6379 is open
3. Set custom host: `REDIS_HOST=192.168.1.50`

### Test Timeout

```
Error: context deadline exceeded
```

**Solution:**
1. Increase timeout: `go test -timeout=120s ...`
2. Check network latency to RAS/Redis
3. Verify RAS server isn't overloaded

### Tests Pass Unit Tests but Fail Integration Tests

```
Unit tests pass, but integration tests fail
```

**Reason:** Unit tests use mocks, integration tests use real RAS server

**Solution:**
1. Verify RAS server is configured correctly
2. Check cluster/infobase exist and are accessible
3. Review logs for RAS errors

---

## Test Development

### Adding New Tests

1. Create test file in `integration/` directory
2. Add build tag: `// +build integration`
3. Use `setupTestEnvironment()` for test resources
4. Use `GetTestClusterID()` and `GetTestInfobaseID()` for resources
5. Call `cleanupTestEnvironment()` in defer

**Example:**

```go
// +build integration

package integration

import (
    "context"
    "testing"

    "github.com/stretchr/testify/require"
)

func TestMyNewFeature(t *testing.T) {
    rasPool, redisClient, _ := setupTestEnvironment(t)
    defer cleanupTestEnvironment(rasPool, redisClient)

    clusterID := GetTestClusterID(t, rasPool)
    infobaseID := GetTestInfobaseID(t, rasPool)

    ctx := context.Background()

    // Your test here
    require.NoError(t, nil)
}
```

### Test Naming Convention

- Functional tests: `Test<Operation><Scenario>`
- Benchmarks: `Benchmark<Operation>`
- Latency tests: `Test<Measurement>Latency`

**Examples:**
- `TestLockUnlockIntegration`
- `TestConcurrentLockOperations`
- `TestP50P95P99Latency`
- `BenchmarkLockUnlock`

---

## CI/CD Integration

### GitHub Actions Example

```yaml
- name: Run Integration Tests
  env:
    RAS_SERVER: localhost:1545
    REDIS_HOST: localhost
  run: |
    cd go-services/ras-adapter
    ./tests/run_integration_tests.sh
```

### Docker Compose for CI

```yaml
version: '3.8'
services:
  redis:
    image: redis:7
    ports:
      - "6379:6379"

  ras-server:
    image: 1c-ras:latest
    ports:
      - "1545:1545"
```

---

## Performance Profiling

### CPU Profile

```bash
go test -tags=integration -cpuprofile=cpu.prof -bench=BenchmarkLockUnlock ./integration/...
go tool pprof cpu.prof
```

### Memory Profile

```bash
go test -tags=integration -memprofile=mem.prof -bench=BenchmarkLockUnlock ./integration/...
go tool pprof mem.prof
```

### View Profiles

```bash
# Interactive
go tool pprof -http=:8080 cpu.prof

# Command line
go tool pprof cpu.prof
(pprof) top
(pprof) list TestLockUnlock
```

---

## Debugging Tests

### Enable Debug Logging

```bash
# All debug logs
go test -tags=integration -v ./integration/... 2>&1 | grep DEBUG

# Specific test with logs
go test -tags=integration -v -run TestLockUnlock ./integration/...
```

### Run Single Test with Timeout

```bash
go test -tags=integration -v -run TestLockUnlock -timeout=30s ./integration/...
```

### Run with Race Detector

```bash
go test -tags=integration -race ./integration/...
```

---

## Known Limitations

1. **Real RAS Server Required**
   - Cannot run without real RAS server
   - Tests are slow compared to unit tests

2. **Test Isolation**
   - Tests share RAS cluster/infobase
   - Lock operations may affect concurrent tests
   - Redis cleanup between tests is minimal

3. **Network Dependent**
   - Test results vary with network latency
   - Firewall rules may affect connectivity

4. **RAS Server State**
   - Tests depend on RAS server configuration
   - Cluster/infobase must exist
   - Lock state persists across tests

---

## Documentation

- **Architecture:** `../../docs/architecture/`
- **API Reference:** `../../docs/api/`
- **Troubleshooting:** `../../CLAUDE.md` (Local Development Guide)
- **RAS Integration:** `../../docs/ODATA_INTEGRATION.md`

---

## Support

For issues with integration tests:

1. Check `integration_test_results.txt` for detailed errors
2. Review this README troubleshooting section
3. Check `RAS_ADAPTER_WEEK3_TEST_REPORT.md` for known issues
4. Consult project CLAUDE.md for local development setup

---

**Last Updated:** November 20, 2025
**Version:** 1.0
**Status:** Ready for Week 3 Testing
