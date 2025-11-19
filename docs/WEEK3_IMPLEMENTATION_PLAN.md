# Week 3 Implementation Plan: Integration & E2E Testing

## Дата создания: 2025-11-18
## Версия: 1.0
## Статус: APPROVED - Ready for Implementation

---

## 📊 Executive Summary

**Цель Week 3:** Завершить Event-Driven Architecture через integration testing, feature flags и production rollout.

**Общая оценка:** 27 часов работы
**Приоритет:** Критичный для production deployment
**Статус базы:** Week 1-2 завершены (149 unit tests, 5 integration tests, все блокеры исправлены)

---

## 📊 Анализ текущего состояния

### ✅ Что уже готово

**Event-Driven Infrastructure:**
- ✅ Shared Events Library (Watermill + Redis Streams)
- ✅ Worker State Machine с compensation logic
- ✅ cluster-service event handlers (lock/unlock/terminate)
- ✅ batch-service event handlers (extension install)
- ✅ orchestrator event subscriber (Python/Django)
- ✅ Prometheus metrics для events (5 метрик)
- ✅ Idempotency через Redis SetNX
- ✅ Coverage: cluster-service 81.2%, batch-service 86.5%

**Базовые Integration Tests (4 сценария):**
1. ✅ Event Flow: Publish → Subscribe
2. ✅ Idempotency: Redis SetNX mechanism
3. ✅ Correlation ID end-to-end tracing
4. ✅ Event fanout to multiple subscribers

**Worker State Machine:**
- ✅ Happy Path test работает (4.29 секунд)
- ⚠️ Только unit tests с mocks (89 тестов)
- ❌ НЕТ integration тестов для failure scenarios

### ❌ Что отсутствует (GAPs)

1. **Worker State Machine Integration Tests (9 scenarios):**
   - Lock failures
   - Terminate timeouts
   - Install failures
   - Unlock retries
   - Compensation flows
   - Out-of-order events
   - Redis unavailable
   - Worker crash/resume
   - Concurrent operations

2. **E2E Testing Infrastructure:**
   - Нет Docker Compose test environment
   - Нет реальных 1C test баз
   - Нет автоматизации E2E scenarios

3. **Performance Testing:**
   - Нет load testing framework
   - Нет benchmarks для 100+ операций
   - Нет stress testing

4. **Feature Flags:**
   - Нет dual-mode (HTTP vs Event-Driven)
   - Нет percentage rollout
   - Нет A/B testing metrics

5. **Migration Strategy:**
   - Нет rollback scripts
   - Нет phased rollout plan
   - Нет monitoring dashboards

---

## 🔍 Best Practices из исследования

### 1. Integration Testing (Testcontainers)

**Источник:** Integration Testing In Go Using Testcontainers

**Ключевые паттерны:**
```go
// Использовать testcontainers-go для Redis/PostgreSQL
container, err := testcontainers.GenericContainer(ctx, testcontainers.GenericContainerRequest{
    ContainerRequest: testcontainers.ContainerRequest{
        Image: "redis:7-alpine",
        ExposedPorts: []string{"6379/tcp"},
        WaitingFor: wait.ForListeningPort("6379/tcp"),
    },
    Started: true,
})
```

**Преимущества:**
- Изолированная test environment для каждого теста
- Автоматический cleanup
- Параллельное выполнение тестов

### 2. Feature Flags Implementation

**Источник:** Feature Flags Best Practices 2025

**Рекомендуемый подход:**
```go
type FeatureFlags struct {
    EnableEventDriven bool    `env:"ENABLE_EVENT_DRIVEN" default:"false"`
    RolloutPercentage float64 `env:"EVENT_DRIVEN_ROLLOUT_PERCENT" default:"0.0"`
}

func (p *TaskProcessor) shouldUseEventDriven() bool {
    if !p.config.EnableEventDriven {
        return false
    }
    // Percentage-based rollout
    return rand.Float64() < p.config.RolloutPercentage
}
```

**Стратегия rollout:**
- 10% → monitor 4h → 50% → monitor 4h → 100%
- Instant rollback через environment variable
- A/B testing metrics в Prometheus

### 3. Performance Testing Patterns

**Источник:** Go Concurrent Testing Best Practices

**Load testing с sync.WaitGroup:**
```go
func TestParallelOperations(t *testing.T) {
    var wg sync.WaitGroup
    errors := make(chan error, 100)

    for i := 0; i < 100; i++ {
        wg.Add(1)
        go func(id int) {
            defer wg.Done()
            if err := executeOperation(id); err != nil {
                errors <- err
            }
        }(i)
    }

    wg.Wait()
    close(errors)

    // Check errors
    var failedOps int
    for err := range errors {
        failedOps++
        t.Logf("Operation failed: %v", err)
    }

    assert.Less(t, failedOps, 5, "Less than 5% failure rate")
}
```

---

## 📋 Детальный план реализации

### Task 3.1: Integration & E2E Testing (16 часов)

#### Subtask 3.1.1: Worker State Machine Integration Tests (8 часов)

**Приоритет:** КРИТИЧНЫЙ ⚠️

**Файлы для создания:**
- `tests/integration/worker_state_machine_test.go`
- `tests/integration/testcontainers_setup.go`
- `tests/integration/mocks.go`

**9 сценариев для реализации:**

```go
// tests/integration/worker_state_machine_test.go

func TestStateMachine_LockFailed(t *testing.T) {
    // Scenario 1: RAS returns error on lock attempt
    // Expected: State = Failed, no compensation needed
}

func TestStateMachine_TerminateTimeout(t *testing.T) {
    // Scenario 2: Sessions don't close within 90s
    // Expected: State = Failed, compensation (unlock)
}

func TestStateMachine_InstallFailed(t *testing.T) {
    // Scenario 3: 1cv8.exe returns error
    // Expected: State = Failed, compensation (unlock)
}

func TestStateMachine_UnlockRetries(t *testing.T) {
    // Scenario 4: Unlock fails, retry 5 times
    // Expected: Manual action event after retries exhausted
}

func TestStateMachine_CompensationChain(t *testing.T) {
    // Scenario 5: Multiple compensations in LIFO order
    // Expected: All compensations execute despite failures
}

func TestStateMachine_DuplicateEvents(t *testing.T) {
    // Scenario 6: Same event published twice
    // Expected: Idempotent handling via deduplication
}

func TestStateMachine_OutOfOrderEvents(t *testing.T) {
    // Scenario 7: Events arrive out of sequence
    // Expected: Invalid transitions ignored
}

func TestStateMachine_RedisUnavailable(t *testing.T) {
    // Scenario 8: Redis goes down mid-workflow
    // Expected: Graceful degradation, log to PostgreSQL
}

func TestStateMachine_WorkerCrashRecovery(t *testing.T) {
    // Scenario 9: Worker crashes and restarts
    // Expected: Resume from last persisted state
}
```

**Testcontainers setup:**
```go
// tests/integration/testcontainers_setup.go

type TestEnvironment struct {
    RedisContainer     testcontainers.Container
    PostgresContainer  testcontainers.Container
    RedisClient        *redis.Client
    DB                 *sql.DB
}

func SetupTestEnvironment(t *testing.T) *TestEnvironment {
    ctx := context.Background()

    // Start Redis
    redisReq := testcontainers.ContainerRequest{
        Image:        "redis:7-alpine",
        ExposedPorts: []string{"6379/tcp"},
        WaitingFor:   wait.ForListeningPort("6379/tcp"),
    }

    // Start PostgreSQL
    postgresReq := testcontainers.ContainerRequest{
        Image:        "postgres:15-alpine",
        ExposedPorts: []string{"5432/tcp"},
        Env: map[string]string{
            "POSTGRES_PASSWORD": "test",
            "POSTGRES_DB":       "test",
        },
        WaitingFor: wait.ForSQL("5432/tcp", "postgres",
            func(port nat.Port) string {
                return fmt.Sprintf("host=localhost port=%s user=postgres password=test dbname=test sslmode=disable", port.Port())
            }),
    }

    // ... initialize containers and clients
    return &TestEnvironment{...}
}
```

**Время:** 8 часов
- Setup testcontainers: 2 часа
- Написание 9 тестов: 6 часов (40 минут/тест)

---

#### Subtask 3.1.2: E2E Tests с реальной 1C базой (4 часа)

**Приоритет:** СРЕДНИЙ

**Файл:** `tests/e2e/real_1c_extension_test.go`

```go
func TestE2E_RealExtensionInstall(t *testing.T) {
    if testing.Short() {
        t.Skip("Skipping E2E test")
    }

    // Check 1C test database availability
    testDB := os.Getenv("TEST_1C_DATABASE")
    if testDB == "" {
        t.Skip("TEST_1C_DATABASE not configured")
    }

    // Setup test environment
    env := SetupE2EEnvironment(t)
    defer env.Cleanup()

    // Create test extension (.cfe)
    extensionPath := createTestExtension(t)

    // Start all services
    startServices(t, env)

    // Execute workflow via API
    response := executeInstallWorkflow(t, testDB, extensionPath)

    // Wait for completion (max 60s)
    waitForCompletion(t, response.OperationID, 60*time.Second)

    // Verify via OData
    verifyExtensionInstalled(t, testDB, "TestExtension")

    // Cleanup
    rollbackExtension(t, testDB)
}
```

**Docker Compose для E2E:**
```yaml
# tests/e2e/docker-compose.e2e.yml
version: '3.8'

services:
  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"

  postgres:
    image: postgres:15-alpine
    environment:
      POSTGRES_PASSWORD: test
      POSTGRES_DB: commandcenter_test
    ports:
      - "5432:5432"

  ras-mock:
    build: ./mocks/ras-grpc-gw
    ports:
      - "9999:9999"
      - "8081:8081"
```

**Время:** 4 часа
- Setup E2E environment: 2 часа
- Написание тестов: 1.5 часа
- Отладка: 0.5 часа

---

#### Subtask 3.1.3: Performance Testing (4 часа)

**Приоритет:** ВЫСОКИЙ

**Файл:** `tests/performance/parallel_operations_test.go`

```go
package performance

import (
    "context"
    "sync"
    "sync/atomic"
    "testing"
    "time"

    "github.com/prometheus/client_golang/prometheus"
    "github.com/stretchr/testify/assert"
)

func TestPerformance_100ParallelOperations(t *testing.T) {
    // Skip in short mode
    if testing.Short() {
        t.Skip("Skipping performance test")
    }

    // Setup
    env := SetupPerfEnvironment(t)
    defer env.Cleanup()

    // Metrics collectors
    var (
        totalOps      int32
        successOps    int32
        failedOps     int32
        totalDuration time.Duration
    )

    // Latency histogram
    latencies := prometheus.NewHistogram(prometheus.HistogramOpts{
        Name:    "test_operation_latency",
        Buckets: []float64{.001, .005, .01, .025, .05, .1, .25, .5, 1, 2, 5, 10},
    })

    // Execute 100 parallel operations
    var wg sync.WaitGroup
    start := time.Now()

    for i := 0; i < 100; i++ {
        wg.Add(1)
        go func(opID int) {
            defer wg.Done()

            opStart := time.Now()
            err := executeTestOperation(opID, env)
            duration := time.Since(opStart)

            atomic.AddInt32(&totalOps, 1)
            latencies.Observe(duration.Seconds())

            if err != nil {
                atomic.AddInt32(&failedOps, 1)
                t.Logf("Operation %d failed: %v", opID, err)
            } else {
                atomic.AddInt32(&successOps, 1)
            }
        }(i)
    }

    wg.Wait()
    totalDuration = time.Since(start)

    // Generate report
    report := &PerformanceReport{
        TotalOperations: int(totalOps),
        SuccessCount:    int(successOps),
        FailureCount:    int(failedOps),
        TotalDuration:   totalDuration,
        OpsPerSecond:    float64(totalOps) / totalDuration.Seconds(),
        SuccessRate:     float64(successOps) / float64(totalOps),
    }

    // Calculate percentiles
    report.LatencyP50 = calculatePercentile(latencies, 0.5)
    report.LatencyP95 = calculatePercentile(latencies, 0.95)
    report.LatencyP99 = calculatePercentile(latencies, 0.99)

    // Write report to file
    saveReport(t, report, "performance_report.json")

    // Assertions
    assert.Less(t, totalDuration, 60*time.Second, "Should complete in < 60s")
    assert.Greater(t, report.SuccessRate, 0.95, "Success rate > 95%")
    assert.Less(t, report.LatencyP99, 10.0, "P99 latency < 10ms")

    // Log summary
    t.Logf("Performance Test Summary:")
    t.Logf("  Total Duration: %v", totalDuration)
    t.Logf("  Operations/sec: %.2f", report.OpsPerSecond)
    t.Logf("  Success Rate: %.2f%%", report.SuccessRate*100)
    t.Logf("  Latency P50: %.3fs", report.LatencyP50)
    t.Logf("  Latency P95: %.3fs", report.LatencyP95)
    t.Logf("  Latency P99: %.3fs", report.LatencyP99)
}

// Benchmark comparison: Event-Driven vs HTTP Sync
func BenchmarkEventDriven(b *testing.B) {
    env := SetupBenchEnvironment(b)
    defer env.Cleanup()

    b.ResetTimer()
    b.RunParallel(func(pb *testing.PB) {
        for pb.Next() {
            _ = executeEventDrivenOperation(env)
        }
    })
}

func BenchmarkHTTPSync(b *testing.B) {
    env := SetupBenchEnvironment(b)
    defer env.Cleanup()

    b.ResetTimer()
    b.RunParallel(func(pb *testing.PB) {
        for pb.Next() {
            _ = executeHTTPSyncOperation(env)
        }
    })
}
```

**Время:** 4 часа
- Setup performance environment: 1 час
- Написание тестов: 2 часа
- Benchmarking и отчеты: 1 час

---

### Task 3.2: Migration Strategy & Feature Flags (7 часов)

#### Subtask 3.2.1: Feature Flag Implementation (3 часа)

**Приоритет:** КРИТИЧНЫЙ ⚠️

**Файлы:**
- `go-services/worker/internal/config/feature_flags.go`
- `go-services/worker/internal/processor/dual_mode.go`

```go
// go-services/worker/internal/config/feature_flags.go

package config

import (
    "math/rand"
    "sync"
    "time"
)

type FeatureFlags struct {
    // Main toggle
    EnableEventDriven bool `env:"ENABLE_EVENT_DRIVEN" envDefault:"false"`

    // Percentage rollout (0.0 - 1.0)
    RolloutPercentage float64 `env:"EVENT_DRIVEN_ROLLOUT_PERCENT" envDefault:"0.0"`

    // User/Database targeting (optional)
    TargetedDatabases []string `env:"EVENT_DRIVEN_TARGET_DBS" envSeparator:","`

    // Operation type targeting
    EnableForExtensions bool `env:"EVENT_DRIVEN_EXTENSIONS" envDefault:"false"`
    EnableForBackups    bool `env:"EVENT_DRIVEN_BACKUPS" envDefault:"false"`

    // Safety switches
    MaxConcurrentEvents int `env:"EVENT_DRIVEN_MAX_CONCURRENT" envDefault:"100"`
    CircuitBreakerThreshold float64 `env:"EVENT_DRIVEN_CB_THRESHOLD" envDefault:"0.95"`

    // A/B testing
    ExperimentID string `env:"EVENT_DRIVEN_EXPERIMENT_ID" envDefault:""`

    mu sync.RWMutex
    rng *rand.Rand
}

func NewFeatureFlags() *FeatureFlags {
    return &FeatureFlags{
        rng: rand.New(rand.NewSource(time.Now().UnixNano())),
    }
}

func (ff *FeatureFlags) ShouldUseEventDriven(operationType string, databaseID string) bool {
    ff.mu.RLock()
    defer ff.mu.RUnlock()

    // Global kill switch
    if !ff.EnableEventDriven {
        return false
    }

    // Check operation type
    switch operationType {
    case "extension":
        if !ff.EnableForExtensions {
            return false
        }
    case "backup":
        if !ff.EnableForBackups {
            return false
        }
    }

    // Check targeted databases (if configured)
    if len(ff.TargetedDatabases) > 0 {
        targeted := false
        for _, db := range ff.TargetedDatabases {
            if db == databaseID {
                targeted = true
                break
            }
        }
        if targeted {
            return true // Always use for targeted DBs
        }
    }

    // Percentage-based rollout
    if ff.RolloutPercentage >= 1.0 {
        return true
    }

    // Consistent hashing for A/B testing (same DB always gets same treatment)
    if ff.ExperimentID != "" {
        hash := hashString(ff.ExperimentID + databaseID)
        threshold := uint32(ff.RolloutPercentage * float64(^uint32(0)))
        return hash < threshold
    }

    // Random rollout
    return ff.rng.Float64() < ff.RolloutPercentage
}

func (ff *FeatureFlags) Reload() error {
    // Hot reload from environment or config service
    // Implementation depends on your config management
    return nil
}

func hashString(s string) uint32 {
    h := uint32(0)
    for _, c := range s {
        h = h*31 + uint32(c)
    }
    return h
}
```

**Dual-mode processor:**
```go
// go-services/worker/internal/processor/dual_mode.go

func (p *TaskProcessor) ProcessExtensionInstall(ctx context.Context, task *Task) error {
    // Record decision metrics
    mode := "http_sync"
    if p.featureFlags.ShouldUseEventDriven("extension", task.DatabaseID) {
        mode = "event_driven"
    }

    metricsExecutionMode.WithLabelValues(mode).Inc()

    start := time.Now()
    var err error

    // Execute based on mode
    if mode == "event_driven" {
        err = p.processEventDriven(ctx, task)
    } else {
        err = p.processHTTPSync(ctx, task)
    }

    // Record metrics
    duration := time.Since(start)
    metricsExecutionDuration.WithLabelValues(mode).Observe(duration.Seconds())

    if err != nil {
        metricsExecutionFailure.WithLabelValues(mode).Inc()
        return fmt.Errorf("%s mode failed: %w", mode, err)
    }

    metricsExecutionSuccess.WithLabelValues(mode).Inc()
    return nil
}
```

**Время:** 3 часа
- Feature flags структура: 1 час
- Dual-mode implementation: 1.5 часа
- Unit tests: 0.5 часа

---

#### Subtask 3.2.2: A/B Testing Metrics (2 часа)

**Приоритет:** ВЫСОКИЙ

**Файл:** `go-services/worker/internal/metrics/ab_testing.go`

```go
package metrics

import (
    "github.com/prometheus/client_golang/prometheus"
    "github.com/prometheus/client_golang/prometheus/promauto"
)

var (
    // Execution mode counter
    executionMode = promauto.NewCounterVec(
        prometheus.CounterOpts{
            Name: "worker_execution_mode_total",
            Help: "Total executions by mode (event_driven vs http_sync)",
        },
        []string{"mode"},
    )

    // Duration by mode
    executionDuration = promauto.NewHistogramVec(
        prometheus.HistogramOpts{
            Name:    "worker_execution_duration_seconds",
            Help:    "Execution duration by mode",
            Buckets: []float64{.01, .025, .05, .1, .25, .5, 1, 2.5, 5, 10, 30},
        },
        []string{"mode"},
    )

    // Success/Failure rates
    executionSuccess = promauto.NewCounterVec(
        prometheus.CounterOpts{
            Name: "worker_execution_success_total",
            Help: "Successful executions by mode",
        },
        []string{"mode"},
    )

    executionFailure = promauto.NewCounterVec(
        prometheus.CounterOpts{
            Name: "worker_execution_failure_total",
            Help: "Failed executions by mode",
        },
        []string{"mode"},
    )

    // Compensation events
    compensationExecuted = promauto.NewCounterVec(
        prometheus.CounterOpts{
            Name: "worker_compensation_executed_total",
            Help: "Compensation actions executed",
        },
        []string{"mode", "reason"},
    )

    // Circuit breaker trips
    circuitBreakerTrips = promauto.NewCounterVec(
        prometheus.CounterOpts{
            Name: "worker_circuit_breaker_trips_total",
            Help: "Circuit breaker trips by mode",
        },
        []string{"mode"},
    )
)
```

**Grafana Dashboard config:**
```json
{
  "dashboard": {
    "title": "A/B Testing: Event-Driven vs HTTP Sync",
    "panels": [
      {
        "title": "Execution Mode Distribution",
        "type": "piechart",
        "targets": [
          {
            "expr": "sum(rate(worker_execution_mode_total[5m])) by (mode)"
          }
        ]
      },
      {
        "title": "Success Rate Comparison",
        "type": "graph",
        "targets": [
          {
            "expr": "rate(worker_execution_success_total[5m]) / rate(worker_execution_mode_total[5m])"
          }
        ]
      },
      {
        "title": "Latency P99 Comparison",
        "type": "graph",
        "targets": [
          {
            "expr": "histogram_quantile(0.99, rate(worker_execution_duration_seconds_bucket[5m]))"
          }
        ]
      }
    ]
  }
}
```

**Время:** 2 часа
- Metrics implementation: 1 час
- Grafana dashboard: 1 час

---

#### Subtask 3.2.3: Rollback Plan Documentation (2 часа)

**Приоритет:** ВЫСОКИЙ

**Файлы:**
- `docs/EVENT_DRIVEN_ROLLBACK_PLAN.md`
- `scripts/rollback-event-driven.sh`

**Rollback Plan Documentation:**
```markdown
# Event-Driven Architecture Rollback Plan

## Quick Rollback (< 2 minutes)

### Step 1: Disable Feature Flag
```bash
# Set in .env.local or environment
export ENABLE_EVENT_DRIVEN=false
export EVENT_DRIVEN_ROLLOUT_PERCENT=0.0
```

### Step 2: Restart Workers
```bash
./scripts/rollback-event-driven.sh
```

## Rollback Triggers

### Automatic Rollback (Circuit Breaker)
- Success rate < 95% for 5 minutes
- P99 latency > 1 second
- Compensation rate > 10%
- Redis unavailable > 1 minute

### Manual Rollback Criteria
- User reports of stuck operations
- Database locks not releasing
- Memory/CPU spike > 200%
- Error rate increase > 5%

## Verification Steps

1. Check metrics dashboard
2. Verify HTTP sync mode active
3. Check Redis queue is empty
4. Verify no stuck operations
5. Monitor for 30 minutes
```

**Rollback Script:**
```bash
#!/bin/bash
# scripts/rollback-event-driven.sh

set -e

echo "🔄 Starting Event-Driven rollback..."

# Step 1: Update configuration
echo "📝 Updating configuration..."
sed -i 's/ENABLE_EVENT_DRIVEN=true/ENABLE_EVENT_DRIVEN=false/' .env.local
sed -i 's/EVENT_DRIVEN_ROLLOUT_PERCENT=.*/EVENT_DRIVEN_ROLLOUT_PERCENT=0.0/' .env.local

# Step 2: Restart workers
echo "🔄 Restarting workers..."
./scripts/dev/restart.sh worker

# Step 3: Verify rollback
echo "✅ Verifying rollback..."
sleep 5
curl -s http://localhost:9090/api/v1/query?query=worker_execution_mode_total | \
  jq '.data.result[] | select(.metric.mode=="http_sync")'

# Step 4: Flush Redis channels (optional)
echo "🧹 Flushing Redis event channels..."
redis-cli --scan --pattern "events:*" | xargs -L 1 redis-cli DEL

echo "✅ Rollback complete!"
echo "📊 Check metrics: http://localhost:3001/d/ab-testing"
```

**Tiempo:** 2 часа
- Documentation: 1 час
- Scripts и alerts: 1 час

---

### Task 3.3: Production Rollout (4 часа)

#### Phase 1: 10% Rollout (1.5 часа)

**Файл:** `scripts/rollout/phase1.sh`

```bash
#!/bin/bash
# scripts/rollout/phase1.sh

echo "🚀 Phase 1: 10% Rollout"

# Pre-flight checks
./scripts/rollout/preflight-checks.sh

# Update configuration
export ENABLE_EVENT_DRIVEN=true
export EVENT_DRIVEN_ROLLOUT_PERCENT=0.10

# Deploy
./scripts/dev/restart.sh worker

# Monitor
echo "📊 Monitoring dashboard: http://localhost:3001/d/rollout"
echo "⏰ Monitoring for 4 hours..."

# Auto-rollback on failure
./scripts/rollout/monitor.sh --duration=4h --threshold=0.95 --auto-rollback
```

#### Phase 2: 50% Rollout (1.5 часа)

**Файл:** `scripts/rollout/phase2.sh`

```bash
#!/bin/bash
# scripts/rollout/phase2.sh

echo "🚀 Phase 2: 50% Rollout"

# Check Phase 1 metrics
PHASE1_SUCCESS=$(./scripts/rollout/check-metrics.sh --phase=1)
if [ "$PHASE1_SUCCESS" != "true" ]; then
    echo "❌ Phase 1 metrics not meeting criteria"
    exit 1
fi

# Update to 50%
export EVENT_DRIVEN_ROLLOUT_PERCENT=0.50
./scripts/dev/restart.sh worker

# Continue monitoring
./scripts/rollout/monitor.sh --duration=4h --threshold=0.95
```

#### Phase 3: 100% Rollout (1 час)

**Файл:** `scripts/rollout/phase3.sh`

```bash
#!/bin/bash
# scripts/rollout/phase3.sh

echo "🚀 Phase 3: 100% Rollout"

# Final checks
./scripts/rollout/final-checks.sh

# Full rollout
export EVENT_DRIVEN_ROLLOUT_PERCENT=1.0
./scripts/dev/restart.sh worker

echo "✅ Event-Driven architecture fully deployed!"
echo "📊 Monitor: http://localhost:3001/d/rollout"
```

---

## 📊 Оценка времени и рисков

### Временные оценки

| Task | Оценка | Приоритет | Риск |
|------|--------|-----------|------|
| **3.1.1: Worker SM Integration Tests** | 8ч | КРИТИЧНЫЙ | Средний |
| **3.1.2: E2E Tests** | 4ч | СРЕДНИЙ | Высокий |
| **3.1.3: Performance Testing** | 4ч | ВЫСОКИЙ | Низкий |
| **3.2.1: Feature Flags** | 3ч | КРИТИЧНЫЙ | Низкий |
| **3.2.2: A/B Metrics** | 2ч | ВЫСОКИЙ | Низкий |
| **3.2.3: Rollback Plan** | 2ч | ВЫСОКИЙ | Низкий |
| **3.3: Production Rollout** | 4ч | СРЕДНИЙ | Высокий |
| **ИТОГО** | **27 часов** | | |

### Риски и митигация

**Риск 1: Сложность integration тестов**
- **Вероятность:** Высокая
- **Воздействие:** Задержка 4-6 часов
- **Митигация:** Использовать testcontainers, готовые примеры из open source

**Риск 2: Отсутствие тестовых 1C баз**
- **Вероятность:** Средняя
- **Воздействие:** E2E тесты невозможны
- **Митигация:** Mock 1C responses, focus на integration tests

**Риск 3: Performance degradation**
- **Вероятность:** Низкая
- **Воздействие:** Rollback required
- **Митигация:** Gradual rollout, circuit breakers, instant rollback

---

## 🎯 Рекомендации по приоритизации

### Что делать в первую очередь (Must Have)

1. **Feature Flags Implementation (3ч)** - без этого невозможен безопасный rollout
2. **Worker SM Integration Tests - первые 3 сценария (3ч)** - критичные failure cases
3. **Rollback Plan & Script (2ч)** - safety net обязателен

**Итого Must Have: 8 часов**

### Что делать во вторую очередь (Should Have)

4. **A/B Testing Metrics (2ч)** - для принятия решений о rollout
5. **Performance Testing базовый (2ч)** - хотя бы 50 операций
6. **Остальные 6 Worker SM тестов (5ч)** - полное покрытие

**Итого Should Have: 9 часов**

### Что можно отложить (Nice to Have)

7. **E2E Tests с реальной 1C (4ч)** - можно заменить на mocks
8. **Production Rollout автоматизация (4ч)** - можно делать вручную
9. **Расширенный performance testing (2ч)** - 100+ операций

**Итого Nice to Have: 10 часов**

---

## 🚀 План быстрого старта (1 день)

Если есть только 8 часов, фокус на критичном:

**Morning (4 часа):**
1. Feature Flags basic implementation - 2ч
2. Rollback script - 1ч
3. Один integration test (Lock Failed) - 1ч

**Afternoon (4 часа):**
4. A/B metrics (basic) - 1ч
5. Performance test (10 operations) - 1ч
6. Manual rollout plan (documentation) - 1ч
7. Testing & fixes - 1ч

---

## 📝 Implementation Checklist

### Task 3.1: Integration & E2E Testing

**Subtask 3.1.1: Worker State Machine Integration Tests (8h)**
- [ ] Setup testcontainers infrastructure
- [ ] Create test environment setup/teardown
- [ ] Test 1: Lock Failed scenario
- [ ] Test 2: Terminate Timeout scenario
- [ ] Test 3: Install Failed scenario
- [ ] Test 4: Unlock Retries scenario
- [ ] Test 5: Compensation Chain scenario
- [ ] Test 6: Duplicate Events scenario
- [ ] Test 7: Out-of-Order Events scenario
- [ ] Test 8: Redis Unavailable scenario
- [ ] Test 9: Worker Crash Recovery scenario

**Subtask 3.1.2: E2E Tests (4h)**
- [ ] Create Docker Compose test environment
- [ ] Setup test 1C database (or mocks)
- [ ] Create test extension (.cfe)
- [ ] Write E2E test: Full installation workflow
- [ ] Verification via OData
- [ ] Cleanup and rollback logic

**Subtask 3.1.3: Performance Testing (4h)**
- [ ] Setup performance test environment
- [ ] Write parallel operations test (100 ops)
- [ ] Implement latency histogram
- [ ] Create performance report generator
- [ ] Write benchmark: Event-Driven vs HTTP Sync
- [ ] Document performance results

### Task 3.2: Migration Strategy & Feature Flags

**Subtask 3.2.1: Feature Flags (3h)**
- [ ] Create FeatureFlags struct
- [ ] Implement ShouldUseEventDriven logic
- [ ] Add percentage-based rollout
- [ ] Add database targeting
- [ ] Implement dual-mode processor
- [ ] Write unit tests

**Subtask 3.2.2: A/B Testing Metrics (2h)**
- [ ] Create Prometheus metrics
- [ ] Implement metrics collection
- [ ] Create Grafana dashboard JSON
- [ ] Test metrics collection
- [ ] Document metrics usage

**Subtask 3.2.3: Rollback Plan (2h)**
- [ ] Write rollback documentation
- [ ] Create rollback script
- [ ] Define rollback triggers
- [ ] Create monitoring alerts
- [ ] Test rollback procedure

### Task 3.3: Production Rollout

**Phase 1: 10% Rollout (1.5h)**
- [ ] Create phase1.sh script
- [ ] Pre-flight checks
- [ ] Update configuration to 10%
- [ ] Deploy and monitor
- [ ] Validate metrics

**Phase 2: 50% Rollout (1.5h)**
- [ ] Create phase2.sh script
- [ ] Check Phase 1 success criteria
- [ ] Update configuration to 50%
- [ ] Deploy and monitor
- [ ] Validate metrics

**Phase 3: 100% Rollout (1h)**
- [ ] Create phase3.sh script
- [ ] Final pre-flight checks
- [ ] Update configuration to 100%
- [ ] Deploy and monitor
- [ ] Celebrate success! 🎉

---

## 📚 Appendix: Dependencies

**Go Packages Required:**
```bash
go get github.com/testcontainers/testcontainers-go
go get github.com/prometheus/client_golang/prometheus
go get github.com/stretchr/testify/assert
```

**Documentation References:**
- EVENT_DRIVEN_ROADMAP.md - Исходный roadmap
- EVENT_DRIVEN_ARCHITECTURE.md - Архитектурный дизайн
- ROADMAP.md - Общий проектный roadmap
- LOCAL_DEVELOPMENT_GUIDE.md - Dev environment setup

---

## 🎯 Success Criteria

**Week 3 считается завершенной когда:**

1. ✅ 9 Worker State Machine integration тестов написаны и PASS
2. ✅ Feature Flags реализованы и протестированы
3. ✅ Rollback script работает (< 2 минуты для rollback)
4. ✅ A/B Testing metrics собираются в Prometheus
5. ✅ Performance test показывает улучшение vs HTTP Sync
6. ✅ Grafana dashboard создан для monitoring
7. ✅ Production rollout plan задокументирован
8. ✅ E2E test работает (или documented why skipped)

---

**Документ одобрен:** 2025-11-18
**Готов к реализации:** ДА
**Следующий шаг:** Запуск Coder агента для Task 3.1.1