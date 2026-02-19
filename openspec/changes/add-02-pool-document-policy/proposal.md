# Change: Декларативный document-policy для управления цепочками документов на рёбрах пула

## Why
Сейчас пользователь не может декларативно управлять тем, какие документы должны создаваться на конкретных рёбрах пула и как заполняются реквизиты/табличные части.

Текущее поведение опирается на runtime payload с общим `entity_name` и `documents_by_database`, что недостаточно для операторского сценария с разными типами документов и связками вида `Реализация/Поступление + соответствующая СчетФактура`.

В результате для новых вариантов распределения требуется backend hardcode, что масштабируется плохо и противоречит цели отделения доменной конфигурации от execution-логики.

## What Changes
- Ввести отдельную доменную конфигурацию `document_policy` (versioned, declarative), управляемую пользователем в tenant scope.
- Зафиксировать хранение document-policy на уровне topology edge metadata (с валидацией схемы и operator-safe read/write path).
- Зафиксировать runtime-этап компиляции `document_plan_artifact` из:
  - активной topology версии;
  - distribution artifact run;
  - document-policy.
- Зафиксировать контракт публикации для цепочек документов с per-document `entity_name`, маппингом реквизитов и табличных частей, а также связями между документами цепочки.
- Зафиксировать обязательный режим `required` для связанной счёт-фактуры в policy (при соответствующей настройке цепочки).
- Зафиксировать fail-closed taxonomy для ошибок policy/configuration/mapping/chain.

## Impact
- Affected specs:
  - `pool-document-policy` (new)
  - `organization-pool-catalog`
  - `pool-workflow-execution-core`
  - `pool-odata-publication`
- Affected code (expected):
  - `orchestrator/apps/api_v2/views/intercompany_pools.py`
  - `orchestrator/apps/intercompany_pools/models.py`
  - `orchestrator/apps/intercompany_pools/pool_domain_steps.py`
  - `orchestrator/apps/intercompany_pools/workflow_runtime.py`
  - `go-services/worker/internal/drivers/poolops/publication_transport.go`
  - `contracts/orchestrator/openapi.yaml`
  - `frontend/src/pages/PoolsCatalog/**`
  - `frontend/src/pages/PoolsRuns/**`
- Dependencies:
  - change `update-01-pool-run-full-chain-distribution` должен предоставить канонический distribution artifact для create-run path.
  - change `refactor-03-unify-platform-execution-runtime` должен использовать `document_plan_artifact` как вход для атомарного workflow compile и единого observability path.

## Coordination with sibling changes
- Этот change — средний слой между:
  - upstream `update-01-pool-run-full-chain-distribution` (даёт `distribution_artifact`);
  - downstream `refactor-03-unify-platform-execution-runtime` (исполняет атомарный workflow graph и unified runtime/operations projection).
- В этом change НЕ переопределяется формула распределения суммы по DAG; используется upstream artifact.
- В этом change НЕ фиксируются platform-wide execution controls (`/operations` projection, queue-only workflow API path); это scope `refactor-03-unify-platform-execution-runtime`.

## Non-Goals
- Не вводить полноценный script/DSL engine для произвольной бизнес-логики.
- Не менять текущую RBAC/mapping модель publication auth.
- Не делать новый визуальный редактор workflow DAG; используется текущий topology management контур.
- Не покрывать все возможные документы 1С “из коробки”; поддерживаются только типы, явно заданные policy и поддержанные publication transport.

## Assumptions
- Минимальный жизнеспособный вариант: document-policy хранится в `PoolEdgeVersion.metadata` и доступен через существующий topology API.
- Обязательность связанной счёт-фактуры определяется policy (`invoice_mode=required`), а не неявным hardcode в runtime.
- Retry для публикации работает от зафиксированного `document_plan_artifact`, а не от произвольного пользовательского payload.
