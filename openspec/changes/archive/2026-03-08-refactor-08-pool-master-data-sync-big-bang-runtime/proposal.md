# Change: Big-bang унификация runtime для двустороннего master-data sync

## Why
Текущая реализация master-data sync имеет split execution path: outbound интегрирован в workflow/operations runtime, inbound реализован отдельным poller-путём. Это расходится с целевой архитектурой `domain -> workflow -> operations -> worker`, усложняет наблюдаемость и повышает риск разной семантики отказов.

С учётом отсутствия реального production-трафика, текущий этап является оптимальным окном для big-bang рефакторинга без длительного dual-path сопровождения.

## What Changes
- **BREAKING**: убрать split-path исполнение inbound и перевести inbound polling/ack в единый workflow runtime путь.
- Ввести единый scheduling contract для sync workload: `priority`, `role`, `server_affinity`, `deadline_at`.
- Зафиксировать commit-before-ack инвариант для inbound exchange-plan/OData: `NotifyChangesReceived` разрешён только после локального commit и сохранения checkpoint.
- Зафиксировать детерминированный `IB scope -> server_affinity` mapping с fail-closed поведением при неразрешимом scope.
- Реализовать reconcile-окно 120 секунд с fan-out/fan-in для 720 ИБ (6 серверов x 120 ИБ).
- Ввести worker topology per 1C server с affinity-aware разбором общей очереди и role/priority fairness.
- Закрыть enqueue consistency gap: mandatory deferred outbox relay + detect/repair для зависших `workflow_enqueue_outbox` и пропущенных root projection.
- Зафиксировать и внедрить fail-closed Go/No-Go gates с измеримыми pass/fail порогами перед включением big-bang режима.
- Зафиксировать machine-readable schema отчёта readiness gates и обязательный ORR sign-off (`platform + security + operations`) перед enablement.
- Зафиксировать безопасный cutover/rollback протокол для in-flight сообщений (freeze, drain, watermark, replay-safe rollback).
- Зафиксировать policy anti-starvation: reserved capacity для `manual_remediation` и tenant budget limiter для noisy tenant.
- Удалить legacy entrypoints/cron hooks, обходящие workflow runtime для inbound.
- Зафиксировать операторскую прозрачность backend-процесса: видимость очередей/задач/дедлайнов по `priority`, `role`, `server_affinity`.

## Impact
- Affected specs:
  - `pool-master-data-sync`
  - `operations-enqueue-consistency`
- Affected code:
  - `orchestrator/apps/intercompany_pools/master_data_sync_*`
  - `orchestrator/apps/templates/workflow/handlers/backends/pool_domain.py`
  - `orchestrator/apps/operations/services/operations_service/workflow.py`
  - runtime scheduler/worker routing для workflow stream
  - read-model/API для observability sync queue/task lifecycle
  - `contracts/**` (workflow enqueue payload/validation)
- Operational impact:
  - единая очередь для sync workload с affinity/priority/role;
  - per-server worker pools;
  - единые метрики SLA для inbound/outbound/reconcile;
  - формализованные go/no-go критерии и протоколы cutover/rollback.
