# Change: Унифицировать исполнение pools через workflow execution core

## Why
Сейчас контур `pools` начал формироваться как самостоятельный runtime с собственными run-состояниями, retry и audit-потоком. Это создаёт риск второй платформы исполнения рядом с уже существующим `workflows` runtime.

Целевой сценарий системы — единый механизм сервисных функций над ИБ (развёртывание, публикация, манипуляции данными) с переиспользованием driver schema и общего execution lifecycle.

Нужен архитектурный разворот: `pools` остаётся доменным модулем, а исполнение переводится в единый workflow execution core.

Дополнительно, после уточнения scope `add-intercompany-pool-distribution-module`, execution-часть намеренно выведена из foundation change и должна быть закрыта здесь.

## What Changes
- Зафиксировать `workflows` как единственный runtime для многошагового исполнения (`Template/Run/Step`, retry, audit, status lifecycle, queueing).
- Зафиксировать `pools` как domain facade + compiler:
  - `Pool Schema Template` и параметры пула компилируются в workflow-compatible execution plan.
  - `Pool Run` создаётся/выполняется через workflow runtime с сохранением pool-доменной идентичности.
- Зафиксировать канонический mapping статусов (без open-ended интерпретаций):
  - `pool:draft` — локально создан run до создания `workflow_run`;
  - `workflow:pending -> pool:validated`;
  - `workflow:running -> pool:publishing`;
  - `workflow:completed + failed_targets=0 -> pool:published`;
  - `workflow:completed + failed_targets>0 -> pool:partial_success`;
  - `workflow:failed|cancelled -> pool:failed`.
- Зафиксировать tenant boundary для unified runtime:
  - `PoolRun.tenant_id` и `WorkflowExecution.tenant_id` обязаны совпадать;
  - создание/чтение workflow-run вне tenant-контекста pool-run запрещено.
- Зафиксировать единую retry-семантику для публикации:
  - доменный контракт `max_attempts_total=5`;
  - компилятор маппит это в workflow step policy (initial attempt + bounded retries);
  - endpoint retry на facade повторно исполняет только failed subset через workflow runtime.
- Зафиксировать queueing-контракт phase 1:
  - используется существующий workflow stream `commands:worker:workflows`;
  - приоритет по умолчанию `normal`;
  - выделенный SLA/priority lane не вводится в этом change.
- Принять deferred execution scope из `add-intercompany-pool-distribution-module`:
  - фактический старт/исполнение `pool run`,
  - lifecycle orchestration и status projection,
  - unified provenance/diagnostics,
  - единая retry/audit semantics через workflow core.
- Сохранить publication service (OData) как adapter-слой step execution, а не как отдельный оркестратор.
- Ввести совместимый API переход:
  - `/pools/runs*` остаётся доменным API,
  - но фактическое исполнение и статусная модель резолвятся через workflow run reference;
  - API обязан возвращать provenance block (`workflow_run_id`, `workflow_status`, `execution_backend`, `retry_chain`).
- Запретить удаление `workflows` до миграции всех consumers на unified execution core.

## Impact
- Affected specs:
  - `pool-workflow-execution-core` (new)
- Prerequisites:
  - foundation задачи из `add-intercompany-pool-distribution-module` (catalog/data/contracts/UI baseline) должны быть завершены или зафиксированы как входной baseline.
- Affected code (high-level):
  - `orchestrator/apps/intercompany_pools/**`
  - `orchestrator/apps/templates/workflow/**`
  - `orchestrator/apps/api_v2/views/intercompany_pools.py`
  - `contracts/orchestrator/**`
  - `frontend/src/pages/Pools/**`

## Non-Goals
- Полное удаление `workflows` в рамках этого change.
- Переписывание business-алгоритмов распределения (top-down/bottom-up) как предметной логики.
- Замена OData-интеграции на другой транспорт.
- Введение отдельной queue/lane инфраструктуры для pools в phase 1.
