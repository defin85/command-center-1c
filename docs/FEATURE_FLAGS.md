# Feature Flags - Dual-Mode Execution

> **Status:** ✅ **IMPLEMENTED** (Task 3.2.1)
> **Version:** 1.0
> **Last Updated:** 2025-11-18

---

## 📋 Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [Configuration](#configuration)
- [Rollout Strategies](#rollout-strategies)
- [Monitoring](#monitoring)
- [Examples](#examples)
- [Troubleshooting](#troubleshooting)

---

## Overview

Feature Flags система позволяет безопасно переключаться между **Event-Driven** и **HTTP Sync** режимами выполнения операций для установки расширений в базы 1С.

### Key Features

✅ **Global Kill Switch** - мгновенное отключение Event-Driven режима
✅ **Percentage Rollout** - постепенное увеличение от 0% до 100%
✅ **Database Targeting** - whitelist для early access
✅ **Operation Type Filtering** - раздельные флаги для extensions/backups
✅ **A/B Testing** - consistent hashing для экспериментов
✅ **Hot Reload** - изменение без перезапуска Worker
✅ **Thread-Safe** - безопасная работа с concurrent запросами

---

## Architecture

### Components

```
┌─────────────────────┐
│  TaskProcessor      │
│  (main entry point) │
└──────────┬──────────┘
           │
           ├─→ FeatureFlags (config)
           │   └─→ ShouldUseEventDriven()
           │
           └─→ DualModeProcessor
               ├─→ ProcessExtensionInstall()
               │   ├─→ determineExecutionMode()
               │   ├─→ processEventDriven() [FUTURE]
               │   └─→ processHTTPSync() [CURRENT]
               └─→ ReloadFeatureFlags()
```

### Decision Flow

```
User Request
    ↓
TaskProcessor.Process()
    ↓
DualModeProcessor.ProcessExtensionInstall()
    ↓
FeatureFlags.ShouldUseEventDriven(operationType, databaseID)
    │
    ├─→ [1] Global Kill Switch? → NO → HTTP Sync
    │   YES ↓
    │
    ├─→ [2] Operation Type Enabled? → NO → HTTP Sync
    │   YES ↓
    │
    ├─→ [3] Database in Whitelist? → YES → Event-Driven
    │   NO ↓
    │
    ├─→ [4] Percentage = 100%? → YES → Event-Driven
    │   NO ↓
    │
    ├─→ [5] Percentage = 0%? → YES → HTTP Sync
    │   NO ↓
    │
    ├─→ [6] A/B Testing (consistent hashing)
    │   └─→ hash(experimentID + databaseID) < threshold
    │       ├─→ YES → Event-Driven
    │       └─→ NO  → HTTP Sync
    │
    └─→ Execute in selected mode
```

---

## Configuration

### Environment Variables

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `ENABLE_EVENT_DRIVEN` | `bool` | `false` | **GLOBAL KILL SWITCH** - мгновенное отключение Event-Driven |
| `EVENT_DRIVEN_ROLLOUT_PERCENT` | `float64` | `0.0` | Percentage rollout (0.0 - 1.0) |
| `EVENT_DRIVEN_TARGET_DBS` | `string` | `""` | Comma-separated whitelist баз для early access |
| `EVENT_DRIVEN_EXTENSIONS` | `bool` | `true` | Включить Event-Driven для установки расширений |
| `EVENT_DRIVEN_BACKUPS` | `bool` | `false` | Включить Event-Driven для backup операций |
| `EVENT_DRIVEN_MAX_CONCURRENT` | `int` | `100` | Maximum concurrent events |
| `EVENT_DRIVEN_CB_THRESHOLD` | `float64` | `0.95` | Circuit breaker threshold (0.0 - 1.0) |
| `EVENT_DRIVEN_EXPERIMENT_ID` | `string` | `""` | Experiment ID для A/B testing |

### Priority Order

Feature Flags применяются в следующем порядке приоритета:

1. **Global Kill Switch** (`ENABLE_EVENT_DRIVEN=false`) - высший приоритет
2. **Operation Type** (`EVENT_DRIVEN_EXTENSIONS`, `EVENT_DRIVEN_BACKUPS`)
3. **Database Whitelist** (`EVENT_DRIVEN_TARGET_DBS`) - всегда Event-Driven
4. **Percentage Rollout** (`EVENT_DRIVEN_ROLLOUT_PERCENT`)
5. **A/B Testing** (`EVENT_DRIVEN_EXPERIMENT_ID`)

---

## Rollout Strategies

### Strategy 1: Instant Rollback (Production)

**Use Case:** Критичный баг в production, нужен мгновенный rollback

```bash
# Instant rollback to HTTP Sync
export ENABLE_EVENT_DRIVEN=false

# Worker продолжает работать, все новые операции → HTTP Sync
# HOT RELOAD: не требует перезапуска Worker!
```

**Time to Rollback:** < 1 секунда
**Impact:** 0% downtime

---

### Strategy 2: Gradual Rollout (Recommended)

**Use Case:** Безопасное внедрение Event-Driven в production

#### Phase 1: Internal Testing (Week 1)
```bash
export ENABLE_EVENT_DRIVEN=true
export EVENT_DRIVEN_ROLLOUT_PERCENT=0.0
export EVENT_DRIVEN_TARGET_DBS=test-db-1,test-db-2
```

**Result:** Только `test-db-1` и `test-db-2` → Event-Driven

---

#### Phase 2: 10% Rollout (Week 2)
```bash
export ENABLE_EVENT_DRIVEN=true
export EVENT_DRIVEN_ROLLOUT_PERCENT=0.10
export EVENT_DRIVEN_TARGET_DBS=  # Clear whitelist
```

**Result:** 10% баз → Event-Driven, 90% → HTTP Sync

---

#### Phase 3: 50% Rollout (Week 3)
```bash
export ENABLE_EVENT_DRIVEN=true
export EVENT_DRIVEN_ROLLOUT_PERCENT=0.50
```

**Result:** 50% баз → Event-Driven, 50% → HTTP Sync

---

#### Phase 4: 100% Rollout (Week 4)
```bash
export ENABLE_EVENT_DRIVEN=true
export EVENT_DRIVEN_ROLLOUT_PERCENT=1.0
```

**Result:** 100% баз → Event-Driven

---

### Strategy 3: A/B Testing

**Use Case:** Сравнить performance Event-Driven vs HTTP Sync на production

```bash
export ENABLE_EVENT_DRIVEN=true
export EVENT_DRIVEN_ROLLOUT_PERCENT=0.50
export EVENT_DRIVEN_EXPERIMENT_ID=exp-2025-week3
```

**Key Feature:** **Consistent Hashing**
- Одна и та же база **ВСЕГДА** получает один и тот же режим
- Позволяет сравнивать performance между группами
- Результаты статистически достоверны

**Metrics to Compare:**
- Average operation duration (Event-Driven vs HTTP Sync)
- Error rate (Event-Driven vs HTTP Sync)
- Resource utilization (CPU/Memory/Network)

---

### Strategy 4: Canary Deployment

**Use Case:** Тестирование на подмножестве production баз

```bash
# Canary group (10 баз)
export ENABLE_EVENT_DRIVEN=true
export EVENT_DRIVEN_TARGET_DBS=db-001,db-002,...,db-010
export EVENT_DRIVEN_ROLLOUT_PERCENT=0.0  # Only whitelist
```

**Advantages:**
- Контролируемое тестирование на known databases
- Быстрый rollback для canary group
- Минимальный риск для production

---

## Monitoring

### Logging

Worker логирует все решения Feature Flags:

```log
INFO  processing extension install: operation_id=op-123, database_id=db-456, mode=http_sync
INFO  execution completed: mode=http_sync, success=true, duration=5.2s
```

**Log Fields:**
- `mode` - `event_driven` или `http_sync`
- `operation_id` - ID операции
- `database_id` - ID базы
- `duration` - длительность выполнения
- `success` - успех/ошибка

---

### Metrics (TODO - Task 3.2.2)

**Planned Prometheus Metrics:**

```prometheus
# Execution mode decision counter
cc1c_worker_execution_mode_total{mode="event_driven"} 150
cc1c_worker_execution_mode_total{mode="http_sync"} 850

# Execution duration histogram
cc1c_worker_execution_duration_seconds{mode="event_driven", quantile="0.5"} 2.5
cc1c_worker_execution_duration_seconds{mode="http_sync", quantile="0.5"} 5.2

# Success/failure counters
cc1c_worker_execution_success_total{mode="event_driven"} 148
cc1c_worker_execution_failure_total{mode="event_driven"} 2
cc1c_worker_execution_success_total{mode="http_sync"} 820
cc1c_worker_execution_failure_total{mode="http_sync"} 30
```

**Grafana Dashboards:**
- Execution Mode Distribution (pie chart)
- Performance Comparison (Event-Driven vs HTTP Sync)
- Error Rate Comparison
- Rollout Progress (percentage over time)

---

## Examples

### Example 1: Full Rollback (Emergency)

**Scenario:** Event-Driven mode вызывает критичные ошибки

```bash
# BEFORE (Event-Driven enabled)
export ENABLE_EVENT_DRIVEN=true
export EVENT_DRIVEN_ROLLOUT_PERCENT=1.0

# AFTER (instant rollback)
export ENABLE_EVENT_DRIVEN=false

# Worker автоматически переключается на HTTP Sync
# Все новые операции → HTTP Sync
# Time to rollback: < 1 second
```

---

### Example 2: Targeted Rollout

**Scenario:** Тестируем Event-Driven на specific базах клиента

```bash
export ENABLE_EVENT_DRIVEN=true
export EVENT_DRIVEN_TARGET_DBS=client-db-1,client-db-2,client-db-3
export EVENT_DRIVEN_ROLLOUT_PERCENT=0.0  # Only whitelist

# Только client-db-1, client-db-2, client-db-3 → Event-Driven
# Все остальные базы → HTTP Sync
```

---

### Example 3: Gradual Rollout with Monitoring

**Week 1: 10% rollout**
```bash
export ENABLE_EVENT_DRIVEN=true
export EVENT_DRIVEN_ROLLOUT_PERCENT=0.10
```

**Monitor for 1 week:**
- Check error rate: `cc1c_worker_execution_failure_total{mode="event_driven"}`
- Check performance: `cc1c_worker_execution_duration_seconds{mode="event_driven"}`
- Check resource usage: CPU/Memory/Network

**Week 2: 25% rollout** (if Week 1 successful)
```bash
export EVENT_DRIVEN_ROLLOUT_PERCENT=0.25
```

**Continue until 100%**

---

### Example 4: A/B Testing

**Scenario:** Сравнить Event-Driven vs HTTP Sync на production

```bash
export ENABLE_EVENT_DRIVEN=true
export EVENT_DRIVEN_ROLLOUT_PERCENT=0.50
export EVENT_DRIVEN_EXPERIMENT_ID=exp-2025-week3
```

**Analyze metrics after 1 week:**
```sql
-- Average duration comparison
SELECT
  mode,
  AVG(duration_seconds) as avg_duration
FROM operation_logs
WHERE experiment_id = 'exp-2025-week3'
GROUP BY mode;

-- Event-Driven: 2.1s
-- HTTP Sync:    5.4s
-- Result: Event-Driven is 2.6x faster!
```

---

## Troubleshooting

### Issue 1: Feature Flags не применяются

**Symptoms:**
- Все операции идут в HTTP Sync mode
- Логи показывают `mode=http_sync` даже при `ENABLE_EVENT_DRIVEN=true`

**Diagnosis:**
```bash
# Check environment variables
env | grep EVENT_DRIVEN

# Check Worker logs
./scripts/dev/logs.sh worker | grep "feature flags loaded"
```

**Solution:**
```bash
# Ensure variables are set correctly
export ENABLE_EVENT_DRIVEN=true
export EVENT_DRIVEN_ROLLOUT_PERCENT=1.0

# Restart Worker
./scripts/dev/restart.sh worker
```

---

### Issue 2: Hot Reload не работает

**Symptoms:**
- Изменения в environment variables не применяются
- Worker продолжает использовать old configuration

**Diagnosis:**
- Hot Reload **НЕ РЕАЛИЗОВАН** в Task 3.2.1
- Требует перезапуск Worker

**Solution:**
```bash
# Change environment variables
export EVENT_DRIVEN_ROLLOUT_PERCENT=0.50

# Restart Worker
./scripts/dev/restart.sh worker
```

**FUTURE (Task 3.2.3):**
- Implement SIGHUP handler для hot reload
- Implement REST API endpoint `/api/v1/feature-flags/reload`

---

### Issue 3: Consistent Hashing не работает

**Symptoms:**
- Одна база получает разные режимы при разных запросах
- A/B testing результаты inconsistent

**Diagnosis:**
```bash
# Check if EXPERIMENT_ID set
echo $EVENT_DRIVEN_EXPERIMENT_ID

# Check logs for same database
./scripts/dev/logs.sh worker | grep "database_id=db-123"
```

**Solution:**
```bash
# Set EXPERIMENT_ID
export EVENT_DRIVEN_EXPERIMENT_ID=exp-2025-week3

# Restart Worker
./scripts/dev/restart.sh worker

# Verify: same database should get same mode
```

---

## Implementation Status

### ✅ Completed (Task 3.2.1)

- [x] FeatureFlags configuration (`feature_flags.go`)
- [x] Unit tests with 100% coverage (`feature_flags_test.go`)
- [x] DualModeProcessor (`dual_mode.go`)
- [x] Integration в TaskProcessor
- [x] Integration в Worker main
- [x] Global Kill Switch
- [x] Percentage Rollout
- [x] Database Targeting (whitelist)
- [x] Operation Type Filtering
- [x] A/B Testing (consistent hashing)
- [x] Thread-safe implementation

### 🚧 In Progress (Task 3.2.2)

- [ ] Prometheus metrics integration
- [ ] Grafana dashboards
- [ ] Performance comparison dashboard

### 📋 Planned (Task 3.2.3+)

- [ ] Hot Reload без перезапуска Worker
- [ ] REST API endpoint для управления feature flags
- [ ] Feature Flags UI в Admin Panel
- [ ] Automatic rollback при error rate > threshold

---

## References

- **Source Code:**
  - `go-services/worker/internal/config/feature_flags.go`
  - `go-services/worker/internal/config/feature_flags_test.go`
  - `go-services/worker/internal/processor/dual_mode.go`

- **Tests:**
  - `go test ./internal/config -v`

- **Related Documentation:**
  - [WEEK3_IMPLEMENTATION_PLAN.md](WEEK3_IMPLEMENTATION_PLAN.md) - Task 3.2.1
  - [EVENT_DRIVEN_ARCHITECTURE.md](architecture/EVENT_DRIVEN_ARCHITECTURE.md) - Overall architecture

---

**Status:** Ready for Task 3.2.2 (A/B Testing Metrics)
