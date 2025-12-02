# API Routes Analysis: AS-IS vs TO-BE

**Дата анализа:** 2025-11-27
**Последнее обновление:** 2025-11-28
**Статус:** ✅ ВСЕ ФАЗЫ ЗАВЕРШЕНЫ

---

## 1. ОБЩАЯ АРХИТЕКТУРА

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────────┐
│    Frontend     │────►│   API Gateway    │────►│  Backend Services   │
│   React:5173    │     │    Go:8080       │     │                     │
│                 │     │                  │     │  ┌───────────────┐  │
│  /api/v2/*      │     │  JWT Auth        │     │  │ Orchestrator  │  │
│                 │     │  Rate Limit      │     │  │ Django:8000   │  │
│                 │     │  Proxy Routes    │     │  └───────────────┘  │
│                 │     │                  │     │                     │
│                 │     │                  │     │  ┌───────────────┐  │
│                 │     │                  │     │  │ RAS Adapter   │  │
│                 │     │                  │     │  │ Go:8088       │  │
│                 │     │                  │     │  └───────────────┘  │
└─────────────────┘     └──────────────────┘     └─────────────────────┘
```

---

## 2. СВОДНАЯ ТАБЛИЦА МАРШРУТОВ

### 2.1 Clusters Endpoints

| Frontend вызывает | API Gateway route | Backend | Статус |
|-------------------|-------------------|---------|--------|
| `GET /clusters/list-clusters` | `/api/v2/clusters/*` → Orchestrator | Django `/api/v2/clusters/list-clusters/` | ✅ OK |
| `GET /clusters/get-cluster?cluster_id=` | `/api/v2/clusters/*` → Orchestrator | Django `/api/v2/clusters/get-cluster/` | ✅ OK |
| `POST /clusters/create-cluster` | `/api/v2/clusters/*` → Orchestrator | Django `/api/v2/clusters/create-cluster/` | ✅ OK (Phase 2) |
| `PUT /clusters/update-cluster` | `/api/v2/clusters/*` → Orchestrator | Django `/api/v2/clusters/update-cluster/` | ✅ OK (Phase 2) |
| `DELETE /clusters/delete-cluster` | `/api/v2/clusters/*` → Orchestrator | Django `/api/v2/clusters/delete-cluster/` | ✅ OK (Phase 2) |
| `POST /clusters/sync-cluster` | `/api/v2/clusters/*` → Orchestrator | Django `/api/v2/clusters/sync-cluster/` | ✅ OK |
| `GET /clusters/get-cluster-databases` | `/api/v2/clusters/*` → Orchestrator | Django `/api/v2/clusters/get-cluster-databases/` | ✅ OK (Phase 2) |

### 2.2 Databases Endpoints

| Frontend вызывает | API Gateway route | Backend | Статус |
|-------------------|-------------------|---------|--------|
| `GET /databases/list-databases` | `/api/v2/databases/*` → Orchestrator | Django `/api/v2/databases/list-databases/` | ✅ OK |
| `GET /databases/get-database?database_id=` | `/api/v2/databases/*` → Orchestrator | Django `/api/v2/databases/get-database/` | ✅ OK |
| `POST /databases/create-database` | `/api/v2/databases/*` → Orchestrator | **НЕТ ENDPOINT** | ❌ MISSING |
| `POST /databases/health-check` | `/api/v2/databases/*` → Orchestrator | Django `/api/v2/databases/health-check/` | ✅ OK |

### 2.3 Operations Endpoints

| Frontend вызывает | API Gateway route | Backend | Статус |
|-------------------|-------------------|---------|--------|
| `GET /operations/` | `/api/v2/operations/*` → Orchestrator | Django `/api/v2/operations/list-operations/` | ⚠️ PATH MISMATCH |
| `GET /operations/{id}/` | `/api/v2/operations/*` → Orchestrator | Django `/api/v2/operations/get-operation/` | ⚠️ PATH MISMATCH |
| `POST /operations/{id}/cancel/` | `/api/v2/operations/*` → Orchestrator | Django `/api/v2/operations/cancel-operation/` | ⚠️ PATH MISMATCH |

### 2.4 System Endpoints

| Frontend вызывает | API Gateway route | Backend | Статус |
|-------------------|-------------------|---------|--------|
| `GET /system/health/` | `/api/v2/system/*` → Orchestrator | Django `/api/v2/system/health/` | ✅ OK |

### 2.5 Workflows Endpoints

| Frontend вызывает | API Gateway route | Backend | Статус |
|-------------------|-------------------|---------|--------|
| `GET /workflows/list-workflows` | `/api/v2/workflows/*` → Orchestrator | Django `/api/v2/workflows/list-workflows/` | ✅ OK |
| `GET /workflows/get-workflow?workflow_id=` | `/api/v2/workflows/*` → Orchestrator | Django `/api/v2/workflows/get-workflow/` | ✅ OK |
| `POST /workflows/execute-workflow` | `/api/v2/workflows/*` → Orchestrator | Django `/api/v2/workflows/execute-workflow/` | ✅ OK |
| `POST /workflows/create-workflow` | `/api/v2/workflows/*` → Orchestrator | Django `/api/v2/workflows/create-workflow/` | ✅ OK (Phase 3) |
| `POST /workflows/update-workflow` | `/api/v2/workflows/*` → Orchestrator | Django `/api/v2/workflows/update-workflow/` | ✅ OK (Phase 3) |
| `POST /workflows/delete-workflow` | `/api/v2/workflows/*` → Orchestrator | Django `/api/v2/workflows/delete-workflow/` | ✅ OK (Phase 3) |
| `POST /workflows/validate-workflow` | `/api/v2/workflows/*` → Orchestrator | Django `/api/v2/workflows/validate-workflow/` | ✅ OK (Phase 3) |
| `POST /workflows/clone-workflow` | `/api/v2/workflows/*` → Orchestrator | Django `/api/v2/workflows/clone-workflow/` | ✅ OK (Phase 3) |
| `GET /workflows/list-executions` | `/api/v2/workflows/*` → Orchestrator | Django `/api/v2/workflows/list-executions/` | ✅ OK (Phase 4) |
| `GET /workflows/get-execution` | `/api/v2/workflows/*` → Orchestrator | Django `/api/v2/workflows/get-execution/` | ✅ OK (Phase 4) |
| `POST /workflows/cancel-execution` | `/api/v2/workflows/*` → Orchestrator | Django `/api/v2/workflows/cancel-execution/` | ✅ OK (Phase 4) |
| `GET /workflows/get-execution-steps` | `/api/v2/workflows/*` → Orchestrator | Django `/api/v2/workflows/get-execution-steps/` | ✅ OK (Phase 4) |

### 2.6 Extensions Endpoints

| Frontend вызывает | API Gateway route | Backend | Статус |
|-------------------|-------------------|---------|--------|
| `GET /extensions/list-extensions` | `/api/v2/extensions/*` → Orchestrator | Django `/api/v2/extensions/list-extensions/` | ✅ OK (Phase 1) |
| `GET /extensions/get-install-status` | `/api/v2/extensions/*` → Orchestrator | Django `/api/v2/extensions/get-install-status/` | ✅ OK (Phase 1) |
| `POST /extensions/retry-installation` | `/api/v2/extensions/*` → Orchestrator | Django `/api/v2/extensions/retry-installation/` | ✅ OK (Phase 1) |

### 2.7 Service Mesh Endpoints

| Frontend вызывает | API Gateway route | Backend | Статус |
|-------------------|-------------------|---------|--------|
| `GET /service-mesh/get-metrics/` | `/api/v2/service-mesh/*` → Orchestrator | Django `/api/v2/service-mesh/get-metrics/` | ✅ OK (Phase 1) |

### 2.8 WebSocket Endpoints

| Frontend вызывает | API Gateway route | Backend | Статус |
|-------------------|-------------------|---------|--------|
| `WS /ws/workflow/{execution_id}/` | `/ws/workflow/*` → Orchestrator | Django Channels | ✅ OK (Phase 5) |
| `WS /ws/service-mesh/` | `/ws/service-mesh/*` → Orchestrator | Django Channels | ✅ OK (Phase 5) |

### 2.9 Internal API Endpoints (Service-to-Service)

| Service вызывает | API Gateway route | Backend | Статус |
|-------------------|-------------------|---------|--------|
| `POST /audit/log-compensation` | `/api/v2/audit/*` → Orchestrator | Django `/api/v2/audit/log-compensation/` | ✅ OK (Phase 6) |
| `POST /events/store-failed` | `/api/v2/events/*` → Orchestrator | Django `/api/v2/events/store-failed/` | ✅ OK (Phase 6) |
| `GET /events/pending` | `/api/v2/events/*` → Orchestrator | Django `/api/v2/events/pending/` | ✅ OK (Phase 6) |

### 2.10 Tracing (Jaeger) Endpoints

| Frontend вызывает | API Gateway route | Backend | Статус |
|-------------------|-------------------|---------|--------|
| `GET /tracing/get-trace?trace_id=` | `/api/v2/tracing/*` → Jaeger | Jaeger `/api/traces/{id}` | ✅ OK (transform) |
| `GET /tracing/search-traces` | `/api/v2/tracing/*` → Jaeger | Jaeger `/api/traces` | ✅ OK (transform) |

### 2.11 RAS Adapter Endpoints (Direct)

| Frontend вызывает | API Gateway route | Backend | Статус |
|-------------------|-------------------|---------|--------|
| - | `/api/v2/infobases/*` → RAS Adapter | RAS `/api/v2/list-infobases` | ✅ OK (transform) |
| - | `/api/v2/sessions/*` → RAS Adapter | RAS `/api/v2/list-sessions` | ✅ OK (transform) |
| - | `/api/v2/list-clusters` (legacy) | RAS `/api/v2/list-clusters` | ✅ OK |

---

## 3. ВЫЯВЛЕННЫЕ ПРОБЛЕМЫ (ВСЕ ИСПРАВЛЕНЫ)

### 3.1 КРИТИЧНЫЕ (Блокируют функционал) - ✅ ИСПРАВЛЕНО

| # | Проблема | Где | Решение | Статус |
|---|----------|-----|---------|--------|
| 1 | Нет CRUD для clusters | Django API v2 | `create-cluster`, `update-cluster`, `delete-cluster`, `get-cluster-databases` | ✅ Phase 2 |
| 2 | Нет route для extensions | API Gateway | `/api/v2/extensions/*` → Orchestrator | ✅ Phase 1 |
| 3 | Нет CRUD для workflows | Django API v2 | `create-workflow`, `update-workflow`, `delete-workflow`, `validate-workflow`, `clone-workflow` | ✅ Phase 3 |
| 4 | Нет executions endpoints | Django API v2 | `list-executions`, `get-execution`, `cancel-execution`, `get-execution-steps` | ✅ Phase 4 |

### 3.2 ВАЖНЫЕ (Влияют на UX) - ✅ ИСПРАВЛЕНО

| # | Проблема | Где | Решение | Статус |
|---|----------|-----|---------|--------|
| 5 | Operations path mismatch | Frontend | Унифицировано на action-based | ✅ |
| 6 | Service mesh path mismatch | Frontend | `/api/v2/service-mesh/*` route добавлен | ✅ Phase 1 |
| 7 | WebSocket routes не настроены | API Gateway | WebSocket proxy `/ws/*` | ✅ Phase 5 |

### 3.3 ТЕХНИЧЕСКИЙ ДОЛГ

| # | Проблема | Где | Примечание |
|---|----------|-----|------------|
| 8 | Дублирование legacy routes | API Gateway | `/api/v2/list-clusters` и `/api/v2/clusters/list-clusters` - legacy поддержка сохранена |
| 9 | Смешанные стили path params | Везде | v2 унифицирован на query params: `?operation_id=` |

---

## 4. ДИАГРАММА ПОТОКОВ ДАННЫХ (TO-BE)

### 4.1 Основные потоки

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           FRONTEND (React:5173)                          │
├─────────────────────────────────────────────────────────────────────────┤
│  Pages:                                                                  │
│  - /clusters        → clustersApi      → /api/v2/clusters/*             │
│  - /databases       → databasesApi     → /api/v2/databases/*            │
│  - /operations      → operationsApi    → /api/v2/operations/*           │
│  - /workflows       → workflowsApi     → /api/v2/workflows/*            │
│  - /extensions      → extensionsApi    → /api/v2/extensions/*           │
│  - /system-status   → systemApi        → /api/v2/system/*               │
│  - /service-mesh    → serviceMeshApi   → /api/v2/service-mesh/*         │
│  - /tracing         → jaegerApi        → /api/v2/tracing/*              │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                        API GATEWAY (Go:8080)                             │
├─────────────────────────────────────────────────────────────────────────┤
│  Middleware: JWT Auth → Rate Limit (100/min) → CORS → Logger            │
│                                                                          │
│  Routes:                                                                 │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │ PUBLIC (no auth):                                                │   │
│  │   POST /api/token          → Orchestrator                        │   │
│  │   GET  /health             → Local handler                       │   │
│  │   GET  /metrics            → Prometheus handler                  │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │ PROTECTED (JWT required):                                        │   │
│  │                                                                  │   │
│  │ → Orchestrator (Django:8000):                                    │   │
│  │   /api/v2/clusters/*       (cluster CRUD)                        │   │
│  │   /api/v2/databases/*      (database management)                 │   │
│  │   /api/v2/operations/*     (batch operations)                    │   │
│  │   /api/v2/workflows/*      (workflow engine)                     │   │
│  │   /api/v2/extensions/*     (extension install)                   │   │
│  │   /api/v2/system/*         (health checks)                       │   │
│  │   /api/v2/service-mesh/*   (service metrics)                     │   │
│  │                                                                  │   │
│  │ → RAS Adapter (Go:8088):                                         │   │
│  │   /api/v2/infobases/*      → /api/v2/{action}                    │   │
│  │   /api/v2/sessions/*       → /api/v2/{action}                    │   │
│  │   /api/v2/ras/*            → /api/v2/{action} (direct RAS)       │   │
│  │                                                                  │   │
│  │ → Jaeger (16686):                                                │   │
│  │   /api/v2/tracing/*        → /api/{path}                         │   │
│  │                                                                  │   │
│  │ → WebSocket:                                                     │   │
│  │   /ws/workflow/*           → Orchestrator Channels               │   │
│  │   /ws/service-mesh/*       → Orchestrator Channels               │   │
│  └─────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
            ┌───────────────────────┼───────────────────────┐
            │                       │                       │
            ▼                       ▼                       ▼
┌───────────────────┐   ┌───────────────────┐   ┌───────────────────┐
│   Orchestrator    │   │   RAS Adapter     │   │     Jaeger        │
│   Django:8000     │   │   Go:8088         │   │     :16686        │
├───────────────────┤   ├───────────────────┤   ├───────────────────┤
│ - Cluster CRUD    │   │ - List clusters   │   │ - Trace search    │
│ - Database CRUD   │   │ - List infobases  │   │ - Trace details   │
│ - Operations      │   │ - Lock/Unlock     │   │ - Services list   │
│ - Workflows       │   │ - Sessions mgmt   │   │                   │
│ - Extensions      │   │ - Block/Unblock   │   │                   │
│ - System health   │   │                   │   │                   │
│ - Service mesh    │   │ Event Handlers:   │   │                   │
│                   │   │ - Lock command    │   │                   │
│ Celery tasks →    │   │ - Unlock command  │   │                   │
│   Redis Queue →   │   │ - Terminate cmd   │   │                   │
│   Worker          │   │                   │   │                   │
└───────────────────┘   └───────────────────┘   └───────────────────┘
            │                       ▲
            │                       │
            ▼                       │
┌───────────────────┐               │
│     Worker        │───────────────┘
│   Go (x2 replicas)│   Redis Pub/Sub events
├───────────────────┤
│ - OData operations│
│ - Extension install│
│ - State machine   │
│ - Event publishing│
└───────────────────┘
            │
            ▼
┌───────────────────┐
│   1C Databases    │
│   OData API       │
└───────────────────┘
```

### 4.2 Extension Install Flow (Event-Driven)

```
Frontend                API Gateway              Orchestrator                Worker                  RAS Adapter
   │                        │                        │                          │                        │
   │  POST /extensions/     │                        │                          │                        │
   │  retry-installation    │                        │                          │                        │
   │───────────────────────►│                        │                          │                        │
   │                        │  Proxy to Django       │                          │                        │
   │                        │───────────────────────►│                          │                        │
   │                        │                        │  Create Celery task      │                        │
   │                        │                        │─────────────────────────►│                        │
   │                        │                        │                          │                        │
   │                        │◄───────────────────────│  Return task_id          │                        │
   │◄───────────────────────│                        │                          │                        │
   │                        │                        │                          │                        │
   │  WebSocket connect     │                        │                          │                        │
   │  /ws/workflow/{exec}   │                        │                          │                        │
   │═══════════════════════►│═══════════════════════►│                          │                        │
   │                        │                        │                          │                        │
   │                        │                        │                          │  Redis: cmd:lock       │
   │                        │                        │                          │─────────────────────────►
   │                        │                        │                          │                        │
   │                        │                        │                          │◄─────────────────────────
   │                        │                        │                          │  Redis: evt:locked     │
   │                        │                        │                          │                        │
   │◄═══════════════════════│◄═══════════════════════│◄─────────────────────────│  Status update         │
   │  WS: node_status       │                        │                          │                        │
   │                        │                        │                          │                        │
   │                        │                        │                          │  ... continue ...      │
```

---

## 5. ПЛАН ИСПРАВЛЕНИЙ (ВСЕ ЗАВЕРШЕНО)

### Phase 1: API Gateway Routes ✅ ЗАВЕРШЕНО (2025-11-28)

**API Gateway** - routes добавлены:
- [x] `/api/v2/extensions/*` → Orchestrator
- [x] `/api/v2/service-mesh/*` → Orchestrator

### Phase 2: Cluster CRUD ✅ ЗАВЕРШЕНО (2025-11-28)

**Django Orchestrator** - endpoints добавлены:
- [x] `/api/v2/clusters/create-cluster/` POST
- [x] `/api/v2/clusters/update-cluster/` POST/PUT
- [x] `/api/v2/clusters/delete-cluster/` DELETE
- [x] `/api/v2/clusters/get-cluster-databases/` GET

### Phase 3: Workflow CRUD ✅ ЗАВЕРШЕНО (2025-11-28)

**Django Orchestrator** - workflow CRUD:
- [x] `/api/v2/workflows/create-workflow/` POST
- [x] `/api/v2/workflows/update-workflow/` POST
- [x] `/api/v2/workflows/delete-workflow/` POST
- [x] `/api/v2/workflows/validate-workflow/` POST
- [x] `/api/v2/workflows/clone-workflow/` POST

### Phase 4: Workflow Executions ✅ ЗАВЕРШЕНО (2025-11-28)

**Django Orchestrator** - execution management:
- [x] `/api/v2/workflows/list-executions/` GET
- [x] `/api/v2/workflows/get-execution/` GET
- [x] `/api/v2/workflows/cancel-execution/` POST
- [x] `/api/v2/workflows/get-execution-steps/` GET

### Phase 5: WebSocket Proxy ✅ ЗАВЕРШЕНО (2025-11-28)

**API Gateway** - WebSocket proxy:
- [x] `/ws/workflow/{execution_id}/` → Orchestrator Channels
- [x] `/ws/service-mesh/` → Orchestrator Channels

**Файлы:**
- `go-services/api-gateway/internal/handlers/websocket.go` - bidirectional WebSocket proxy
- Ping/Pong heartbeat, connection pooling, graceful shutdown

### Phase 6: Event-Driven Completion ✅ ЗАВЕРШЕНО (2025-11-28)

**Go Worker** - Saga compensation improvements:
- [x] `compensation_executor.go` - exponential backoff с retry (2s → 4s → 8s, jitter ±300ms)
- [x] `compensation_metrics.go` - Prometheus метрики
- [x] `audit_logger.go` - HTTP Audit Logger
- [x] `watchdog.go` - детекция stuck workflows (30 мин threshold)

**Django Orchestrator** - PostgreSQL fallback:
- [x] `/api/v2/audit/log-compensation/` - audit logging (internal API)
- [x] `/api/v2/events/store-failed/` - failed events storage
- [x] `/api/v2/events/pending/` - pending events monitoring
- [x] `event_replay.py` - Celery task для replay failed events

**Go Shared** - event publishing:
- [x] `PublishWithFallback()` - Redis → PostgreSQL graceful degradation
- [x] `SetServiceToken()` - internal service authentication

**Security fixes:**
- [x] `IsInternalService` permission class (X-Internal-Service-Token)
- [x] Thread-safe rand.Rand (mutex for jitter calculation)

---

## 6. ТЕКУЩЕЕ СОСТОЯНИЕ ROUTES В API GATEWAY

```go
// router.go (актуальное состояние - 2025-11-28)

// Public routes (no auth)
router.POST("/api/token", handlers.ProxyToOrchestratorAuth)
router.POST("/api/token/refresh", handlers.ProxyToOrchestratorAuth)
router.GET("/health", handlers.HealthCheck)

// WebSocket routes (Phase 5)
router.GET("/ws/workflow/:execution_id/", handlers.WebSocketWorkflowProxy)
router.GET("/ws/service-mesh/", handlers.WebSocketServiceMeshProxy)

// V2 API routes (JWT protected, rate limited 100/min)
v2 := router.Group("/api/v2")
v2.Use(auth.AuthMiddleware(jwtManager))
v2.Use(middleware.RateLimitMiddleware(100, time.Minute))

// RAS Adapter routes
infobases := v2.Group("/infobases")  // → RAS Adapter
sessions := v2.Group("/sessions")    // → RAS Adapter

// Legacy flat routes (backward compatibility)
v2.GET("/list-clusters", rasHandler)
v2.GET("/list-infobases", rasHandler)
// ... etc

// Orchestrator routes (✅ ALL COMPLETED)
v2.Any("/operations/*path", handlers.ProxyToOrchestratorV2)
v2.Any("/databases/*path", handlers.ProxyToOrchestratorV2)
v2.Any("/clusters/*path", handlers.ProxyToOrchestratorV2)     // Phase 2
v2.Any("/workflows/*path", handlers.ProxyToOrchestratorV2)
v2.Any("/system/*path", handlers.ProxyToOrchestratorV2)
v2.Any("/extensions/*path", handlers.ProxyToOrchestratorV2)   // Phase 1
v2.Any("/service-mesh/*path", handlers.ProxyToOrchestratorV2) // Phase 1

// Jaeger routes
v2.Any("/tracing/*path", jaegerHandler)
```

---

## 7. СРАВНЕНИЕ С АРХИТЕКТУРНЫМИ ДОКУМЕНТАМИ

### 7.1 WORKFLOW_ENGINE_ARCHITECTURE.md vs AS-IS

**Документ описывает (TO-BE):**
```
POST   /api/v1/workflows/templates/          # Create workflow
GET    /api/v1/workflows/templates/          # List workflows
GET    /api/v1/workflows/templates/{id}/     # Get workflow
PUT    /api/v1/workflows/templates/{id}/     # Update workflow
DELETE /api/v1/workflows/templates/{id}/     # Delete workflow
POST   /api/v1/workflows/templates/{id}/validate/

POST   /api/v1/workflows/executions/         # Execute workflow
GET    /api/v1/workflows/executions/         # List executions
GET    /api/v1/workflows/executions/{id}/    # Get execution
POST   /api/v1/workflows/executions/{id}/cancel/
GET    /api/v1/workflows/executions/{id}/steps/
```

**⚠️ ПРОБЛЕМЫ (все исправлены 2025-11-28):**

| Проблема | Описание | Решение | Статус |
|----------|----------|---------|--------|
| **API Version** | Документ использует v1, проект на v2 | v2 action-based реализован | ✅ |
| **Naming Style** | Документ: `/templates/{id}/`, AS-IS: `action-based` | v2 унифицирован на action-based | ✅ |
| **Missing CRUD** | create/update/delete не реализованы | Phase 3 | ✅ |
| **Missing Validation** | `validate-workflow` не реализован | Phase 3 | ✅ |
| **Missing Executions** | list/get/cancel executions не реализованы | Phase 4 | ✅ |

**Соответствие TO-BE → AS-IS (обновлено 2025-11-28):**

| Workflow Engine Doc (v1) | Нужно в API v2 | AS-IS Статус |
|--------------------------|----------------|--------------|
| `POST /templates/` | `POST /api/v2/workflows/create-workflow` | ✅ Phase 3 |
| `GET /templates/` | `GET /api/v2/workflows/list-workflows` | ✅ EXISTS |
| `GET /templates/{id}/` | `GET /api/v2/workflows/get-workflow?workflow_id=` | ✅ EXISTS |
| `PUT /templates/{id}/` | `POST /api/v2/workflows/update-workflow` | ✅ Phase 3 |
| `DELETE /templates/{id}/` | `POST /api/v2/workflows/delete-workflow` | ✅ Phase 3 |
| `POST /templates/{id}/validate/` | `POST /api/v2/workflows/validate-workflow` | ✅ Phase 3 |
| `POST /executions/` | `POST /api/v2/workflows/execute-workflow` | ✅ EXISTS |
| `GET /executions/` | `GET /api/v2/workflows/list-executions` | ✅ Phase 4 |
| `GET /executions/{id}/` | `GET /api/v2/workflows/get-execution?execution_id=` | ✅ Phase 4 |
| `POST /executions/{id}/cancel/` | `POST /api/v2/workflows/cancel-execution` | ✅ Phase 4 |
| `GET /executions/{id}/steps/` | `GET /api/v2/workflows/get-execution-steps` | ✅ Phase 4 |

### 7.2 EVENT_DRIVEN_ARCHITECTURE.md vs AS-IS

**Документ описывает Event Channels (TO-BE):**
```
Commands:
  commands:cluster-service:infobase:lock
  commands:cluster-service:sessions:terminate
  commands:cluster-service:infobase:unlock
  commands:batch-service:extension:install
  commands:orchestrator:status:update

Events:
  events:cluster-service:infobase:locked
  events:cluster-service:sessions:closed
  events:cluster-service:infobase:unlocked
  events:batch-service:extension:installed
  events:orchestrator:operation:completed
```

**⚠️ ПРОБЛЕМЫ (частично решены 2025-11-28):**

| Проблема | Описание | Решение | Статус |
|----------|----------|---------|--------|
| **Service Name** | Doc: `cluster-service`, AS-IS: `ras-adapter` | Обновить документ | ⚠️ Doc outdated |
| **Channel Naming** | Doc: `commands:cluster-service:*`, AS-IS: `cmd:*` | Унифицировать | ⚠️ Doc outdated |
| **Batch Service** | Doc описывает batch-service | В разработке | ⚠️ In progress |
| **Orchestrator Events** | Doc: Orchestrator слушает events | Phase 6 - PostgreSQL fallback | ✅ |

**Текущая реализация в ras-adapter (AS-IS):**

```
Event Handlers (ras-adapter):
  cmd:lock       → Lock infobase via RAS
  cmd:unlock     → Unlock infobase via RAS
  cmd:terminate  → Terminate sessions via RAS

Event Publishing:
  evt:locked     → Published after lock
  evt:unlocked   → Published after unlock
  evt:terminated → Published after terminate
```

**Gap Analysis (обновлено 2025-11-28):**

| Event-Driven Doc | Status | Notes |
|------------------|--------|-------|
| Worker State Machine | ✅ IMPLEMENTED | State Machine с compensation stack |
| Saga Compensation | ✅ IMPLEMENTED | CompensationExecutor с retry + exponential backoff |
| Idempotent Handlers | ✅ IMPLEMENTED | Redis SetNX в Worker |
| Correlation ID | ✅ IMPLEMENTED | Реализовано в Worker |
| WebSocket notifications | ✅ IMPLEMENTED | API Gateway WebSocket proxy (Phase 5) |
| Event Replay | ✅ IMPLEMENTED | PostgreSQL fallback + Celery replay (Phase 6) |
| Watchdog | ✅ IMPLEMENTED | Stuck workflow detection (30 min threshold) |
| Audit Logging | ✅ IMPLEMENTED | HTTP Audit Logger + Django endpoint |

### 7.3 СТАТУС РЕАЛИЗАЦИИ (обновлено 2025-11-28)

```
┌─────────────────────────────────────────────────────────────────────────┐
│                     ALL ARCHITECTURE GAPS CLOSED ✅                      │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  ┌─────────────────────┐    ┌─────────────────────┐                     │
│  │  WORKFLOW ENGINE    │    │   EVENT-DRIVEN      │                     │
│  │  (docs/WORKFLOW_*)  │    │ (docs/architecture/)│                     │
│  └──────────┬──────────┘    └──────────┬──────────┘                     │
│             │                          │                                 │
│             ▼                          ▼                                 │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │                    ✅ ALL IMPLEMENTED                            │   │
│  ├─────────────────────────────────────────────────────────────────┤   │
│  │                                                                  │   │
│  │  WORKFLOW (Phase 3+4):              EVENT-DRIVEN (Phase 6):     │   │
│  │  ✅ create-workflow                 ✅ Saga compensation         │   │
│  │  ✅ update-workflow                 ✅ WebSocket proxy (Phase 5) │   │
│  │  ✅ delete-workflow                 ✅ Event replay (PostgreSQL) │   │
│  │  ✅ validate-workflow               ✅ Worker State Machine      │   │
│  │  ✅ clone-workflow                  ✅ Watchdog (stuck detection)│   │
│  │  ✅ list-executions                 ✅ Audit logging             │   │
│  │  ✅ get-execution                   ✅ Prometheus metrics        │   │
│  │  ✅ cancel-execution                                             │   │
│  │  ✅ get-execution-steps                                          │   │
│  │                                                                  │   │
│  │  CLUSTERS (Phase 2):                API GATEWAY (Phase 1+5):    │   │
│  │  ✅ create-cluster                  ✅ /extensions/* route       │   │
│  │  ✅ update-cluster                  ✅ /service-mesh/* route     │   │
│  │  ✅ delete-cluster                  ✅ /ws/* WebSocket proxy     │   │
│  │  ✅ get-cluster-databases                                        │   │
│  │                                                                  │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                                                          │
│  ✅ ПОЛНЫЙ СПИСОК РЕАЛИЗОВАННОГО:                                        │
│  • Workflow CRUD: create, update, delete, validate, clone               │
│  • Workflow Executions: list, get, cancel, get-steps                    │
│  • Cluster CRUD: create, update, delete, get-databases                  │
│  • API Gateway: extensions, service-mesh, WebSocket proxy               │
│  • Event-Driven: Saga compensation, watchdog, audit, replay             │
│  • Security: IsInternalService permission, thread-safe jitter           │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

### 7.4 ПРИОРИТИЗИРОВАННЫЙ ПЛАН РЕАЛИЗАЦИИ - ✅ ВСЕ ЗАВЕРШЕНО (2025-11-28)

**Phase 1: API Gateway Routes** ✅
- [x] Добавить `/api/v2/extensions/*` → Orchestrator
- [x] Добавить `/api/v2/service-mesh/*` → Orchestrator

**Phase 2: Cluster CRUD** ✅
- [x] `create-cluster` endpoint
- [x] `update-cluster` endpoint
- [x] `delete-cluster` endpoint
- [x] `get-cluster-databases` endpoint

**Phase 3: Workflow CRUD** ✅
- [x] `create-workflow` endpoint
- [x] `update-workflow` endpoint
- [x] `delete-workflow` endpoint
- [x] `validate-workflow` endpoint (DAG validation)
- [x] `clone-workflow` endpoint

**Phase 4: Workflow Executions** ✅
- [x] `list-executions` endpoint
- [x] `get-execution` endpoint
- [x] `cancel-execution` endpoint
- [x] `get-execution-steps` endpoint

**Phase 5: WebSocket Proxy** ✅
- [x] API Gateway WebSocket proxy `/ws/*`
- [x] Orchestrator Django Channels integration
- [x] Bidirectional proxy with Ping/Pong heartbeat

**Phase 6: Event-Driven Completion** ✅
- [x] Saga compensation в Worker (CompensationExecutor с retry + metrics)
- [x] Watchdog для stuck workflows (30 мин threshold)
- [x] HTTP Audit Logger + Django endpoints
- [x] PostgreSQL event replay fallback (FailedEvent model + Celery replay task)
- [x] Security: IsInternalService permission, thread-safe jitter

---

## 8. ССЫЛКИ НА ФАЙЛЫ

**API Gateway:**
- `go-services/api-gateway/internal/routes/router.go`
- `go-services/api-gateway/internal/handlers/proxy_ras.go`
- `go-services/api-gateway/internal/handlers/databases.go`
- `go-services/api-gateway/internal/handlers/websocket.go` (Phase 5 - WebSocket proxy)

**Django Orchestrator:**
- `orchestrator/apps/api_v2/urls.py`
- `orchestrator/apps/api_v2/views/clusters.py`
- `orchestrator/apps/api_v2/views/databases.py`
- `orchestrator/apps/api_v2/views/operations.py`
- `orchestrator/apps/api_v2/views/workflows.py`
- `orchestrator/apps/api_v2/views/extensions.py`
- `orchestrator/apps/api_v2/views/system.py`
- `orchestrator/apps/api_v2/views/service_mesh.py`
- `orchestrator/apps/api_v2/views/audit.py` (Phase 6 - compensation logging)
- `orchestrator/apps/api_v2/views/events.py` (Phase 6 - failed events storage)
- `orchestrator/apps/core/permissions.py` (Phase 6 - IsInternalService)
- `orchestrator/apps/operations/tasks/event_replay.py` (Phase 6 - Celery replay task)
- `orchestrator/apps/operations/models.py` (CompensationAuditLog, FailedEvent)

**Frontend:**
- `frontend/src/api/endpoints/*.ts`
- `frontend/src/hooks/useWorkflowExecution.ts`
- `frontend/src/hooks/useServiceMesh.ts`

**RAS Adapter:**
- `go-services/ras-adapter/internal/api/rest/v2/routes.go`
- `go-services/ras-adapter/internal/eventhandlers/*.go`

**Worker:**
- `go-services/worker/cmd/main.go`
- `go-services/worker/internal/processor/processor.go`
- `go-services/worker/internal/statemachine/compensation_executor.go` (Phase 6 - retry logic)
- `go-services/worker/internal/statemachine/compensation_metrics.go` (Phase 6 - Prometheus)
- `go-services/worker/internal/statemachine/audit_logger.go` (Phase 6 - HTTP audit)
- `go-services/worker/internal/statemachine/watchdog.go` (Phase 6 - stuck detection)

**Shared:**
- `go-services/shared/events/publisher.go` (PublishWithFallback, SetServiceToken)
