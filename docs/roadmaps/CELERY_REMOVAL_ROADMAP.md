# Roadmap: Полный отказ от Celery

> **Архитектурный план миграции с Celery на Go-based execution engine**

**Дата создания:** 2025-12-07
**Последнее обновление:** 2025-12-07
**Статус:** IN PROGRESS (Phase 0-2 ✅ Done)
**Автор:** Claude Opus 4.5 (Architecture Analysis)

---

## Executive Summary

Данный документ описывает план полного отказа от Celery (Worker + Beat) и переноса всей логики выполнения операций в Go Worker. Django Orchestrator остается только для API и бизнес-логики, но не выполняет никаких операций.

**Цели:**
1. Убрать Celery Worker и Celery Beat полностью
2. Перенести периодические задачи в Go (scheduler)
3. Go Worker становится единым execution engine
4. Упростить архитектуру (меньше runtime dependencies)
5. Улучшить производительность (Go vs Python для I/O-bound tasks)

---

## 1. Текущее состояние Celery

### 1.1. Beat Schedule (периодические задачи)

| Задача | Интервал | Файл |
|--------|----------|------|
| cluster-health-check | 60s | `databases/tasks.py` |
| database-health-check | 60s | `databases/tasks.py` |
| batch-service-health-check | 30s | `databases/tasks.py` |
| cleanup-status-history | daily 3:00 UTC | `databases/tasks.py` |
| replay-failed-events | 60s | `operations/tasks/event_replay.py` |
| cleanup-old-replayed-events | daily 4:00 UTC | `operations/tasks/event_replay.py` |

### 1.2. Inventory Celery Tasks

#### A. Operations App (`orchestrator/apps/operations/tasks.py`)

| Task | Назначение | Сложность миграции | Зависимости |
|------|------------|-------------------|-------------|
| `enqueue_operation` | Отправка операции в Redis queue для Go Worker | **УДАЛИТЬ** - уже дублирует функционал | Redis, BatchOperation model |
| `process_operation_with_template` | Рендеринг шаблона и постановка в очередь | **СРЕДНЯЯ** - Template Engine на Python | Template model, Jinja2 |
| `process_operation_result` | Обработка результата от Go Worker | **НИЗКАЯ** - простой update БД | BatchOperation, Task models |
| `process_batch_operation` | Группировка batch операций | **НИЗКАЯ** - TODO, не реализовано | - |
| `cleanup_old_operations` | Очистка старых операций | **НИЗКАЯ** - простой DELETE | BatchOperation model |

#### B. Operations Event Replay (`orchestrator/apps/operations/tasks/event_replay.py`)

| Task | Назначение | Сложность миграции | Зависимости |
|------|------------|-------------------|-------------|
| `replay_failed_events` | Повторная отправка failed events в Redis | **СРЕДНЯЯ** | FailedEvent model, Redis |
| `cleanup_old_replayed_events` | Удаление старых replayed events | **НИЗКАЯ** | FailedEvent model |

#### C. Databases App (`orchestrator/apps/databases/tasks.py`)

| Task | Назначение | Сложность миграции | Зависимости |
|------|------------|-------------------|-------------|
| `check_databases_health` | Проверка здоровья баз (on-demand) | **НИЗКАЯ** | Database model, DatabaseService |
| `queue_extension_installation` | Постановка установки расширений | **УДАЛИТЬ** - Go Worker уже делает | Redis, BatchOperation |
| `subscribe_installation_progress` | Pub/Sub подписка на прогресс | **УДАЛИТЬ** - Go Worker уже делает | Redis Pub/Sub |
| `periodic_cluster_health_check` | **PERIODIC:** Проверка кластеров | **ВЫСОКАЯ** - требует RAS Adapter | Cluster model, RasAdapterClient |
| `sync_cluster_task` | Синхронизация инфобаз кластера | **СРЕДНЯЯ** | ClusterService, BatchOperation |
| `periodic_database_health_check` | **PERIODIC:** Проверка баз | **ВЫСОКАЯ** - батчинг, locks | Database model, Redis |
| `check_database_batch` | Батч проверки баз | **СРЕДНЯЯ** | DatabaseService |
| `periodic_batch_service_health_check` | **PERIODIC:** Проверка BatchService | **НИЗКАЯ** | BatchService model |
| `cleanup_old_status_history` | **PERIODIC:** Очистка истории | **НИЗКАЯ** | StatusHistory model |

#### D. Templates App (`orchestrator/apps/templates/tasks.py`)

| Task | Назначение | Сложность миграции | Зависимости |
|------|------------|-------------------|-------------|
| `execute_workflow_node` | Выполнение ноды DAG workflow | **ВЫСОКАЯ** - сложная логика | WorkflowExecution, DAG, Handlers |
| `execute_workflow_async` | Асинхронный запуск workflow | **ВЫСОКАЯ** | WorkflowEngine |
| `execute_parallel_nodes` | Параллельное выполнение нод | **ВЫСОКАЯ** - Celery group | Celery primitives |
| `cancel_workflow_async` | Отмена workflow | **СРЕДНЯЯ** | WorkflowEngine |

### 1.3. Классификация задач

```
┌─────────────────────┐   ┌─────────────────────┐   ┌─────────────────────┐
│   УДАЛИТЬ (3)       │   │   PERIODIC (6)      │   │   ON-DEMAND (7)     │
│   Дублирование      │   │   → Go Scheduler    │   │   → Go Worker       │
├─────────────────────┤   ├─────────────────────┤   ├─────────────────────┤
│ • enqueue_operation │   │ • cluster_health    │   │ • sync_cluster      │
│ • queue_extension   │   │ • database_health   │   │ • template_render   │
│ • subscribe_install │   │ • batch_svc_health  │   │ • workflow_execute  │
│                     │   │ • cleanup_history   │   │ • result_process    │
│                     │   │ • replay_events     │   │ • batch_operation   │
│                     │   │ • cleanup_replayed  │   │ • cancel_workflow   │
│                     │   │                     │   │ • parallel_nodes    │
└─────────────────────┘   └─────────────────────┘   └─────────────────────┘
```

---

## 2. Целевая архитектура

### 2.1. Диаграмма компонентов (AS-IS vs TO-BE)

```
╔═══════════════════════════════════════════════════════════════════════════╗
║                              AS-IS (Current)                               ║
╠═══════════════════════════════════════════════════════════════════════════╣
║                                                                           ║
║  ┌─────────────┐     ┌─────────────────────────────────────────────────┐  ║
║  │  Frontend   │────▶│              API Gateway (Go:8180)              │  ║
║  └─────────────┘     └───────────────────────┬─────────────────────────┘  ║
║                                              │                            ║
║                      ┌───────────────────────▼─────────────────────────┐  ║
║                      │         Django Orchestrator (8200)              │  ║
║                      │  • REST API                                     │  ║
║                      │  • Business Logic                               │  ║
║                      │  • Template Engine (Jinja2)                     │  ║
║                      └───────────────────────┬─────────────────────────┘  ║
║                                              │                            ║
║           ┌──────────────────────────────────┼──────────────────────────┐ ║
║           │                                  │                          │ ║
║           ▼                                  ▼                          ▼ ║
║  ┌─────────────────┐              ┌──────────────────┐        ┌─────────┐ ║
║  │  Celery Worker  │◀────────────▶│      Redis       │◀──────▶│Go Worker│ ║
║  │  (Python)       │              │   (Broker/Queue) │        │         │ ║
║  └────────┬────────┘              └──────────────────┘        └────┬────┘ ║
║           │                                                        │      ║
║  ┌────────▼────────┐                                              ▼      ║
║  │  Celery Beat    │                               ┌─────────────────────┐║
║  │  (Scheduler)    │                               │  RAS Adapter (8188) │║
║  └─────────────────┘                               └─────────────────────┘║
║                                                                           ║
╚═══════════════════════════════════════════════════════════════════════════╝


╔═══════════════════════════════════════════════════════════════════════════╗
║                              TO-BE (Target)                                ║
╠═══════════════════════════════════════════════════════════════════════════╣
║                                                                           ║
║  ┌─────────────┐     ┌─────────────────────────────────────────────────┐  ║
║  │  Frontend   │────▶│              API Gateway (Go:8180)              │  ║
║  └─────────────┘     └───────────────────────┬─────────────────────────┘  ║
║                                              │                            ║
║                      ┌───────────────────────▼─────────────────────────┐  ║
║                      │         Django Orchestrator (8200)              │  ║
║                      │  • REST API                                     │  ║
║                      │  • Business Logic                               │  ║
║                      │  • Models & Validation                          │  ║
║                      │  • Job History Storage                          │  ║
║                      │  ✗ NO Task Execution                            │  ║
║                      └───────────────────────┬─────────────────────────┘  ║
║                                              │                            ║
║                                              ▼                            ║
║                               ┌──────────────────────┐                    ║
║                               │        Redis         │                    ║
║                               │   (Queue + Pub/Sub)  │                    ║
║                               └──────────┬───────────┘                    ║
║                                          │                                ║
║                      ┌───────────────────▼───────────────────┐            ║
║                      │      Go Worker (Unified Engine)       │            ║
║                      │  ┌─────────────────────────────────┐  │            ║
║                      │  │         Task Processor          │  │            ║
║                      │  │  • OData Operations             │  │            ║
║                      │  │  • Extension Install            │  │            ║
║                      │  │  • Template Rendering (NEW)     │  │            ║
║                      │  │  • Workflow Execution (NEW)     │  │            ║
║                      │  └─────────────────────────────────┘  │            ║
║                      │  ┌─────────────────────────────────┐  │            ║
║                      │  │         Scheduler (NEW)         │  │            ║
║                      │  │  • Health Checks (cron)         │  │            ║
║                      │  │  • Cleanup Jobs (daily)         │  │            ║
║                      │  │  • Event Replay (periodic)      │  │            ║
║                      │  │  • Prometheus Metrics           │  │            ║
║                      │  └─────────────────────────────────┘  │            ║
║                      └───────────────────┬───────────────────┘            ║
║                                          │                                ║
║                      ┌───────────────────▼───────────────────┐            ║
║                      │         RAS Adapter (8188)            │            ║
║                      └───────────────────────────────────────┘            ║
║                                                                           ║
╚═══════════════════════════════════════════════════════════════════════════╝
```

### 2.2. Ключевые изменения

| Компонент | AS-IS | TO-BE |
|-----------|-------|-------|
| **Celery Worker** | Выполняет Python tasks | **УДАЛЕН** |
| **Celery Beat** | Periodic scheduling | **УДАЛЕН** |
| **Go Worker** | OData + Extensions | Unified Execution Engine |
| **Django** | API + Tasks + Templates | API + Business Logic + Job History |
| **Template Engine** | Python/Jinja2 | Go (pongo2 - Jinja2 compatible) |
| **Scheduler** | Celery Beat | Go cron scheduler (robfig/cron) |
| **Monitoring** | Flower | Prometheus + Grafana + Django Admin |

### 2.3. Новые компоненты Go Worker

```
go-services/worker/
├── cmd/
│   └── main.go
├── internal/
│   ├── processor/               # Existing: OData, Extensions
│   ├── queue/                   # Existing: Redis consumer
│   ├── scheduler/               # NEW: Periodic tasks
│   │   ├── scheduler.go         # robfig/cron integration
│   │   ├── config.go            # Schedule configuration (YAML/env)
│   │   └── jobs/
│   │       ├── health_check.go
│   │       ├── cleanup.go
│   │       └── event_replay.go
│   ├── template/                # NEW: Template Engine
│   │   ├── engine.go            # pongo2 (Jinja2-compatible)
│   │   ├── filters.go           # guid1c, datetime1c, date1c
│   │   └── validator.go         # Security sandbox
│   ├── workflow/                # NEW: Workflow Engine
│   │   ├── engine.go            # DAG execution
│   │   ├── state.go             # Execution state (Redis)
│   │   └── handlers/            # action, condition, loop, parallel
│   ├── orchestrator/            # NEW: Django API client
│   │   ├── client.go            # HTTP client
│   │   └── models.go
│   └── metrics/                 # NEW: Prometheus metrics
│       └── metrics.go
```

---

## 3. План миграции по этапам

### Phase 0: Подготовка (Prerequisites) ✅ DONE

| # | Задача | Описание | Статус |
|---|--------|----------|--------|
| 0.1 | Internal API в Django | Endpoints для Go Worker: credentials, templates, workflows, results | ✅ Done |
| 0.2 | OpenAPI контракты | `contracts/orchestrator-internal/openapi.yaml`, генерация Go client | ✅ Done |
| 0.3 | Feature flags | `ENABLE_GO_SCHEDULER`, `ENABLE_GO_TEMPLATE_ENGINE`, `ENABLE_GO_WORKFLOW_ENGINE` | ✅ Done |
| 0.4 | Job History модели | `SchedulerJobRun`, `TaskExecutionLog` в Django | ✅ Done |

**Internal API endpoints:**
- `GET /api/internal/databases/{id}/credentials`
- `GET /api/internal/templates/{id}`
- `GET /api/internal/workflows/{id}`
- `POST /api/internal/operations/{id}/result`
- `POST /api/internal/operations/{id}/progress`
- `POST /api/internal/scheduler/runs/start`
- `POST /api/internal/scheduler/runs/{id}/complete`

### Phase 1: Go Scheduler + Monitoring ✅ DONE

| # | Задача | Описание | Статус |
|---|--------|----------|--------|
| 1.1 | Go Scheduler | `robfig/cron/v3`, конфигурация через YAML/env | ✅ Done |
| 1.2 | Redis distributed locks | SETNX для предотвращения duplicate execution | ✅ Done |
| 1.3 | Prometheus metrics | `scheduler_jobs_total`, `scheduler_job_duration_seconds`, `queue_depth` | ✅ Done |
| 1.4 | Job History integration | Запись в Django через Internal API | ✅ Done |
| 1.5 | Миграция простых jobs | `cleanup_old_status_history`, `cleanup_old_replayed_events`, `periodic_batch_service_health` | ✅ Done |
| 1.6 | Grafana dashboard | Замена Flower: job status, duration, errors | 🔲 TODO |
| 1.7 | A/B testing | Запустить оба (Celery Beat + Go), сравнить метрики | 🔲 TODO |
| 1.8 | Отключение Celery Beat | Для мигрированных задач | 🔲 TODO |

**Мониторинг включает:**
- **Prometheus metrics** — real-time данные
- **Grafana dashboards** — визуализация
- **Django Admin** — история выполнения (SchedulerJobRun, TaskExecutionLog)
- **Alerting** — SchedulerJobFailed, SchedulerJobMissed, QueueBacklog

### Phase 2: Health Check Jobs ✅ DONE

| # | Задача | Описание | Статус |
|---|--------|----------|--------|
| 2.1 | Orchestrator Client | HTTP client для Django API с connection pooling | ✅ Done |
| 2.2 | RAS Adapter Client | HTTP client для RAS Adapter API | ✅ Done |
| 2.3 | Миграция health checks | `periodic_cluster_health_check`, `periodic_database_health_check` | ✅ Done |
| 2.4 | Батчинг | Worker pool для 700+ баз, parallel processing | ✅ Done |
| 2.5 | Redis locks | Предотвращение overlap при multiple replicas | ✅ Done |

### Phase 3: Event Replay System

| # | Задача | Описание |
|---|--------|----------|
| 3.1 | Миграция replay | `replay_failed_events` → Go |
| 3.2 | API integration | Fetch FailedEvent via API, update status |
| 3.3 | Отключение Celery | Для event replay tasks |

### Phase 4: Template Engine (Go)

| # | Задача | Описание |
|---|--------|----------|
| 4.1 | pongo2 integration | Jinja2-compatible template engine |
| 4.2 | Custom filters | `guid1c`, `datetime1c`, `date1c`, `safe_string` |
| 4.3 | Security sandbox | Prohibited constructs, resource limits |
| 4.4 | Compatibility tests | Все существующие шаблоны должны работать |
| 4.5 | Миграция | `process_operation_with_template` → Go |
| 4.6 | Fallback | HTTP API к Python если pongo2 не справится |

### Phase 5: Workflow Engine (Go)

| # | Задача | Описание |
|---|--------|----------|
| 5.1 | DAG Executor | Parse JSON, topological sort, node execution |
| 5.2 | Node Handlers | ActionHandler, ConditionHandler, LoopHandler, ParallelHandler |
| 5.3 | State Management | Redis для текущего состояния, PostgreSQL для истории |
| 5.4 | Checkpoint/Resume | Error recovery, partial execution |
| 5.5 | Миграция workflow tasks | `execute_workflow_node`, `execute_workflow_async`, `execute_parallel_nodes`, `cancel_workflow_async` |

### Phase 6: Cleanup & Removal

| # | Задача | Описание |
|---|--------|----------|
| 6.1 | Удалить Celery dependencies | `requirements.txt`: celery, kombu, billiard, flower |
| 6.2 | Удалить Celery код | `config/celery.py`, `apps/*/tasks.py` |
| 6.3 | Обновить инфраструктуру | docker-compose, scripts/dev/*.sh, k8s manifests |
| 6.4 | Обновить документацию | CLAUDE.md, ROADMAP.md, LOCAL_DEVELOPMENT_GUIDE.md |

---

## 4. Файлы для изменения/удаления

### 4.1. Файлы для УДАЛЕНИЯ

```
orchestrator/
├── config/celery.py
├── apps/operations/tasks.py
├── apps/operations/tasks/
├── apps/databases/tasks.py
└── apps/templates/tasks.py

infrastructure/k8s/
├── celery-worker-deployment.yaml
├── celery-beat-deployment.yaml
└── flower-deployment.yaml
```

### 4.2. Файлы для ИЗМЕНЕНИЯ

```
orchestrator/
├── config/__init__.py              # Убрать celery_app import
├── config/settings/base.py         # Убрать CELERY_* settings
├── requirements.txt                # Убрать celery, kombu, billiard, flower
└── apps/api_v2/views/*.py          # Убрать .delay() calls

scripts/dev/
├── start-all.sh                    # Убрать celery services
├── stop-all.sh
├── restart-all.sh
├── logs.sh
└── health-check.sh

docker-compose.yml                  # Убрать celery-worker, celery-beat
```

### 4.3. Новые файлы

```
go-services/worker/internal/
├── scheduler/
├── template/
├── workflow/
├── orchestrator/
└── metrics/

orchestrator/apps/operations/models/
├── scheduler_job_run.py            # NEW: Job history
└── task_execution_log.py           # NEW: Task history

contracts/orchestrator-internal/
└── openapi.yaml                    # NEW: Internal API spec

infrastructure/monitoring/
├── dashboards/go-worker.json       # NEW: Grafana dashboard
└── alerts/scheduler.yaml           # NEW: Alert rules
```

---

## 5. Риски и митигации

### 5.1. Критические риски

| Риск | Вероятность | Влияние | Митигация |
|------|-------------|---------|-----------|
| **Template Engine несовместимость** | Высокая | Высокое | pongo2 (Jinja2-compatible). Test suite. Fallback на Python API. |
| **Workflow Engine сложность** | Высокая | Высокое | Поэтапная миграция. Feature flags. Простые workflows сначала. |
| **Race conditions в scheduler** | Средняя | Среднее | Redis SETNX locks. |
| **Data consistency** | Средняя | Высокое | Idempotency checks. Audit logging. |
| **Performance regression** | Низкая | Среднее | A/B testing. Metrics comparison. |

### 5.2. Технические риски

| Риск | Митигация |
|------|-----------|
| Jinja2 edge cases | Test suite, parallel execution (Go + Python) для verification |
| DAG execution correctness | Unit tests для каждого node type |
| Health check timing | Configurable intervals, Redis locks, timeout handling |
| Memory leaks | pprof profiling, resource limits, restart strategy |

### 5.3. Операционные риски

| Риск | Митигация |
|------|-----------|
| Rollback сложность | Feature flags per-component, canary deployments |
| Monitoring gaps | Flower до полного перехода, затем Grafana + Django Admin |
| Team learning curve | Документация, code examples |

---

## 6. Метрики успеха

### 6.1. Технические метрики

| Метрика | Текущее (Celery) | Цель (Go) |
|---------|------------------|-----------|
| Health check latency | ~200ms | <50ms |
| Template render time | ~50ms | <10ms |
| Scheduler accuracy | ~1s drift | <100ms drift |
| Memory usage (scheduler) | ~500MB | <100MB |
| CPU usage (idle) | ~5% | <1% |

### 6.2. Операционные метрики

| Метрика | Цель |
|---------|------|
| Zero downtime migration | 100% uptime during transition |
| Feature parity | All Celery tasks migrated |
| Test coverage | >80% for new Go code |
| Rollback time | <5 minutes |

---

## 7. Timeline (Ориентировочный)

```
Phase 0: Prerequisites          ███░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░
Phase 1: Go Scheduler           ░░░████░░░░░░░░░░░░░░░░░░░░░░░░░░░
Phase 2: Health Check Jobs      ░░░░░░░███░░░░░░░░░░░░░░░░░░░░░░░░
Phase 3: Event Replay           ░░░░░░░░░░██░░░░░░░░░░░░░░░░░░░░░░
Phase 4: Template Engine        ░░░░░░░░░░░░█████░░░░░░░░░░░░░░░░░
Phase 5: Workflow Engine        ░░░░░░░░░░░░░░░░░███████░░░░░░░░░░
Phase 6: Cleanup & Removal      ░░░░░░░░░░░░░░░░░░░░░░░░██░░░░░░░░
                               ────────────────────────────────────
                               Week 1    5    10   15   20   25
```

---

## 8. Альтернативы рассмотренные

### 8.1. Оставить Celery только для Workflow Engine

**Решение:** Отклонено. Цель — полный отказ от Celery для упрощения архитектуры.

### 8.2. Использовать Temporal.io вместо custom workflow engine

**Решение:** Рассмотреть в будущем, если workflow complexity увеличится. Сейчас — overkill.

### 8.3. Оставить Template Engine на Python (HTTP API)

**Решение:** Возможный fallback, если pongo2 не справится с существующими шаблонами.

---

## 9. Принятые решения

| Вопрос | Решение | Обоснование |
|--------|---------|-------------|
| **Template Engine** | pongo2 | Jinja2-совместимость, существующие шаблоны работают без изменений |
| **Workflow state** | Redis (current) + PostgreSQL (history) | Гибрид: быстрый доступ + durability |
| **Leader election** | Redis SETNX locks | Простота, достаточно для текущих требований |
| **Migration testing** | Feature flags + canary | Постепенный rollout, быстрый rollback |
| **Monitoring** | Prometheus + Grafana + Django Admin | История в Django Admin для дебага, метрики в Grafana |

---

**Документ создан:** 2025-12-07
**Последнее обновление:** 2025-12-07
**Автор:** Claude Opus 4.5
**Статус:** IN PROGRESS — Phase 0-2 завершены, Phase 3+ в очереди

**Commits:**
- `0d8122a` Phase 0+1: Go Scheduler и Internal API
- `e3afd6c` Phase 2: Health Check Jobs
