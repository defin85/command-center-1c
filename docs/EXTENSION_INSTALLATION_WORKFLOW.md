# Правильный Workflow Установки Расширений в 1С

**Версия:** 1.0
**Дата:** 2025-11-12
**Статус:** Архитектурное решение
**Автор:** Architecture Team

---

## 📋 Содержание

1. [Executive Summary](#executive-summary)
2. [Анализ проблемы](#анализ-проблемы)
3. [RAS API Analysis](#ras-api-analysis)
4. [Архитектурные варианты](#архитектурные-варианты)
5. [Рекомендуемое решение](#рекомендуемое-решение)
6. [Детальный дизайн](#детальный-дизайн)
7. [Error Handling & Rollback](#error-handling--rollback)
8. [Implementation Plan](#implementation-plan)
9. [Risks & Mitigation](#risks--mitigation)

---

## Executive Summary

### Рекомендация: **Option B (Worker-Orchestrated Workflow)**

**Обоснование:**
- ✅ **Single Responsibility** - Worker управляет полным lifecycle операции установки расширения
- ✅ **Minimal Latency** - Прямые HTTP calls к cluster-service без промежуточных слоев
- ✅ **Clear Error Handling** - Весь rollback logic в одном месте
- ✅ **Testability** - Unit tests для каждого шага workflow
- ✅ **Production Ready** - Используем существующую инфраструктуру (cluster-service уже имеет нужные API)

**Архитектурная концепция:**
```
Worker executeExtensionInstall():
  1. Lock Scheduled Jobs (cluster-service API)
  2. Terminate All Sessions (cluster-service API)
  3. Poll until sessions=0 (max 30 sec)
  4. Install Extension (batch-service API)
  5. Unlock Scheduled Jobs (cluster-service API)
  6. Rollback на каждом failure шаге
```

**Performance estimates:**
- Sequential (1 база): ~1-2 минуты
- Parallel (100 баз): ~10-20 минут (с worker pool)

---

## Анализ проблемы

### Текущая реализация (НЕ работает)

**Файл:** `go-services/worker/internal/processor/extension_handler.go`

```go
func (p *TaskProcessor) executeExtensionInstall(...) {
    // Simplified workflow:
    // 1. Fetch credentials
    // 2. Call batch-service: LoadCfg + ForceTerminate + UpdateDBCfg
    // 3. Return result
}
```

**Файл:** `go-services/batch-service/internal/infrastructure/v8executor/extension_installer.go`

```go
func (i *ExtensionInstaller) InstallExtension(...) error {
    // 1. LoadCfg(extensionPath) → ✅ Успешно
    // 2. ForceTerminateSessions(all=true, message="Extension install") → ✅ Успешно
    // 3. UpdateDBCfg() → ❌ exit code 101 (база занята)
}
```

### Почему exit code 101?

**Exit code 101 = база занята (locked):**
- Регламентные задания **НЕ заблокированы** → продолжают запускаться
- Новые сеансы создаются **ПОСЛЕ** ForceTerminate
- UpdateDBCfg требует **эксклюзивную блокировку** БД → не может получить доступ

**Timing issue:**
```
T0: ForceTerminate → Убивает 3 активных сеанса ✅
T1: Регламентное задание автоматически стартует новый сеанс ❌
T2: UpdateDBCfg → exit 101 (база занята новым сеансом) ❌
```

### Production workflow (правильный)

**От пользователя (проверенный на реальных системах):**

```
1. Блокировка регламентных заданий (через RAS API)
2. Завершение ВСЕХ активных сеансов
3. LoadCfg (загрузка .cfe файла)
4. UpdateDBCfg (применение к БД) → теперь работает ✅
5. Разблокировка регламентных заданий
```

**Критично:** Регламентные задания должны быть заблокированы **ДО** ForceTerminate!

---

## RAS API Analysis

### Доступные proto-файлы

**Репозиторий:** `C:\1CProject\ras-grpc-gw\accessapis\`

```
infobase/service/management.proto - ✅ НАЙДЕН
access/service/client.proto
access/service/token.proto
```

### Infobase Management Service (gRPC)

**Proto definition:** `ras-grpc-gw/accessapis/infobase/service/management.proto`

```protobuf
service InfobaseManagementService {
  // LockInfobase блокирует доступ к информационной базе
  rpc LockInfobase(LockInfobaseRequest) returns (LockInfobaseResponse);

  // UnlockInfobase снимает блокировку с информационной базы
  rpc UnlockInfobase(UnlockInfobaseRequest) returns (UnlockInfobaseResponse);

  // UpdateInfobase изменяет параметры существующей информационной базы
  rpc UpdateInfobase(UpdateInfobaseRequest) returns (UpdateInfobaseResponse);
}

message LockInfobaseRequest {
  string cluster_id = 1;   // UUID кластера 1С
  string infobase_id = 2;  // UUID информационной базы

  bool sessions_deny = 3;                     // Запретить новые сеансы
  optional Timestamp denied_from = 4;         // Начало блокировки
  optional Timestamp denied_to = 5;           // Конец блокировки
  optional string denied_message = 6;         // Сообщение пользователям
  optional string permission_code = 7;        // Код для обхода блокировки

  bool scheduled_jobs_deny = 8;  // ✅ Блокировка регламентных заданий

  optional string cluster_user = 9;        // Администратор кластера
  optional string cluster_password = 10;   // Пароль администратора
}

message UnlockInfobaseRequest {
  string cluster_id = 1;
  string infobase_id = 2;

  bool unlock_sessions = 3;           // Разрешить новые сеансы
  bool unlock_scheduled_jobs = 4;     // ✅ Разрешить выполнение регламентных заданий

  optional string cluster_user = 5;
  optional string cluster_password = 6;
}
```

### Session Termination (через cluster-service)

**Текущий endpoint:** `POST /api/v1/sessions/terminate`

**Файл:** `go-services/cluster-service/internal/api/handlers/sessions.go` (MOCK implementation)

```go
// TerminateSessions terminates multiple sessions
// MOCK IMPLEMENTATION for P3.3 - simulates successful termination
func (h *SessionsHandler) TerminateSessions(c *gin.Context) {
    var req models.TerminateSessionsRequest
    // ... validation

    // MOCK: Simulate successful termination
    // In real implementation, this would call RAS gRPC service
}

type TerminateSessionsRequest struct {
    InfobaseID string   `json:"infobase_id"`
    SessionIDs []string `json:"session_ids"`  // Empty array = terminate ALL
}
```

**TODO (Phase 2):** Реализовать real termination через ras-grpc-gw

### Session Count (для polling)

**Текущий endpoint:** `GET /api/v1/sessions?infobase_id={id}`

**Файл:** `go-services/cluster-service/internal/api/handlers/sessions.go` (MOCK implementation)

```go
// GetSessions returns active sessions for a specific infobase
// MOCK IMPLEMENTATION for P3.3 - returns fake session data
func (h *SessionsHandler) GetSessions(c *gin.Context) {
    // Returns mock sessions:
    // - session-001 (1CV8C)
    // - session-002 (WebClient)
}
```

**TODO (Phase 2):** Реализовать real sessions через ras-grpc-gw

### Необходимые методы для cluster-service

**Что ЕСТЬ сейчас (через ras-grpc-gw proto):**

✅ `LockInfobase(cluster_id, infobase_id, scheduled_jobs_deny=true)` - через gRPC proto
✅ `UnlockInfobase(cluster_id, infobase_id, unlock_scheduled_jobs=true)` - через gRPC proto
🟡 `TerminateSessions(infobase_id, session_ids=[])` - MOCK, нужна real implementation
🟡 `GetSessions(infobase_id)` - MOCK, нужна real implementation

**Что НУЖНО добавить в cluster-service:**

1. **HTTP endpoint для блокировки регламентных заданий:**
   ```
   POST /api/v1/infobases/{infobase_id}/lock-scheduled-jobs
   Body: {
     "cluster_id": "uuid",
     "cluster_user": "admin",
     "cluster_password": "***"
   }
   ```

2. **HTTP endpoint для разблокировки:**
   ```
   POST /api/v1/infobases/{infobase_id}/unlock-scheduled-jobs
   Body: {
     "cluster_id": "uuid",
     "cluster_user": "admin",
     "cluster_password": "***"
   }
   ```

3. **Реализовать real termination и polling:**
   - Переделать `TerminateSessions()` из MOCK в real gRPC call
   - Переделать `GetSessions()` из MOCK в real gRPC call

**Complexity:** **MEDIUM** (2-4 часа)
- gRPC proto уже есть
- Нужны только HTTP handlers для new endpoints
- gRPC client уже подключен

---

## Архитектурные варианты

### Option A: Orchestrator-Managed Workflow (Saga Pattern)

```python
# orchestrator/apps/operations/workflows/extension_workflow.py

class ExtensionInstallationWorkflow:
    def execute(self, operation_id, database_ids, extension_config):
        """
        Saga pattern:
        1. Call cluster-service: LockScheduledJobs
        2. Call cluster-service: TerminateAllSessions
        3. Poll until sessions=0 (timeout 30 sec)
        4. Call batch-service: InstallExtension
        5. Call cluster-service: UnlockScheduledJobs
        6. Rollback на failure каждого шага
        """

        for database_id in database_ids:
            saga = ExtensionInstallSaga(database_id, extension_config)
            try:
                saga.step1_lock_jobs()
                saga.step2_terminate_sessions()
                saga.step3_wait_sessions_clear()
                saga.step4_install_extension()
                saga.step5_unlock_jobs()
            except Exception as e:
                saga.rollback()  # Unlock jobs if locked
                raise
```

#### Pros
- ✅ **Централизованный контроль** - Orchestrator видит весь workflow
- ✅ **Легко расширять** - Добавить новые шаги в Saga
- ✅ **Audit trail** - Все шаги логируются в Django DB
- ✅ **Retry на уровне Saga** - Можно повторить весь workflow
- ✅ **Transaction consistency** - Легко откатить на failure

#### Cons
- ❌ **High latency** - Orchestrator → Worker → cluster-service (2 network hops)
- ❌ **Increased complexity** - Saga state machine в Django
- ❌ **Network overhead** - Worker должен делать callbacks в Orchestrator
- ❌ **Tight coupling** - Worker зависит от Orchestrator API
- ❌ **Scaling bottleneck** - Orchestrator координирует каждый шаг для 700 баз

#### Timing estimate
- Single database: **~2-3 минуты** (network overhead)
- 700 databases parallel: **~15-30 минут** (координация через Orchestrator)

---

### Option B: Worker-Orchestrated Workflow (Self-Contained) ⭐ **RECOMMENDED**

```go
// worker/internal/processor/extension_workflow.go

func (p *TaskProcessor) executeExtensionInstallWithWorkflow(
    ctx context.Context,
    databaseID string,
    extensionConfig ExtensionConfig,
) error {
    workflow := NewExtensionInstallWorkflow(p.config, databaseID, extensionConfig)

    // Step 1: Lock scheduled jobs
    if err := workflow.LockScheduledJobs(ctx); err != nil {
        return fmt.Errorf("step 1 failed: %w", err)
    }
    defer workflow.UnlockScheduledJobs(ctx) // Rollback on panic

    // Step 2: Terminate all sessions
    if err := workflow.TerminateAllSessions(ctx); err != nil {
        return fmt.Errorf("step 2 failed: %w", err)
    }

    // Step 3: Wait until sessions=0
    if err := workflow.WaitSessionsClear(ctx, 30*time.Second); err != nil {
        return fmt.Errorf("step 3 failed: %w", err)
    }

    // Step 4: Install extension
    if err := workflow.InstallExtension(ctx); err != nil {
        return fmt.Errorf("step 4 failed: %w", err)
    }

    // Step 5: Unlock scheduled jobs (explicit unlock)
    if err := workflow.UnlockScheduledJobs(ctx); err != nil {
        log.Warnf("unlock failed (already deferred): %v", err)
    }

    return nil
}
```

#### Pros
- ✅ **Low latency** - Worker → cluster-service (1 network hop)
- ✅ **Self-contained** - Весь workflow в одном месте
- ✅ **Easy testing** - Unit tests для каждого шага
- ✅ **No Orchestrator dependency** - Worker автономен
- ✅ **Parallel execution** - 100-500 workers могут работать независимо
- ✅ **Simple rollback** - `defer workflow.UnlockScheduledJobs()`
- ✅ **Production ready** - Используем существующую инфраструктуру

#### Cons
- ⚠️ **Limited audit trail** - Нужно логировать в structured logs
- ⚠️ **No central coordination** - Orchestrator не видит промежуточные шаги
- ⚠️ **Retry complexity** - Нужно определить retry logic для каждого шага

#### Timing estimate
- Single database: **~1-2 минуты** (minimal overhead)
- 700 databases parallel: **~10-20 минут** (worker pool 100-500)

---

### Option C: Batch Service-Managed Workflow (Consolidated)

```go
// batch-service/internal/service/extension_installer_workflow.go

func (i *ExtensionInstaller) InstallWithWorkflow(
    ctx context.Context,
    req *InstallRequest,
) (*InstallResponse, error) {
    // Initialize cluster-service client
    clusterClient := cluster.NewClient(i.clusterServiceURL)

    // 1. Lock scheduled jobs
    clusterClient.LockScheduledJobs(req.ClusterID, req.InfobaseID)
    defer clusterClient.UnlockScheduledJobs(req.ClusterID, req.InfobaseID)

    // 2. Terminate sessions
    clusterClient.TerminateAllSessions(req.InfobaseID)

    // 3. Wait for sessions=0
    clusterClient.WaitSessionsClear(req.InfobaseID, 30*time.Second)

    // 4. Execute 1cv8.exe LoadCfg + UpdateDBCfg
    i.executor.InstallExtension(ctx, req)

    return &InstallResponse{Success: true}, nil
}
```

#### Pros
- ✅ **Consolidated logic** - Все в одном сервисе
- ✅ **Simple API** - Worker просто вызывает InstallWithWorkflow()
- ✅ **Atomic operation** - Весь workflow как единая операция

#### Cons
- ❌ **Tight coupling** - Batch Service зависит от cluster-service
- ❌ **Violates SRP** - Batch Service теперь знает про RAS workflow
- ❌ **Hard to test** - Смешивание subprocess (1cv8.exe) и HTTP calls
- ❌ **Not aligned with architecture** - Batch Service должен только управлять 1cv8.exe

#### Timing estimate
- Single database: **~1-2 минуты**
- 700 databases parallel: **~10-20 минут**

---

## Рекомендуемое решение

### **Option B: Worker-Orchestrated Workflow** ⭐

**Обоснование:**

1. **Architectural fit:**
   - Worker уже отвечает за выполнение операций
   - cluster-service уже предоставляет нужные API
   - batch-service остается focused на subprocess execution

2. **Performance:**
   - Минимальная latency (1 network hop)
   - Parallel execution на 100-500 workers
   - ~10-20 минут для 700 баз (production target)

3. **Maintainability:**
   - Self-contained workflow (легко читать и тестировать)
   - Simple rollback logic (defer pattern)
   - Clear separation of concerns

4. **Production readiness:**
   - Используем существующую инфраструктуру
   - Minimal changes required
   - Easy to monitor и debug

---

## Детальный дизайн

### Architecture Diagram

```
┌──────────────────────────────────────────────────────────────┐
│ Worker (Go)                                                  │
│                                                              │
│  executeExtensionInstall(ctx, databaseID, extensionConfig)   │
│                                                              │
│  ┌────────────────────────────────────────────────────────┐ │
│  │ ExtensionInstallWorkflow                               │ │
│  │                                                        │ │
│  │  1. LockScheduledJobs()                                │ │
│  │     └─► HTTP POST cluster-service:8088/lock-jobs      │ │
│  │                                                        │ │
│  │  2. TerminateAllSessions()                             │ │
│  │     └─► HTTP POST cluster-service:8088/sessions/...   │ │
│  │                                                        │ │
│  │  3. WaitSessionsClear(timeout=30s)                     │ │
│  │     └─► HTTP GET  cluster-service:8088/sessions       │ │
│  │         (polling every 1 sec)                          │ │
│  │                                                        │ │
│  │  4. InstallExtension()                                 │ │
│  │     └─► HTTP POST batch-service:8087/install          │ │
│  │         (LoadCfg + UpdateDBCfg)                        │ │
│  │                                                        │ │
│  │  5. UnlockScheduledJobs()                              │ │
│  │     └─► HTTP POST cluster-service:8088/unlock-jobs    │ │
│  │                                                        │ │
│  │  [defer UnlockScheduledJobs() для rollback]           │ │
│  └────────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────┘
           │                        │                      │
           ▼                        ▼                      ▼
   ┌───────────────┐     ┌──────────────────┐   ┌─────────────────┐
   │cluster-service│     │cluster-service   │   │batch-service    │
   │(RAS API)      │     │(RAS API)         │   │(1cv8.exe)       │
   │:8088          │     │:8088             │   │:8087            │
   └───────────────┘     └──────────────────┘   └─────────────────┘
           │                        │                      │
           ▼                        ▼                      ▼
   ┌───────────────────────────────────────────────────────────┐
   │ ras-grpc-gw → RAS → 1C Cluster → Infobase                │
   └───────────────────────────────────────────────────────────┘
```

### Code Structure

```
go-services/worker/internal/processor/
├── extension_handler.go          # Existing (entry point)
├── extension_workflow.go         # NEW - workflow orchestration
└── extension_workflow_test.go    # NEW - unit tests

go-services/cluster-service/internal/
├── api/handlers/
│   ├── infobase_lock.go          # NEW - Lock/Unlock scheduled jobs
│   └── sessions.go               # MODIFY - Real termination (remove MOCK)
└── service/
    └── infobase_management.go    # NEW - gRPC client wrapper
```

### Implementation Details

#### 1. ExtensionInstallWorkflow (worker)

**Файл:** `go-services/worker/internal/processor/extension_workflow.go`

```go
package processor

import (
    "context"
    "fmt"
    "time"
    "net/http"
    "encoding/json"

    "github.com/commandcenter1c/commandcenter/shared/logger"
    "github.com/commandcenter1c/commandcenter/shared/config"
)

// ExtensionInstallWorkflow orchestrates safe extension installation
type ExtensionInstallWorkflow struct {
    config          *config.Config
    databaseID      string
    extensionConfig ExtensionConfig

    // Cluster/Infobase metadata
    clusterID       string
    infobaseID      string

    // Flags for rollback
    jobsLocked      bool
}

// ExtensionConfig holds extension installation parameters
type ExtensionConfig struct {
    ExtensionName string
    ExtensionPath string
    Server        string
    InfobaseName  string
    Username      string
    Password      string
}

func NewExtensionInstallWorkflow(
    cfg *config.Config,
    databaseID string,
    extensionConfig ExtensionConfig,
) *ExtensionInstallWorkflow {
    return &ExtensionInstallWorkflow{
        config:          cfg,
        databaseID:      databaseID,
        extensionConfig: extensionConfig,
        jobsLocked:      false,
    }
}

// Execute runs the full workflow with rollback on error
func (w *ExtensionInstallWorkflow) Execute(ctx context.Context) error {
    log := logger.GetLogger()
    log.Infof("starting extension install workflow for database %s", w.databaseID)

    // Setup rollback (unlock jobs on panic or error)
    defer func() {
        if w.jobsLocked {
            if err := w.UnlockScheduledJobs(context.Background()); err != nil {
                log.Errorf("rollback failed to unlock jobs: %v", err)
            }
        }
    }()

    // Step 1: Fetch cluster/infobase metadata
    if err := w.fetchMetadata(ctx); err != nil {
        return fmt.Errorf("step 0 (metadata): %w", err)
    }

    // Step 1: Lock scheduled jobs
    if err := w.LockScheduledJobs(ctx); err != nil {
        return fmt.Errorf("step 1 (lock jobs): %w", err)
    }

    // Step 2: Terminate all sessions
    if err := w.TerminateAllSessions(ctx); err != nil {
        return fmt.Errorf("step 2 (terminate sessions): %w", err)
    }

    // Step 3: Wait until sessions=0
    if err := w.WaitSessionsClear(ctx, 30*time.Second); err != nil {
        return fmt.Errorf("step 3 (wait sessions clear): %w", err)
    }

    // Step 4: Install extension (LoadCfg + UpdateDBCfg)
    if err := w.InstallExtension(ctx); err != nil {
        return fmt.Errorf("step 4 (install extension): %w", err)
    }

    // Step 5: Unlock scheduled jobs (explicit)
    if err := w.UnlockScheduledJobs(ctx); err != nil {
        // Log warning but don't fail (already deferred)
        log.Warnf("explicit unlock failed: %v", err)
    }

    log.Infof("extension install workflow completed successfully for database %s", w.databaseID)
    return nil
}

// fetchMetadata retrieves cluster_id and infobase_id from Orchestrator
func (w *ExtensionInstallWorkflow) fetchMetadata(ctx context.Context) error {
    // TODO: Call Orchestrator API to get cluster_id and infobase_id
    // GET /api/v1/databases/{database_id}/cluster-metadata
    // Response: { "cluster_id": "uuid", "infobase_id": "uuid" }

    // MOCK for now:
    w.clusterID = "mock-cluster-id"
    w.infobaseID = "mock-infobase-id"
    return nil
}

// LockScheduledJobs блокирует регламентные задания через cluster-service
func (w *ExtensionInstallWorkflow) LockScheduledJobs(ctx context.Context) error {
    log := logger.GetLogger()
    log.Infof("locking scheduled jobs for infobase %s", w.infobaseID)

    url := fmt.Sprintf("%s/api/v1/infobases/%s/lock-scheduled-jobs",
        w.config.ClusterServiceURL, w.infobaseID)

    reqBody := map[string]interface{}{
        "cluster_id": w.clusterID,
        // TODO: Add cluster credentials if needed
    }

    if err := w.httpPostJSON(ctx, url, reqBody, nil); err != nil {
        return fmt.Errorf("failed to lock scheduled jobs: %w", err)
    }

    w.jobsLocked = true
    log.Infof("scheduled jobs locked successfully")
    return nil
}

// UnlockScheduledJobs разблокирует регламентные задания
func (w *ExtensionInstallWorkflow) UnlockScheduledJobs(ctx context.Context) error {
    if !w.jobsLocked {
        return nil // Nothing to unlock
    }

    log := logger.GetLogger()
    log.Infof("unlocking scheduled jobs for infobase %s", w.infobaseID)

    url := fmt.Sprintf("%s/api/v1/infobases/%s/unlock-scheduled-jobs",
        w.config.ClusterServiceURL, w.infobaseID)

    reqBody := map[string]interface{}{
        "cluster_id": w.clusterID,
    }

    if err := w.httpPostJSON(ctx, url, reqBody, nil); err != nil {
        return fmt.Errorf("failed to unlock scheduled jobs: %w", err)
    }

    w.jobsLocked = false
    log.Infof("scheduled jobs unlocked successfully")
    return nil
}

// TerminateAllSessions завершает все активные сеансы
func (w *ExtensionInstallWorkflow) TerminateAllSessions(ctx context.Context) error {
    log := logger.GetLogger()
    log.Infof("terminating all sessions for infobase %s", w.infobaseID)

    url := fmt.Sprintf("%s/api/v1/sessions/terminate", w.config.ClusterServiceURL)

    reqBody := map[string]interface{}{
        "infobase_id": w.infobaseID,
        "session_ids": []string{}, // Empty = terminate ALL
    }

    var resp struct {
        TerminatedCount int      `json:"terminated_count"`
        FailedSessions  []string `json:"failed_sessions"`
    }

    if err := w.httpPostJSON(ctx, url, reqBody, &resp); err != nil {
        return fmt.Errorf("failed to terminate sessions: %w", err)
    }

    log.Infof("terminated %d sessions", resp.TerminatedCount)

    if len(resp.FailedSessions) > 0 {
        log.Warnf("failed to terminate %d sessions: %v",
            len(resp.FailedSessions), resp.FailedSessions)
    }

    return nil
}

// WaitSessionsClear ждет пока все сеансы завершатся (polling)
func (w *ExtensionInstallWorkflow) WaitSessionsClear(ctx context.Context, timeout time.Duration) error {
    log := logger.GetLogger()
    log.Infof("waiting for sessions to clear (timeout=%v)", timeout)

    deadline := time.Now().Add(timeout)
    ticker := time.NewTicker(1 * time.Second)
    defer ticker.Stop()

    for {
        select {
        case <-ctx.Done():
            return ctx.Err()
        case <-ticker.C:
            count, err := w.getSessionsCount(ctx)
            if err != nil {
                log.Warnf("failed to get sessions count: %v", err)
                continue
            }

            if count == 0 {
                log.Infof("all sessions cleared")
                return nil
            }

            log.Infof("waiting for %d sessions to clear...", count)

            if time.Now().After(deadline) {
                return fmt.Errorf("timeout waiting for sessions to clear (still %d active)", count)
            }
        }
    }
}

// getSessionsCount возвращает количество активных сеансов
func (w *ExtensionInstallWorkflow) getSessionsCount(ctx context.Context) (int, error) {
    url := fmt.Sprintf("%s/api/v1/sessions?infobase_id=%s",
        w.config.ClusterServiceURL, w.infobaseID)

    var resp struct {
        Sessions []map[string]interface{} `json:"sessions"`
        Count    int                      `json:"count"`
    }

    if err := w.httpGetJSON(ctx, url, &resp); err != nil {
        return 0, err
    }

    return resp.Count, nil
}

// InstallExtension вызывает batch-service для установки расширения
func (w *ExtensionInstallWorkflow) InstallExtension(ctx context.Context) error {
    log := logger.GetLogger()
    log.Infof("installing extension %s", w.extensionConfig.ExtensionName)

    url := fmt.Sprintf("%s/api/v1/extensions/install", w.config.BatchServiceURL)

    reqBody := map[string]interface{}{
        "server":                   w.extensionConfig.Server,
        "infobase_name":            w.extensionConfig.InfobaseName,
        "username":                 w.extensionConfig.Username,
        "password":                 w.extensionConfig.Password,
        "extension_path":           w.extensionConfig.ExtensionPath,
        "extension_name":           w.extensionConfig.ExtensionName,
        "update_db_config":         true,  // NOW safe to update
        "force_terminate_sessions": false, // Already terminated
    }

    var resp struct {
        Success bool   `json:"success"`
        Message string `json:"message"`
        Error   string `json:"error,omitempty"`
    }

    if err := w.httpPostJSON(ctx, url, reqBody, &resp); err != nil {
        return fmt.Errorf("batch service call failed: %w", err)
    }

    if !resp.Success {
        return fmt.Errorf("extension installation failed: %s", resp.Error)
    }

    log.Infof("extension installed successfully: %s", resp.Message)
    return nil
}

// httpPostJSON helper for POST requests
func (w *ExtensionInstallWorkflow) httpPostJSON(ctx context.Context, url string, reqBody interface{}, respBody interface{}) error {
    // Implementation similar to existing code in extension_handler.go
    // ...
    return nil
}

// httpGetJSON helper for GET requests
func (w *ExtensionInstallWorkflow) httpGetJSON(ctx context.Context, url string, respBody interface{}) error {
    // Implementation...
    return nil
}
```

#### 2. Modify extension_handler.go to use Workflow

**Файл:** `go-services/worker/internal/processor/extension_handler.go`

```go
// executeExtensionInstall handles extension installation via Workflow
func (p *TaskProcessor) executeExtensionInstall(ctx context.Context, msg *models.OperationMessage, databaseID string) models.DatabaseResultV2 {
    log := logger.GetLogger()
    start := time.Now()

    result := models.DatabaseResultV2{
        DatabaseID: databaseID,
    }

    // Extract extension data from payload
    extensionName, _ := msg.Payload.Data["extension_name"].(string)
    extensionPath, _ := msg.Payload.Data["extension_path"].(string)

    // Fetch credentials
    creds, err := p.credsClient.Fetch(ctx, databaseID)
    if err != nil {
        result.Success = false
        result.Error = fmt.Sprintf("failed to fetch credentials: %v", err)
        result.ErrorCode = "CREDENTIALS_ERROR"
        result.Duration = time.Since(start).Seconds()
        return result
    }

    // Build extension config
    extensionConfig := ExtensionConfig{
        ExtensionName: extensionName,
        ExtensionPath: extensionPath,
        Server:        creds.ServerAddress,
        InfobaseName:  creds.InfobaseName,
        Username:      creds.Username,
        Password:      creds.Password,
    }

    // Execute workflow
    workflow := NewExtensionInstallWorkflow(p.config, databaseID, extensionConfig)
    if err := workflow.Execute(ctx); err != nil {
        result.Success = false
        result.Error = fmt.Sprintf("workflow failed: %v", err)
        result.ErrorCode = "WORKFLOW_ERROR"
        result.Duration = time.Since(start).Seconds()
        return result
    }

    // Success
    result.Success = true
    result.Data = map[string]interface{}{
        "extension_name": extensionName,
        "message":        "Extension installed successfully",
    }
    result.Duration = time.Since(start).Seconds()

    return result
}
```

#### 3. Add cluster-service endpoints

**Файл:** `go-services/cluster-service/internal/api/handlers/infobase_lock.go` (NEW)

```go
package handlers

import (
    "net/http"

    "github.com/gin-gonic/gin"
    "go.uber.org/zap"

    "github.com/command-center-1c/cluster-service/internal/service"
)

type InfobaseLockHandler struct {
    logger              *zap.Logger
    infobaseManagement  *service.InfobaseManagementService
}

func NewInfobaseLockHandler(logger *zap.Logger, mgmtService *service.InfobaseManagementService) *InfobaseLockHandler {
    return &InfobaseLockHandler{
        logger:             logger,
        infobaseManagement: mgmtService,
    }
}

// LockScheduledJobs блокирует регламентные задания
// POST /api/v1/infobases/:infobase_id/lock-scheduled-jobs
func (h *InfobaseLockHandler) LockScheduledJobs(c *gin.Context) {
    infobaseID := c.Param("infobase_id")

    var req struct {
        ClusterID       string `json:"cluster_id" binding:"required"`
        ClusterUser     string `json:"cluster_user"`
        ClusterPassword string `json:"cluster_password"`
    }

    if err := c.ShouldBindJSON(&req); err != nil {
        c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
        return
    }

    h.logger.Info("locking scheduled jobs",
        zap.String("infobase_id", infobaseID),
        zap.String("cluster_id", req.ClusterID))

    // Call gRPC service
    err := h.infobaseManagement.LockScheduledJobs(c.Request.Context(), service.LockScheduledJobsRequest{
        ClusterID:       req.ClusterID,
        InfobaseID:      infobaseID,
        ClusterUser:     req.ClusterUser,
        ClusterPassword: req.ClusterPassword,
    })

    if err != nil {
        h.logger.Error("failed to lock scheduled jobs", zap.Error(err))
        c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
        return
    }

    c.JSON(http.StatusOK, gin.H{
        "success": true,
        "message": "Scheduled jobs locked successfully",
    })
}

// UnlockScheduledJobs разблокирует регламентные задания
// POST /api/v1/infobases/:infobase_id/unlock-scheduled-jobs
func (h *InfobaseLockHandler) UnlockScheduledJobs(c *gin.Context) {
    infobaseID := c.Param("infobase_id")

    var req struct {
        ClusterID       string `json:"cluster_id" binding:"required"`
        ClusterUser     string `json:"cluster_user"`
        ClusterPassword string `json:"cluster_password"`
    }

    if err := c.ShouldBindJSON(&req); err != nil {
        c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
        return
    }

    h.logger.Info("unlocking scheduled jobs",
        zap.String("infobase_id", infobaseID),
        zap.String("cluster_id", req.ClusterID))

    // Call gRPC service
    err := h.infobaseManagement.UnlockScheduledJobs(c.Request.Context(), service.UnlockScheduledJobsRequest{
        ClusterID:       req.ClusterID,
        InfobaseID:      infobaseID,
        ClusterUser:     req.ClusterUser,
        ClusterPassword: req.ClusterPassword,
    })

    if err != nil {
        h.logger.Error("failed to unlock scheduled jobs", zap.Error(err))
        c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
        return
    }

    c.JSON(http.StatusOK, gin.H{
        "success": true,
        "message": "Scheduled jobs unlocked successfully",
    })
}
```

**Файл:** `go-services/cluster-service/internal/service/infobase_management.go` (NEW)

```go
package service

import (
    "context"
    "fmt"

    "go.uber.org/zap"
    "google.golang.org/grpc"

    pb "github.com/v8platform/ras-grpc-gw/pkg/gen/infobase/service"
)

type InfobaseManagementService struct {
    logger     *zap.Logger
    grpcClient pb.InfobaseManagementServiceClient
}

func NewInfobaseManagementService(logger *zap.Logger, grpcConn *grpc.ClientConn) *InfobaseManagementService {
    return &InfobaseManagementService{
        logger:     logger,
        grpcClient: pb.NewInfobaseManagementServiceClient(grpcConn),
    }
}

type LockScheduledJobsRequest struct {
    ClusterID       string
    InfobaseID      string
    ClusterUser     string
    ClusterPassword string
}

func (s *InfobaseManagementService) LockScheduledJobs(ctx context.Context, req LockScheduledJobsRequest) error {
    s.logger.Info("locking scheduled jobs via gRPC",
        zap.String("cluster_id", req.ClusterID),
        zap.String("infobase_id", req.InfobaseID))

    // Build gRPC request
    grpcReq := &pb.LockInfobaseRequest{
        ClusterId:          req.ClusterID,
        InfobaseId:         req.InfobaseID,
        SessionsDeny:       false,               // Don't block user sessions
        ScheduledJobsDeny:  true,                // Block scheduled jobs
        ClusterUser:        &req.ClusterUser,
        ClusterPassword:    &req.ClusterPassword,
    }

    // Call gRPC
    resp, err := s.grpcClient.LockInfobase(ctx, grpcReq)
    if err != nil {
        return fmt.Errorf("gRPC call failed: %w", err)
    }

    if !resp.Success {
        return fmt.Errorf("lock failed: %s", resp.Message)
    }

    s.logger.Info("scheduled jobs locked successfully",
        zap.String("infobase_id", req.InfobaseID))

    return nil
}

type UnlockScheduledJobsRequest struct {
    ClusterID       string
    InfobaseID      string
    ClusterUser     string
    ClusterPassword string
}

func (s *InfobaseManagementService) UnlockScheduledJobs(ctx context.Context, req UnlockScheduledJobsRequest) error {
    s.logger.Info("unlocking scheduled jobs via gRPC",
        zap.String("cluster_id", req.ClusterID),
        zap.String("infobase_id", req.InfobaseID))

    // Build gRPC request
    grpcReq := &pb.UnlockInfobaseRequest{
        ClusterId:           req.ClusterID,
        InfobaseId:          req.InfobaseID,
        UnlockSessions:      false,  // Don't change user sessions
        UnlockScheduledJobs: true,   // Unlock scheduled jobs
        ClusterUser:         &req.ClusterUser,
        ClusterPassword:     &req.ClusterPassword,
    }

    // Call gRPC
    resp, err := s.grpcClient.UnlockInfobase(ctx, grpcReq)
    if err != nil {
        return fmt.Errorf("gRPC call failed: %w", err)
    }

    if !resp.Success {
        return fmt.Errorf("unlock failed: %s", resp.Message)
    }

    s.logger.Info("scheduled jobs unlocked successfully",
        zap.String("infobase_id", req.InfobaseID))

    return nil
}
```

#### 4. Update router (cluster-service)

**Файл:** `go-services/cluster-service/internal/api/router.go`

```go
// Add new routes
infobaseLockHandler := handlers.NewInfobaseLockHandler(logger, infobaseManagementService)

v1.POST("/infobases/:infobase_id/lock-scheduled-jobs", infobaseLockHandler.LockScheduledJobs)
v1.POST("/infobases/:infobase_id/unlock-scheduled-jobs", infobaseLockHandler.UnlockScheduledJobs)
```

---

## Error Handling & Rollback

### Failure Scenarios

#### Scenario 1: LockScheduledJobs failed

**Причина:**
- gRPC connection timeout
- Invalid credentials
- RAS server unavailable

**Rollback:**
- ❌ Не требуется (блокировка не была установлена)

**Retry:**
- ✅ Retry 3 раза с exponential backoff (100ms, 200ms, 400ms)

**User notification:**
- Error: "Failed to lock scheduled jobs: {reason}"

---

#### Scenario 2: TerminateAllSessions failed

**Причина:**
- Some sessions refuse to terminate (stuck transactions)
- gRPC connection error

**Rollback:**
- ✅ UnlockScheduledJobs (deferred)

**Retry:**
- ✅ Retry 2 раза
- ⚠️ Log warning if some sessions can't be terminated, but continue

**User notification:**
- Warning: "Failed to terminate {N} sessions, continuing..."

---

#### Scenario 3: Timeout waiting for sessions=0

**Причина:**
- Регламентные задания продолжают создавать новые сеансы (если lock не сработал)
- Долгие транзакции

**Rollback:**
- ✅ UnlockScheduledJobs (deferred)

**Retry:**
- ❌ Не retry (timeout - финальная ошибка)

**User notification:**
- Error: "Timeout waiting for sessions to clear (still {N} active)"

---

#### Scenario 4: LoadCfg failed (batch-service)

**Причина:**
- Invalid .cfe file
- File not found
- Disk space

**Rollback:**
- ✅ UnlockScheduledJobs (deferred)

**Retry:**
- ❌ Не retry (corrupted file or missing file)

**User notification:**
- Error: "Failed to load extension: {reason}"

---

#### Scenario 5: UpdateDBCfg failed (exit code 101)

**Причина:**
- База занята (не должно случиться если workflow правильный)
- Недостаточно прав
- База в режиме конфигуратора

**Rollback:**
- ✅ UnlockScheduledJobs (deferred)
- ⚠️ Extension уже загружен (LoadCfg), но не применен

**Retry:**
- ✅ Retry 1 раз (может быть race condition)

**User notification:**
- Error: "Failed to update database configuration: {reason}"

---

#### Scenario 6: UnlockScheduledJobs failed (rollback)

**Причина:**
- gRPC connection error
- RAS server unavailable

**Rollback:**
- ⚠️ Manual intervention required

**Retry:**
- ✅ Retry 3 раза
- 🚨 Alert administrators if final retry fails

**User notification:**
- Critical Error: "Failed to unlock scheduled jobs after installation. Manual unlock required!"

---

### Rollback Strategy

```go
defer func() {
    if w.jobsLocked {
        // Attempt unlock with separate context (не зависит от parent ctx)
        unlockCtx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
        defer cancel()

        if err := w.UnlockScheduledJobs(unlockCtx); err != nil {
            log.Errorf("CRITICAL: failed to unlock scheduled jobs: %v", err)
            // Send alert to monitoring system
            // TODO: Integrate with Prometheus AlertManager
        }
    }
}()
```

**Importance:**
- Используй `context.Background()` для rollback (не зависит от cancelled parent context)
- Timeout для unlock = 10 секунд (достаточно для gRPC call)
- Alert administrators если unlock failed (manual intervention required)

---

## Implementation Plan

### Phase 1: cluster-service enhancements (2-4 часа)

**Tasks:**

1. **Генерация gRPC stubs** (если еще не сделано)
   ```bash
   cd ras-grpc-gw
   make generate  # Generate Go code from proto
   ```

2. **Добавить InfobaseManagementService** (1 час)
   - File: `go-services/cluster-service/internal/service/infobase_management.go`
   - Methods: `LockScheduledJobs()`, `UnlockScheduledJobs()`
   - gRPC client wrapper

3. **Добавить HTTP handlers** (1 час)
   - File: `go-services/cluster-service/internal/api/handlers/infobase_lock.go`
   - Endpoints:
     - `POST /api/v1/infobases/:id/lock-scheduled-jobs`
     - `POST /api/v1/infobases/:id/unlock-scheduled-jobs`

4. **Update router** (15 мин)
   - File: `go-services/cluster-service/internal/api/router.go`

5. **Unit tests** (1 час)
   - File: `go-services/cluster-service/internal/service/infobase_management_test.go`
   - Mock gRPC responses

---

### Phase 2: Worker workflow implementation (4-6 часов)

**Tasks:**

1. **Create ExtensionInstallWorkflow** (2 часа)
   - File: `go-services/worker/internal/processor/extension_workflow.go`
   - Implement 5-step workflow
   - Rollback logic (defer unlock)

2. **HTTP helpers** (1 час)
   - `httpPostJSON()`, `httpGetJSON()`
   - Retry logic with exponential backoff

3. **Modify extension_handler.go** (1 час)
   - Integrate workflow into `executeExtensionInstall()`

4. **Unit tests** (2 часа)
   - File: `go-services/worker/internal/processor/extension_workflow_test.go`
   - Mock HTTP responses from cluster-service and batch-service
   - Test rollback scenarios

---

### Phase 3: Integration testing (2-3 часа)

**Tasks:**

1. **End-to-end test** (1 час)
   - Setup test environment (local 1C server)
   - Create test infobase
   - Install test extension

2. **Error scenarios testing** (1 час)
   - Test timeout waiting for sessions
   - Test failed UpdateDBCfg
   - Test rollback (unlock jobs)

3. **Load testing** (1 час)
   - Test parallel installation on 10 bases
   - Measure timing and success rate

---

### Phase 4: Django integration (2 часа)

**Tasks:**

1. **Add cluster metadata endpoint** (1 час)
   - File: `orchestrator/apps/databases/views.py`
   - Endpoint: `GET /api/v1/databases/:id/cluster-metadata`
   - Returns: `{ "cluster_id": "uuid", "infobase_id": "uuid" }`

2. **Update Database model** (30 мин)
   - Add fields: `cluster_id`, `infobase_id` (nullable, for Phase 2 sync)

3. **Documentation** (30 мин)
   - Update API docs
   - Add workflow diagram

---

### Total Estimate: **10-15 часов** (1.5-2 дня)

---

## Risks & Mitigation

### Risk 1: ras-grpc-gw не поддерживает LockInfobase

**Likelihood:** LOW
**Impact:** HIGH

**Mitigation:**
- ✅ Proto definition уже существует (`management.proto`)
- ✅ Проверено: `LockInfobase()` и `UnlockInfobase()` уже определены
- ⚠️ Нужно проверить что реализация в ras-grpc-gw работает

**Fallback:**
- Использовать `UpdateInfobase()` с параметром `scheduled_jobs_deny=true`

---

### Risk 2: Новые сеансы создаются между Terminate и UpdateDBCfg

**Likelihood:** MEDIUM
**Impact:** MEDIUM

**Mitigation:**
- ✅ LockScheduledJobs предотвращает автоматические сеансы
- ✅ Polling `WaitSessionsClear()` гарантирует sessions=0
- ⚠️ Пользователи могут подключиться вручную (если sessions_deny=false)

**Solution:**
- Добавить `sessions_deny=true` в `LockInfobase()` (блокировка ВСЕХ сеансов)
- Permission code для администраторов

---

### Risk 3: UnlockScheduledJobs failed (manual intervention)

**Likelihood:** LOW
**Impact:** CRITICAL

**Mitigation:**
- ✅ Retry 3 раза с timeout
- ✅ Alert administrators через Prometheus AlertManager
- ✅ Документация для manual unlock через 1C консоль администрирования

**Manual unlock procedure:**
1. Открыть консоль администрирования 1С
2. Подключиться к кластеру
3. Найти информационную базу
4. Properties → Scheduled Jobs → Unblock

---

### Risk 4: Timeout ожидания sessions=0 (30 секунд)

**Likelihood:** MEDIUM
**Impact:** MEDIUM

**Mitigation:**
- ✅ Configurable timeout (env variable)
- ✅ Exponential backoff polling (1s → 2s → 4s)
- ⚠️ Некоторые регламентные задания могут выполняться >30 сек

**Solution:**
- Увеличить timeout до 60 секунд для production
- Добавить force terminate для stuck sessions (SIGKILL)

---

### Risk 5: Параллельные установки на одну базу (race condition)

**Likelihood:** LOW
**Impact:** HIGH

**Mitigation:**
- ✅ Django Operation model имеет unique constraint на (database_id, status=processing)
- ✅ Redis lock на database_id при старте операции

**Implementation:**
```python
# orchestrator/apps/operations/services.py
def create_extension_install_operation(database_id, ...):
    # Check for existing operation
    if Operation.objects.filter(
        database_id=database_id,
        status__in=['pending', 'processing']
    ).exists():
        raise ValidationError("Operation already in progress for this database")

    # Create operation
    ...
```

---

## Appendix A: API Reference

### cluster-service new endpoints

#### Lock Scheduled Jobs

```http
POST /api/v1/infobases/{infobase_id}/lock-scheduled-jobs
Content-Type: application/json

{
  "cluster_id": "uuid",
  "cluster_user": "admin",
  "cluster_password": "password"
}

Response 200 OK:
{
  "success": true,
  "message": "Scheduled jobs locked successfully"
}

Response 500 Internal Server Error:
{
  "error": "gRPC call failed: connection refused"
}
```

#### Unlock Scheduled Jobs

```http
POST /api/v1/infobases/{infobase_id}/unlock-scheduled-jobs
Content-Type: application/json

{
  "cluster_id": "uuid",
  "cluster_user": "admin",
  "cluster_password": "password"
}

Response 200 OK:
{
  "success": true,
  "message": "Scheduled jobs unlocked successfully"
}
```

---

### Orchestrator new endpoint

#### Get Cluster Metadata

```http
GET /api/v1/databases/{database_id}/cluster-metadata

Response 200 OK:
{
  "cluster_id": "550e8400-e29b-41d4-a716-446655440000",
  "infobase_id": "660e8400-e29b-41d4-a716-446655440001",
  "cluster_server": "localhost:1545",
  "cluster_user": "admin"
}
```

---

## Appendix B: Timing Breakdown

### Single Database Installation

| Step | Operation | Time (sec) | Notes |
|------|-----------|------------|-------|
| 0 | Fetch metadata | 0.1-0.3 | HTTP call to Orchestrator |
| 1 | Lock scheduled jobs | 0.1-0.5 | gRPC call via cluster-service |
| 2 | Terminate sessions | 0.5-2.0 | Depends on # of sessions |
| 3 | Wait sessions=0 | 0-30 | Polling (usually <10s) |
| 4 | LoadCfg | 5-10 | 1cv8.exe subprocess |
| 5 | UpdateDBCfg | 10-30 | 1cv8.exe subprocess |
| 6 | Unlock scheduled jobs | 0.1-0.5 | gRPC call |

**Total:** **16-73 seconds** (average: ~60 seconds)

---

### Parallel Execution (700 databases)

**Assumptions:**
- Worker pool size: 100
- Average time per database: 60 seconds
- No failures

**Sequential:** 700 × 60s = **42,000 seconds** (11.7 hours) ❌

**Parallel (100 workers):** 700 / 100 × 60s = **420 seconds** (~7 minutes) ✅

**With 20% failures + retries:** ~**10-15 minutes** ✅

---

## Appendix C: Monitoring & Alerts

### Prometheus Metrics

```go
// worker/internal/processor/extension_workflow.go

var (
    extensionInstallDuration = prometheus.NewHistogramVec(
        prometheus.HistogramOpts{
            Name: "extension_install_duration_seconds",
            Help: "Duration of extension installation workflow",
            Buckets: []float64{10, 30, 60, 120, 300},
        },
        []string{"step", "status"},
    )

    extensionInstallErrors = prometheus.NewCounterVec(
        prometheus.CounterOpts{
            Name: "extension_install_errors_total",
            Help: "Total number of extension installation errors",
        },
        []string{"step", "error_type"},
    )

    scheduledJobsLockFailures = prometheus.NewCounter(
        prometheus.CounterOpts{
            Name: "scheduled_jobs_unlock_failures_total",
            Help: "Total number of failed unlock operations (CRITICAL)",
        },
    )
)
```

### Grafana Alerts

```yaml
# Alert: Scheduled jobs unlock failures
- alert: ScheduledJobsUnlockFailed
  expr: increase(scheduled_jobs_unlock_failures_total[5m]) > 0
  for: 1m
  labels:
    severity: critical
  annotations:
    summary: "Failed to unlock scheduled jobs"
    description: "{{ $value }} databases have failed unlock operations. Manual intervention required!"

# Alert: High extension install failure rate
- alert: HighExtensionInstallFailureRate
  expr: rate(extension_install_errors_total[5m]) > 0.1
  for: 5m
  labels:
    severity: warning
  annotations:
    summary: "High extension installation failure rate"
    description: "More than 10% of extension installations are failing"
```

---

## Заключение

**Рекомендуемое решение:** **Option B (Worker-Orchestrated Workflow)**

Это решение:
- ✅ Минимизирует latency и network overhead
- ✅ Использует существующую инфраструктуру (cluster-service, batch-service)
- ✅ Обеспечивает четкий rollback logic
- ✅ Production-ready для масштабирования на 700 баз
- ✅ Testable и maintainable

**Estimated implementation time:** 10-15 часов (1.5-2 дня)

**Next steps:**
1. Утвердить архитектурное решение с пользователем
2. Начать реализацию с Phase 1 (cluster-service enhancements)
3. Протестировать на dev окружении с 1-2 базами
4. Развернуть на production после успешного тестирования

---

**Версия:** 1.0
**Дата:** 2025-11-12
**Статус:** Ready for Implementation
**Автор:** Architecture Team

**См. также:**
- `docs/1C_ADMINISTRATION_GUIDE.md` - RAS/RAC управление
- `docs/DJANGO_CLUSTER_INTEGRATION.md` - cluster-service интеграция
- `go-services/cluster-service/README.md` - cluster-service документация
- `go-services/batch-service/README.md` - batch-service документация
