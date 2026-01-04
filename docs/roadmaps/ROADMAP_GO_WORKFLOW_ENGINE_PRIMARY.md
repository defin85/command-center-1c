# Roadmap: Go Workflow Engine as Primary (creates BatchOperations + UI node progress)

Цель: при `ENABLE_GO_WORKFLOW_ENGINE=true` workflow исполняется **в Go Worker** как основной engine и:
- каждый `operation`-node создаёт **ровно одну** `BatchOperation` на список `database_ids`;
- следующий node **ждёт завершения** этой `BatchOperation` (последовательная консистентность);
- UI `/workflows/executions/*` показывает **node progress** (running/completed/failed/skipped) в реальном времени;
- решение работает при **нескольких worker-репликах** и выдерживает рестарты без дубликатов операций.

---

## Термины

- **WorkflowTemplate**: шаблон workflow (DAG) в Orchestrator (Postgres).
- **WorkflowExecution**: runtime-инстанс workflow в Orchestrator (Postgres), источник правды для UI.
- **OperationTemplate**: шаблон операции (OData/RAS/CLI/IBCMD) в Orchestrator.
- **BatchOperation**: операция в Orchestrator (Postgres), исполняется Go Worker через Redis Streams.
- **worker-ops**: воркеры, которые исполняют `BatchOperation` (существующий поток).
- **worker-workflows**: воркеры, которые исполняют workflow DAG (новый поток).

---

## Входные ограничения (важно)

- **Celery удалён**, единственный execution engine для операций — Go Worker + Redis Streams.
- **1C transactions < 15s** (долгие шаги через worker).
- **OData batch 100-500 records/batch** (не увеличивать без необходимости).
- **Coverage > 70%** на изменяемые модули.
- API: v2 action-based (`/api/v2/*`), изменения фиксируются contract-first в `contracts/**`.

---

## Текущее состояние (as-is) и пробелы

1) `ENABLE_GO_WORKFLOW_ENGINE=true` включает Go workflow engine, но:
- `operation`-ноды не материализуются в `BatchOperation` (фактически `execution_skipped`).
- нет стабильного обновления `WorkflowExecution.node_statuses/current_node_id` из Go engine, поэтому UI не видит node progress.

2) Go workflow engine генерирует свой `execution_id` для внутреннего state (Redis), который не совпадает с `WorkflowExecution.id` в Orchestrator:
- ухудшает корреляцию, резюмирование, отладку и консистентность истории.

3) Worker consumer сейчас читает один stream `commands:worker:operations`, сообщение обрабатывается синхронно.
- если workflow будет ждать операцию в том же worker-процессе/потоке, можно получить дедлок/задержки.

---

## Целевая архитектура (to-be)

### Потоки и сервисы

Frontend -> API Gateway -> Orchestrator -> Redis -> worker-workflows + worker-ops

- `commands:worker:workflows` (NEW): только `execute_workflow` (workflow DAG orchestration).
- `commands:worker:operations` (EXISTING): `create/update/query/ras/cli/ibcmd/...` (BatchOperation execution).
- `events:*` (EXISTING): события от worker, которые уже обрабатывает Orchestrator EventSubscriber.

### Основной flow: execute workflow

1) Frontend вызывает `POST /api/v2/workflows/execute-workflow/` (mode=async).
2) Orchestrator создаёт `WorkflowExecution` (pending) и кладёт meta-операцию `execute_workflow` в `commands:worker:workflows`.
3) worker-workflows получает `execute_workflow`, делает:
   - `GET /api/v2/internal/workflows/get-execution?execution_id=...` (уже есть)
   - `POST /api/v2/internal/workflows/update-execution-status` -> `running` (уже есть, но расширим/добавим node updates)
4) worker-workflows исполняет DAG. На каждом node:
   - отправляет `node_started` в Orchestrator (internal API) -> обновление DB + WebSocket broadcast;
   - если node.type == operation:
     - вызывает Orchestrator internal API: **создать BatchOperation из OperationTemplate**
     - Orchestrator создаёт `BatchOperation` + `Task` и **enqueue** в `commands:worker:operations`;
     - worker-workflows ждёт завершения BatchOperation (с таймаутом node) и после:
       - `node_completed` или `node_failed` в Orchestrator (internal API).
5) По завершению DAG worker-workflows обновляет `WorkflowExecution` -> `completed/failed` (internal API) и финальный результат.

---

## Контракты (contracts-first)

План: добавить новые internal endpoints и (минимально) расширить существующие, с контрактами в `contracts/**`.

### 1) Internal: создать BatchOperation из operation template

`POST /api/v2/internal/operations/create-from-template`

Назначение: “materialize operation-node -> BatchOperation (1 шт.)”, с идемпотентностью по `(execution_id, node_id)`.

Request (пример):
```json
{
  "execution_id": "uuid",
  "node_id": "n1",
  "template_id": "tpl-uuid-or-string",
  "database_ids": ["db-uuid-1", "db-uuid-2"],
  "context": { "any": "vars" },
  "created_by": "username",
  "idempotency_key": "execution_id:n1",
  "enqueue": true
}
```

Response (пример):
```json
{
  "success": true,
  "operation_id": "batch-<...>",
  "status": "queued",
  "total_tasks": 2
}
```

Поведение:
- если `idempotency_key` уже существует -> вернуть тот же `operation_id` (без создания дубликата).
- обязательно записать `metadata.workflow_execution_id`, `metadata.node_id`, `metadata.trace_id` (если есть).

### 2) Internal: статус BatchOperation (для ожидания)

`GET /api/v2/internal/operations/status?operation_id=...`

Response (пример):
```json
{
  "operation_id": "batch-...",
  "status": "queued|processing|completed|failed|cancelled",
  "progress": 0-100,
  "summary": { "total": 2, "completed": 2, "failed": 0 }
}
```

MVP: polling с backoff в worker-workflows.
Оптимизация позже: event-driven ожидание через Redis Streams (см. этапы).

### 3) Internal: node updates для UI (WebSocket)

Вариант A (рекомендуется): отдельный endpoint

`POST /api/v2/internal/workflows/update-node-status`

Request (пример):
```json
{
  "execution_id": "uuid",
  "node_id": "n1",
  "status": "running|completed|failed|skipped",
  "progress": 0.0,
  "current_node_id": "n1",
  "output": { "operation_id": "batch-..." },
  "error_message": "",
  "duration_ms": 1234
}
```

Orchestrator:
- обновляет `WorkflowExecution.node_statuses`, `current_node_id`, `completed_nodes/failed_nodes`;
- делает `broadcast_node_update` + `broadcast_workflow_update`, чтобы UI видел прогресс.

Вариант B: расширить существующий `update-execution-status` (менее чисто).

---

## Изоляция воркеров (обязательно, чтобы не ловить дедлоки)

### Почему нужно разделять очереди

workflow-воркер делает “оркестрацию” и может долго ждать завершения операции. Операции должны продолжать исполняться независимо.

### Что делаем

- Добавить новый stream `commands:worker:workflows` + отдельную consumer-group (например `worker-workflows-group`).
- Поднять отдельный deployment `worker-workflows` (replicas Nw).
- Оставить `worker-ops` (replicas No) на `commands:worker:operations`.
- Оба deployment используют один и тот же код, но выбирают stream через env:
  - `WORKER_STREAM_NAME=commands:worker:operations|commands:worker:workflows`
  - `WORKER_CONSUMER_GROUP=...` (разные группы)

---

## Идемпотентность и устойчивость (must-have)

### 1) Workflow execution lock

В worker-workflows:
- Redis lock `cc1c:workflow:{execution_id}:lock` (lease TTL + heartbeat),
- если lock уже занят -> не исполняем второй раз (или пытаемся reclaim по idle timeout).

### 2) Operation-node idempotency

В Orchestrator:
- таблица маппинга `workflow_node_operations` (или unique-index в отдельной модели):
  - `(execution_id, node_id)` unique -> `operation_id`
  - хранить status/attempt для дебага.

### 3) Resume после рестарта

Если worker-workflows умер после создания BatchOperation:
- на рестарте читает маппинг `(execution_id,node_id)` и продолжает ждать завершения, не создавая новую операцию.

---

## Cancellation

Требование: cancel из UI должен реально останавливать ожидание и дальнейшие шаги.

MVP:
- worker-workflows периодически проверяет `WorkflowExecution.status` (internal `get-execution`) и останавливается, если `cancelled`.

Позже:
- отдельная meta-операция `cancel_workflow` в `commands:worker:workflows` (event-driven).

---

## Наблюдаемость (UI + tracing + metrics)

### UI node progress

Источник данных для UI: `WorkflowExecution` в Postgres (обновляется internal API).
Push: `apps/templates/consumers.py` WebSocket broadcast.

### Корреляция

- `execution_id` единый (равен `WorkflowExecution.id`).
- Каждый `BatchOperation.metadata` содержит `workflow_execution_id` + `node_id`.
- Timeline events для операций включают те же поля.

### Метрики (минимум)

- `workflow_execution_duration_seconds` (p50/p95/p99)
- `workflow_node_duration_seconds` (по node type/template)
- `workflow_operation_wait_seconds`
- `workflow_node_failures_total` (+ error_code)
- `workflow_duplicate_operation_prevented_total` (idempotency hit)

---

## Декомпозиция на этапы

### Этап 0 — Контракты и дизайн (contracts-first)

Результат:
- Контракты internal endpoints: `create-from-template`, `operation status`, `update-node-status`.
- Решение по stream’ам и consumer groups (workflow vs ops).
- Определены SLO/метрики и стратегия rollout.

Проверка:
- OpenAPI контракты валидируются.
- Есть документ с sequence diagram и полями request/response.

---

### Этап 1 — Queue split + деплой воркеров

Результат:
- Добавлен stream `commands:worker:workflows`.
- Worker умеет читать stream, заданный через env (`WORKER_STREAM_NAME`).
- Отдельный deployment `worker-workflows` (можно 1 реплика на stage).

Проверка:
- Сообщения `execute_workflow` попадают в workflow stream и обрабатываются.
- Операции (`commands:worker:operations`) продолжают работать как раньше.

---

### Этап 2 — Единый execution_id в Go workflow engine

Результат:
- Go workflow engine больше не генерирует свой `execution_id` для state store.
- Внутренний state (Redis) и отчётность используют `WorkflowExecution.id`.

Проверка:
- В логах нет “result_execution_id != execution_id”.
- Любой node/event коррелируется по одному id.

---

### Этап 3 — Internal API: create-from-template + status

Результат:
- Orchestrator умеет по internal API создавать `BatchOperation` из `OperationTemplate` и enqueue в ops stream.
- Orchestrator отдаёт статус `BatchOperation` по internal API.
- Идемпотентность `(execution_id,node_id)` реализована.

Проверка:
- Повторный вызов create-from-template не создаёт вторую BatchOperation.
- В `/operations` появляется операция с `metadata.workflow_execution_id/node_id`.

---

### Этап 4 — Go OperationExecutor: “создать и ждать”

Результат:
- `operation`-нода в Go workflow engine:
  - создаёт BatchOperation через internal API (ровно одну),
  - ждёт завершения,
  - на success даёт output в workflow context,
  - на failure валит workflow (по StopOnError=true).

Проверка:
- В реальном workflow операции создаются и выполняются последовательно.
- При падении workflow-воркера посередине, после рестарта нет дублей (resume).

---

### Этап 5 — UI node progress: update-node-status + WebSocket broadcast

Результат:
- worker-workflows отправляет node events в Orchestrator.
- Orchestrator обновляет `WorkflowExecution.node_statuses/current_node_id` и делает broadcast.

Проверка:
- UI `/workflows/executions/<id>` показывает “running node”, прогресс и итоги по node.
- WebSocket не “молчит” во время исполнения.

---

### Этап 6 — Cancellation end-to-end

Результат:
- Cancel execution из UI приводит к остановке исполнения workflow в worker-workflows.
- (Опционально) отмена текущей BatchOperation (если имеет смысл) через существующий cancel operation flow.

Проверка:
- После cancel workflow не продолжает следующие node.
- Статусы в UI корректны.

---

### Этап 7 — Hardening: event-driven ожидание (опционально, после MVP)

Цель: убрать polling статусов, снизить нагрузку на Orchestrator.

Варианты:
- worker-workflows слушает Redis stream `events:worker:completed|failed` своей consumer-group и фильтрует по `operation_id`;
- или worker-ops пишет дополнительные компактные события `events:workflow:operation_completed` (специально для ожидания).

Проверка:
- 0 polling запросов к Orchestrator в steady-state.
- Устойчивость при рестарте consumers (PEL/claim).

---

## Rollout plan

1) Stage:
- включить `ENABLE_GO_WORKFLOW_ENGINE=true`;
- поднять `worker-workflows` (1 реплика), оставить `worker-ops` как есть;
- ограничить список workflow templates (allowlist) через runtime setting или флаг.

2) Canary on prod:
- 1-5% workflow executions идут в Go engine (по allowlist/label), остальные — старый путь.
- мониторинг метрик: failures, duplicate-prevented, timeouts.

3) Full rollout:
- enable for all templates, старый путь оставить как fallback (kill-switch).

4) Fallback:
- `ENABLE_GO_WORKFLOW_ENGINE=false` возвращает исполнение workflow в Orchestrator (Python engine).

