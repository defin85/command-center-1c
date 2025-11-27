# API Routes Analysis: AS-IS vs TO-BE

**Дата анализа:** 2025-11-27
**Статус:** Требуется исправление

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
| `POST /clusters/create-cluster` | `/api/v2/clusters/*` → Orchestrator | **НЕТ ENDPOINT** | ❌ MISSING |
| `PUT /clusters/update-cluster` | `/api/v2/clusters/*` → Orchestrator | **НЕТ ENDPOINT** | ❌ MISSING |
| `DELETE /clusters/delete-cluster` | `/api/v2/clusters/*` → Orchestrator | **НЕТ ENDPOINT** | ❌ MISSING |
| `POST /clusters/sync-cluster` | `/api/v2/clusters/*` → Orchestrator | Django `/api/v2/clusters/sync-cluster/` | ✅ OK |
| `GET /clusters/get-cluster-databases` | `/api/v2/clusters/*` → Orchestrator | **НЕТ ENDPOINT** | ❌ MISSING |

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
| `POST /workflows/create-workflow` | `/api/v2/workflows/*` → Orchestrator | **НЕТ ENDPOINT** | ❌ MISSING |
| `POST /workflows/update-workflow` | `/api/v2/workflows/*` → Orchestrator | **НЕТ ENDPOINT** | ❌ MISSING |
| `POST /workflows/delete-workflow` | `/api/v2/workflows/*` → Orchestrator | **НЕТ ENDPOINT** | ❌ MISSING |
| `POST /workflows/validate-workflow` | `/api/v2/workflows/*` → Orchestrator | **НЕТ ENDPOINT** | ❌ MISSING |
| `POST /workflows/clone-workflow` | `/api/v2/workflows/*` → Orchestrator | **НЕТ ENDPOINT** | ❌ MISSING |
| `GET /workflows/list-executions` | `/api/v2/workflows/*` → Orchestrator | **НЕТ ENDPOINT** | ❌ MISSING |
| `GET /workflows/get-execution` | `/api/v2/workflows/*` → Orchestrator | **НЕТ ENDPOINT** | ❌ MISSING |
| `POST /workflows/cancel-execution` | `/api/v2/workflows/*` → Orchestrator | **НЕТ ENDPOINT** | ❌ MISSING |

### 2.6 Extensions Endpoints

| Frontend вызывает | API Gateway route | Backend | Статус |
|-------------------|-------------------|---------|--------|
| `GET /extensions/list-extensions` | **НЕТ ROUTE** | Django `/api/v2/extensions/list-extensions/` | ❌ NO GATEWAY ROUTE |
| `GET /extensions/get-install-status` | **НЕТ ROUTE** | Django `/api/v2/extensions/get-install-status/` | ❌ NO GATEWAY ROUTE |
| `POST /extensions/retry-installation` | **НЕТ ROUTE** | Django `/api/v2/extensions/retry-installation/` | ❌ NO GATEWAY ROUTE |

### 2.7 Service Mesh Endpoints

| Frontend вызывает | API Gateway route | Backend | Статус |
|-------------------|-------------------|---------|--------|
| `GET /operations/service-mesh/metrics/` | `/api/v2/operations/*` → Orchestrator | Django `/api/v2/service-mesh/get-metrics/` | ⚠️ PATH MISMATCH |

### 2.8 Tracing (Jaeger) Endpoints

| Frontend вызывает | API Gateway route | Backend | Статус |
|-------------------|-------------------|---------|--------|
| `GET /tracing/get-trace?trace_id=` | `/api/v2/tracing/*` → Jaeger | Jaeger `/api/traces/{id}` | ✅ OK (transform) |
| `GET /tracing/search-traces` | `/api/v2/tracing/*` → Jaeger | Jaeger `/api/traces` | ✅ OK (transform) |

### 2.9 RAS Adapter Endpoints (Direct)

| Frontend вызывает | API Gateway route | Backend | Статус |
|-------------------|-------------------|---------|--------|
| - | `/api/v2/infobases/*` → RAS Adapter | RAS `/api/v2/list-infobases` | ✅ OK (transform) |
| - | `/api/v2/sessions/*` → RAS Adapter | RAS `/api/v2/list-sessions` | ✅ OK (transform) |
| - | `/api/v2/list-clusters` (legacy) | RAS `/api/v2/list-clusters` | ✅ OK |

---

## 3. ВЫЯВЛЕННЫЕ ПРОБЛЕМЫ

### 3.1 КРИТИЧНЫЕ (Блокируют функционал)

| # | Проблема | Где | Решение |
|---|----------|-----|---------|
| 1 | Нет CRUD для clusters | Django API v2 | Добавить `create-cluster`, `update-cluster`, `delete-cluster`, `get-cluster-databases` |
| 2 | Нет route для extensions | API Gateway | Добавить `/api/v2/extensions/*` → Orchestrator |
| 3 | Нет CRUD для workflows | Django API v2 | Добавить `create-workflow`, `update-workflow`, `delete-workflow`, `validate-workflow`, `clone-workflow` |
| 4 | Нет executions endpoints | Django API v2 | Добавить `list-executions`, `get-execution`, `cancel-execution`, `get-execution-steps` |

### 3.2 ВАЖНЫЕ (Влияют на UX)

| # | Проблема | Где | Решение |
|---|----------|-----|---------|
| 5 | Operations path mismatch | Frontend | Frontend использует `/operations/` и `/operations/{id}/`, Django использует `list-operations`, `get-operation` |
| 6 | Service mesh path mismatch | Frontend | Frontend `/operations/service-mesh/`, Django `/service-mesh/` |
| 7 | WebSocket routes не настроены | API Gateway | Нужно проксировать `/ws/*` на Django Channels |

### 3.3 ТЕХНИЧЕСКИЙ ДОЛГ

| # | Проблема | Где | Примечание |
|---|----------|-----|------------|
| 8 | Дублирование legacy routes | API Gateway | `/api/v2/list-clusters` и `/api/v2/clusters/list-clusters` - оба работают |
| 9 | Смешанные стили path params | Везде | v1: `/operations/{id}/`, v2: `?operation_id=` |

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

## 5. ПЛАН ИСПРАВЛЕНИЙ

### Phase 1: Критичные исправления (Сейчас)

1. **API Gateway** - добавить routes:
   - `/api/v2/extensions/*` → Orchestrator
   - `/api/v2/service-mesh/*` → Orchestrator

2. **Django Orchestrator** - добавить endpoints:
   - `/api/v2/clusters/create-cluster/` POST
   - `/api/v2/clusters/update-cluster/` POST/PUT
   - `/api/v2/clusters/delete-cluster/` DELETE
   - `/api/v2/clusters/get-cluster-databases/` GET

### Phase 2: Workflow Engine (Sprint 2.3)

3. **Django Orchestrator** - workflow CRUD:
   - `/api/v2/workflows/create-workflow/` POST
   - `/api/v2/workflows/update-workflow/` POST
   - `/api/v2/workflows/delete-workflow/` POST
   - `/api/v2/workflows/validate-workflow/` POST
   - `/api/v2/workflows/clone-workflow/` POST

4. **Django Orchestrator** - execution management:
   - `/api/v2/workflows/list-executions/` GET
   - `/api/v2/workflows/get-execution/` GET
   - `/api/v2/workflows/get-execution-status/` GET
   - `/api/v2/workflows/cancel-execution/` POST
   - `/api/v2/workflows/get-execution-steps/` GET

### Phase 3: WebSocket (Sprint 3.1)

5. **API Gateway** - WebSocket proxy:
   - `/ws/workflow/{execution_id}/` → Orchestrator Channels
   - `/ws/service-mesh/` → Orchestrator Channels

### Phase 4: Унификация (Backlog)

6. Стандартизация path параметров:
   - Все ID через query params: `?cluster_id=`, `?database_id=`
   - Удалить legacy path params: `/{id}/`

---

## 6. ТЕКУЩЕЕ СОСТОЯНИЕ ROUTES В API GATEWAY

```go
// router.go (актуальное состояние после исправлений)

// RAS Adapter routes
infobases := v2.Group("/infobases")  // → RAS Adapter /api/v2/
sessions := v2.Group("/sessions")    // → RAS Adapter /api/v2/

// Legacy flat routes (backward compatibility)
v2.GET("/list-clusters", rasHandler)  // → RAS Adapter
v2.GET("/list-infobases", rasHandler) // → RAS Adapter
// ... etc

// Orchestrator routes
v2.Any("/operations/*path", ProxyToOrchestratorV2)
v2.Any("/databases/*path", ProxyToOrchestratorV2)
v2.Any("/clusters/*path", ProxyToOrchestratorV2)   // ✅ Added
v2.Any("/workflows/*path", ProxyToOrchestratorV2)
v2.Any("/system/*path", ProxyToOrchestratorV2)
// MISSING: /extensions/*
// MISSING: /service-mesh/*

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

**⚠️ ПРОБЛЕМЫ:**

| Проблема | Описание | Решение |
|----------|----------|---------|
| **API Version** | Документ использует v1, проект на v2 | Обновить документ или создать v2 endpoints |
| **Naming Style** | Документ: `/templates/{id}/`, AS-IS: `action-based` (`list-workflows`) | **Унифицировать**: выбрать action-based для v2 |
| **Missing CRUD** | create/update/delete не реализованы | Добавить endpoints в Django |
| **Missing Validation** | `validate-workflow` не реализован | Критично для DAG validation |
| **Missing Executions** | list/get/cancel executions не реализованы | Нужно для мониторинга |

**Соответствие TO-BE → AS-IS:**

| Workflow Engine Doc (v1) | Нужно в API v2 | AS-IS Статус |
|--------------------------|----------------|--------------|
| `POST /templates/` | `POST /api/v2/workflows/create-workflow` | ❌ MISSING |
| `GET /templates/` | `GET /api/v2/workflows/list-workflows` | ✅ EXISTS |
| `GET /templates/{id}/` | `GET /api/v2/workflows/get-workflow?workflow_id=` | ✅ EXISTS |
| `PUT /templates/{id}/` | `POST /api/v2/workflows/update-workflow` | ❌ MISSING |
| `DELETE /templates/{id}/` | `POST /api/v2/workflows/delete-workflow` | ❌ MISSING |
| `POST /templates/{id}/validate/` | `POST /api/v2/workflows/validate-workflow` | ❌ MISSING |
| `POST /executions/` | `POST /api/v2/workflows/execute-workflow` | ✅ EXISTS |
| `GET /executions/` | `GET /api/v2/workflows/list-executions` | ❌ MISSING |
| `GET /executions/{id}/` | `GET /api/v2/workflows/get-execution?execution_id=` | ❌ MISSING |
| `POST /executions/{id}/cancel/` | `POST /api/v2/workflows/cancel-execution` | ❌ MISSING |
| `GET /executions/{id}/steps/` | `GET /api/v2/workflows/get-execution-steps` | ❌ MISSING |

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

**⚠️ ПРОБЛЕМЫ:**

| Проблема | Описание | Решение |
|----------|----------|---------|
| **Service Name** | Doc: `cluster-service`, AS-IS: `ras-adapter` | Обновить документ |
| **Channel Naming** | Doc: `commands:cluster-service:*`, AS-IS: `cmd:*` | Унифицировать |
| **Batch Service** | Doc описывает batch-service, но он в разработке | Приоритизировать batch-service |
| **Orchestrator Events** | Doc: Orchestrator слушает events, AS-IS: HTTP | Перевести на Event-Driven |

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

**Gap Analysis:**

| Event-Driven Doc | AS-IS Status | Gap |
|------------------|--------------|-----|
| Worker State Machine | ⚠️ PARTIAL | State Machine не полностью реализован |
| Saga Compensation | ❌ MISSING | Rollback логика не реализована |
| Idempotent Handlers | ⚠️ PARTIAL | Есть в ras-adapter, нет в batch-service |
| Correlation ID | ✅ EXISTS | Реализовано в Worker |
| WebSocket notifications | ❌ MISSING | API Gateway не проксирует WS |
| Event Replay | ❌ MISSING | Нет PostgreSQL fallback |

### 7.3 ДИАГРАММА GAPS

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        ARCHITECTURE GAPS                                 │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  ┌─────────────────────┐    ┌─────────────────────┐                     │
│  │  WORKFLOW ENGINE    │    │   EVENT-DRIVEN      │                     │
│  │  (docs/WORKFLOW_*)  │    │ (docs/architecture/)│                     │
│  └──────────┬──────────┘    └──────────┬──────────┘                     │
│             │                          │                                 │
│             ▼                          ▼                                 │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │                    MISSING IN AS-IS                              │   │
│  ├─────────────────────────────────────────────────────────────────┤   │
│  │                                                                  │   │
│  │  WORKFLOW:                         EVENT-DRIVEN:                 │   │
│  │  ❌ create-workflow                ❌ Saga compensation          │   │
│  │  ❌ update-workflow                ❌ WebSocket proxy            │   │
│  │  ❌ delete-workflow                ❌ Event replay (PostgreSQL)  │   │
│  │  ❌ validate-workflow              ⚠️ Worker State Machine       │   │
│  │  ❌ clone-workflow                 ⚠️ batch-service events       │   │
│  │  ❌ list-executions                                              │   │
│  │  ❌ get-execution                                                │   │
│  │  ❌ cancel-execution                                             │   │
│  │  ❌ get-execution-steps                                          │   │
│  │                                                                  │   │
│  │  CLUSTERS:                         API GATEWAY:                  │   │
│  │  ❌ create-cluster                 ❌ /extensions/* route        │   │
│  │  ❌ update-cluster                 ❌ /service-mesh/* route      │   │
│  │  ❌ delete-cluster                 ❌ /ws/* WebSocket proxy      │   │
│  │  ❌ get-cluster-databases                                        │   │
│  │                                                                  │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                                                          │
│  ✅ IMPLEMENTED:                                                         │
│  • list-workflows, get-workflow, execute-workflow                        │
│  • list-clusters, get-cluster, sync-cluster                              │
│  • list-databases, get-database, health-check                            │
│  • ras-adapter event handlers (lock/unlock/terminate)                    │
│  • Worker Redis Pub/Sub integration                                      │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

### 7.4 ПРИОРИТИЗИРОВАННЫЙ ПЛАН РЕАЛИЗАЦИИ

**Phase 1: API Gateway Routes (1 день)**
- [ ] Добавить `/api/v2/extensions/*` → Orchestrator
- [ ] Добавить `/api/v2/service-mesh/*` → Orchestrator

**Phase 2: Cluster CRUD (2 дня)**
- [ ] `create-cluster` endpoint
- [ ] `update-cluster` endpoint
- [ ] `delete-cluster` endpoint
- [ ] `get-cluster-databases` endpoint

**Phase 3: Workflow CRUD (3 дня)**
- [ ] `create-workflow` endpoint
- [ ] `update-workflow` endpoint
- [ ] `delete-workflow` endpoint
- [ ] `validate-workflow` endpoint (DAG validation)
- [ ] `clone-workflow` endpoint

**Phase 4: Workflow Executions (2 дня)**
- [ ] `list-executions` endpoint
- [ ] `get-execution` endpoint
- [ ] `cancel-execution` endpoint
- [ ] `get-execution-steps` endpoint

**Phase 5: WebSocket Proxy (2 дня)**
- [ ] API Gateway WebSocket proxy `/ws/*`
- [ ] Orchestrator Django Channels integration

**Phase 6: Event-Driven Completion (Sprint 2.3+)**
- [ ] Saga compensation в Worker
- [ ] batch-service event handlers
- [ ] PostgreSQL event replay fallback

---

## 8. ССЫЛКИ НА ФАЙЛЫ

**API Gateway:**
- `go-services/api-gateway/internal/routes/router.go`
- `go-services/api-gateway/internal/handlers/proxy_ras.go`
- `go-services/api-gateway/internal/handlers/databases.go`

**Django Orchestrator:**
- `orchestrator/apps/api_v2/urls.py`
- `orchestrator/apps/api_v2/views/clusters.py`
- `orchestrator/apps/api_v2/views/databases.py`
- `orchestrator/apps/api_v2/views/operations.py`
- `orchestrator/apps/api_v2/views/workflows.py`
- `orchestrator/apps/api_v2/views/extensions.py`
- `orchestrator/apps/api_v2/views/system.py`
- `orchestrator/apps/api_v2/views/service_mesh.py`

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
