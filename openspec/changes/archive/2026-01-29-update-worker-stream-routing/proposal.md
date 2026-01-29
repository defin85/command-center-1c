# Change: Конфигурируемый routing Redis Streams для Worker (под roadmap workflow engine primary)

## Why
Roadmap `docs/roadmaps/ROADMAP_GO_WORKFLOW_ENGINE_PRIMARY.md` явно требует разделить очереди:
- `commands:worker:operations` (существующий поток для BatchOperation)
- `commands:worker:workflows` (новый поток для execute_workflow)
и выбирать stream/group через env (`WORKER_STREAM_NAME`, `WORKER_CONSUMER_GROUP`).

Сейчас:
- Worker consumer хардкодит stream `commands:worker:operations` и group `worker-group` (`go-services/worker/internal/queue/stream_consumer.go:19-33`, `:75-83`);
- env `WORKER_CONSUMER_GROUP` уже существует в shared config (`go-services/shared/config/config.go:130-137`), но consumer его не использует;
- Orchestrator enqueue_workflow_execution отправляет `execute_workflow` в общий operations stream (`orchestrator/apps/operations/services/operations_service/workflow.py:52-77`), что противоречит целевой архитектуре и увеличивает риск дедлоков/конкуренции.

## What Changes
- Worker: сделать stream и consumer group **конфигурируемыми** (env-driven).
- Orchestrator: направлять `execute_workflow` в `commands:worker:workflows` (не смешивая с operations).
- Обновить документацию/настройки деплоя (env vars), чтобы можно было поднять отдельные deployment’ы:
  - `worker-ops` (operations stream)
  - `worker-workflows` (workflows stream)

## Non-Goals
- Не реализуем в этом change полный workflow DAG engine и node progress (это отдельные задачи roadmap).
- Не меняем формат событий results (`events:worker:*`) в рамках этого change.

## Impact
- Go Worker: `internal/queue` + `shared/config`.
- Orchestrator: enqueue path для workflow execute.
- Документация: обновление roadmap/README (если нужно).

