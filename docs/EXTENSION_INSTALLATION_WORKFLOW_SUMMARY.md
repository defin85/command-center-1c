# Extension Installation Workflow - Executive Summary

**Версия:** 1.0
**Дата:** 2025-11-12
**Полная документация:** [EXTENSION_INSTALLATION_WORKFLOW.md](EXTENSION_INSTALLATION_WORKFLOW.md)

---

## Проблема

**Текущая реализация НЕ работает:**
```
Worker → Batch Service:
  1. LoadCfg (.cfe file) ✅
  2. ForceTerminateSessions ✅
  3. UpdateDBCfg → ❌ exit code 101 (база занята)
```

**Почему exit code 101?**
- Регламентные задания **НЕ заблокированы** → продолжают создавать новые сеансы
- UpdateDBCfg требует **эксклюзивную блокировку** → не может получить доступ

---

## Правильный Workflow

```
1. Блокировка регламентных заданий (через RAS)
2. Завершение ВСЕХ активных сеансов
3. LoadCfg (загрузка .cfe файла)
4. UpdateDBCfg (применение к БД) → теперь работает ✅
5. Разблокировка регламентных заданий
```

**Критично:** Регламентные задания должны быть заблокированы **ДО** ForceTerminate!

---

## Рекомендуемое решение

### **Option B: Worker-Orchestrated Workflow** ⭐

**Архитектура:**
```go
Worker executeExtensionInstall():
  1. Lock Scheduled Jobs (cluster-service API)
  2. Terminate All Sessions (cluster-service API)
  3. Poll until sessions=0 (max 30 sec)
  4. Install Extension (batch-service API)
  5. Unlock Scheduled Jobs (cluster-service API)
  6. Rollback на каждом failure шаге (defer unlock)
```

**Почему этот вариант?**
- ✅ **Minimal Latency** - 1 network hop (Worker → cluster-service)
- ✅ **Self-Contained** - Весь workflow в одном месте
- ✅ **Production Ready** - Используем существующую инфраструктуру
- ✅ **Simple Rollback** - `defer workflow.UnlockScheduledJobs()`
- ✅ **Parallel Execution** - 100-500 workers независимо

**Performance:**
- 1 база: ~1-2 минуты
- 700 баз (parallel): ~10-20 минут ✅

---

## RAS API (уже доступен!)

**Proto file:** `ras-grpc-gw/accessapis/infobase/service/management.proto`

```protobuf
service InfobaseManagementService {
  rpc LockInfobase(LockInfobaseRequest) returns (LockInfobaseResponse);
  rpc UnlockInfobase(UnlockInfobaseRequest) returns (UnlockInfobaseResponse);
}

message LockInfobaseRequest {
  string cluster_id = 1;
  string infobase_id = 2;
  bool scheduled_jobs_deny = 8;  // ✅ Блокировка регламентных заданий
  ...
}
```

**Статус:** ✅ gRPC proto уже существует, нужны только HTTP handlers в cluster-service

---

## Что нужно добавить

### 1. cluster-service (2-4 часа)

**New endpoints:**
```
POST /api/v1/infobases/{id}/lock-scheduled-jobs
POST /api/v1/infobases/{id}/unlock-scheduled-jobs
```

**Implementation:**
- File: `go-services/cluster-service/internal/service/infobase_management.go` (NEW)
- File: `go-services/cluster-service/internal/api/handlers/infobase_lock.go` (NEW)
- gRPC client wrapper для `LockInfobase()` и `UnlockInfobase()`

---

### 2. Worker workflow (4-6 часов)

**New file:** `go-services/worker/internal/processor/extension_workflow.go`

```go
type ExtensionInstallWorkflow struct {
    databaseID      string
    extensionConfig ExtensionConfig
    jobsLocked      bool  // For rollback tracking
}

func (w *ExtensionInstallWorkflow) Execute(ctx context.Context) error {
    defer func() {
        if w.jobsLocked {
            w.UnlockScheduledJobs(context.Background())  // Rollback
        }
    }()

    // 5-step workflow
    w.LockScheduledJobs(ctx)
    w.TerminateAllSessions(ctx)
    w.WaitSessionsClear(ctx, 30*time.Second)
    w.InstallExtension(ctx)
    w.UnlockScheduledJobs(ctx)
}
```

---

### 3. Orchestrator endpoint (2 часа)

**New endpoint:** `GET /api/v1/databases/{id}/cluster-metadata`

**Response:**
```json
{
  "cluster_id": "uuid",
  "infobase_id": "uuid",
  "cluster_server": "localhost:1545",
  "cluster_user": "admin"
}
```

**Зачем?** Worker нуждается в cluster_id и infobase_id для вызова cluster-service

---

## Error Handling

### Rollback Strategy

```go
defer func() {
    if w.jobsLocked {
        unlockCtx := context.WithTimeout(context.Background(), 10*time.Second)
        if err := w.UnlockScheduledJobs(unlockCtx); err != nil {
            // CRITICAL: Alert administrators
            log.Errorf("CRITICAL: failed to unlock scheduled jobs: %v", err)
        }
    }
}()
```

**Важно:**
- Используй `context.Background()` для rollback (не зависит от cancelled parent context)
- Alert administrators если unlock failed

---

### Failure Scenarios

| Scenario | Rollback | Retry | User Notification |
|----------|----------|-------|-------------------|
| **Lock failed** | ❌ None | ✅ 3 retries | "Failed to lock scheduled jobs" |
| **Terminate failed** | ✅ Unlock | ✅ 2 retries | Warning: "Failed to terminate N sessions" |
| **Timeout sessions** | ✅ Unlock | ❌ No retry | "Timeout waiting for sessions" |
| **LoadCfg failed** | ✅ Unlock | ❌ No retry | "Failed to load extension" |
| **UpdateDBCfg failed** | ✅ Unlock | ✅ 1 retry | "Failed to update DB config" |
| **Unlock failed** | 🚨 Alert | ✅ 3 retries | "CRITICAL: Manual unlock required" |

---

## Implementation Plan

### Phase 1: cluster-service (2-4 часа)
1. Добавить `InfobaseManagementService` (gRPC wrapper)
2. Добавить HTTP handlers для lock/unlock
3. Update router
4. Unit tests

### Phase 2: Worker workflow (4-6 часов)
1. Create `ExtensionInstallWorkflow`
2. HTTP helpers (retry logic)
3. Modify `extension_handler.go`
4. Unit tests

### Phase 3: Integration testing (2-3 часа)
1. End-to-end test на dev окружении
2. Error scenarios testing
3. Load testing (10 баз parallel)

### Phase 4: Django integration (2 часа)
1. Add cluster metadata endpoint
2. Update Database model
3. Documentation

**Total:** **10-15 часов** (1.5-2 дня)

---

## Risks & Mitigation

### Risk 1: UnlockScheduledJobs failed (CRITICAL)

**Likelihood:** LOW
**Impact:** CRITICAL

**Mitigation:**
- ✅ Retry 3 раза
- ✅ Alert administrators через Prometheus
- ✅ Manual unlock procedure в документации

**Manual unlock:**
```
1. Открыть консоль администрирования 1С
2. Подключиться к кластеру
3. Найти информационную базу
4. Properties → Scheduled Jobs → Unblock
```

---

### Risk 2: Новые сеансы между Terminate и UpdateDBCfg

**Likelihood:** MEDIUM
**Impact:** MEDIUM

**Mitigation:**
- ✅ LockScheduledJobs предотвращает автоматические сеансы
- ✅ Polling `WaitSessionsClear()` гарантирует sessions=0
- ⚠️ Добавить `sessions_deny=true` для блокировки ВСЕХ сеансов

---

### Risk 3: Timeout ожидания sessions=0

**Likelihood:** MEDIUM
**Impact:** MEDIUM

**Mitigation:**
- ✅ Configurable timeout (env variable)
- ✅ Увеличить до 60 секунд для production
- ⚠️ Некоторые регламентные задания могут выполняться >30 сек

---

## Performance Estimates

### Single Database

| Step | Time (sec) |
|------|------------|
| Fetch metadata | 0.1-0.3 |
| Lock scheduled jobs | 0.1-0.5 |
| Terminate sessions | 0.5-2.0 |
| Wait sessions=0 | 0-30 |
| LoadCfg | 5-10 |
| UpdateDBCfg | 10-30 |
| Unlock scheduled jobs | 0.1-0.5 |

**Total:** **16-73 seconds** (average: ~60 seconds)

---

### Parallel Execution (700 databases)

**Sequential:** 700 × 60s = **42,000 seconds** (11.7 hours) ❌

**Parallel (100 workers):** 700 / 100 × 60s = **420 seconds** (~7 minutes) ✅

**With 20% failures + retries:** **~10-15 minutes** ✅

---

## Monitoring

### Prometheus Metrics

```go
extension_install_duration_seconds{step, status}  // Histogram
extension_install_errors_total{step, error_type}  // Counter
scheduled_jobs_unlock_failures_total              // Counter (CRITICAL)
```

### Grafana Alerts

```yaml
- alert: ScheduledJobsUnlockFailed
  expr: increase(scheduled_jobs_unlock_failures_total[5m]) > 0
  severity: critical
  message: "Manual intervention required!"
```

---

## Next Steps

1. ✅ **Утвердить архитектурное решение** с пользователем
2. ⏳ **Начать реализацию** с Phase 1 (cluster-service)
3. ⏳ **Протестировать** на dev окружении (1-2 базы)
4. ⏳ **Развернуть** на production после успешного тестирования

---

## Сравнение вариантов

| Критерий | Option A (Orchestrator) | **Option B (Worker)** ⭐ | Option C (Batch Service) |
|----------|-------------------------|--------------------------|--------------------------|
| **Latency** | High (2 hops) | ✅ Low (1 hop) | Low (1 hop) |
| **Complexity** | High (Saga state) | ✅ Medium | High (tight coupling) |
| **Testability** | Medium | ✅ High | Low (mixed concerns) |
| **Scalability** | Medium (bottleneck) | ✅ High (parallel) | High (parallel) |
| **Rollback** | Complex | ✅ Simple (defer) | Medium |
| **SRP** | Good | ✅ Good | ❌ Violates |
| **Time to implement** | 15-20 hours | ✅ **10-15 hours** | 12-18 hours |

---

## Заключение

**Рекомендация:** **Option B (Worker-Orchestrated Workflow)**

Это решение обеспечивает:
- ✅ Минимальную latency
- ✅ Четкий rollback logic
- ✅ Production-ready масштабирование
- ✅ Простоту тестирования и поддержки

**Estimated implementation time:** 10-15 часов (1.5-2 дня)

---

**Полная документация:** [EXTENSION_INSTALLATION_WORKFLOW.md](EXTENSION_INSTALLATION_WORKFLOW.md)

**См. также:**
- `docs/1C_ADMINISTRATION_GUIDE.md` - RAS/RAC управление
- `docs/DJANGO_CLUSTER_INTEGRATION.md` - cluster-service интеграция
