# Change: Big-bang унификация runtime для двустороннего master-data sync

## Why
Текущая реализация master-data sync имеет split execution path: outbound интегрирован в workflow/operations runtime, inbound реализован отдельным poller-путём. Это расходится с целевой архитектурой `domain -> workflow -> operations -> worker`, усложняет наблюдаемость и повышает риск разной семантики отказов.

С учётом отсутствия реального production-трафика, текущий этап является оптимальным окном для big-bang рефакторинга без длительного dual-path сопровождения.

## What Changes
- **BREAKING**: убрать split-path исполнение inbound и перевести inbound polling/ack в единый workflow runtime путь.
- Ввести единый scheduling contract для sync workload: `priority`, `role`, `server_affinity`, `deadline_at`.
- Реализовать reconcile-окно 120 секунд с fan-out/fan-in для 720 ИБ (6 серверов x 120 ИБ).
- Ввести worker topology per 1C server с affinity-aware разбором общей очереди.
- Зафиксировать и внедрить fail-closed Go/No-Go gates перед включением big-bang режима.
- Удалить legacy entrypoints/cron hooks, обходящие workflow runtime для inbound.

## Impact
- Affected specs:
  - `pool-master-data-sync`
  - `operations-enqueue-consistency`
- Affected code:
  - `orchestrator/apps/intercompany_pools/master_data_sync_*`
  - `orchestrator/apps/templates/workflow/handlers/backends/pool_domain.py`
  - `orchestrator/apps/operations/services/operations_service/workflow.py`
  - runtime scheduler/worker routing для workflow stream
  - `contracts/**` (workflow enqueue payload/validation)
- Operational impact:
  - единая очередь для sync workload с affinity/priority/role;
  - per-server worker pools;
  - единые метрики SLA для inbound/outbound/reconcile.
