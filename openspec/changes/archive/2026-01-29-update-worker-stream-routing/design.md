# Design: Separate streams + env-driven consumer config

## Цель
Снизить архитектурный риск, отмеченный в roadmap: workflow-оркестрация не должна блокировать исполнение операций и не должна конкурировать за один stream/consumer-group.

## Предлагаемое поведение
### Worker
- Stream name берётся из env `WORKER_STREAM_NAME` (default: `commands:worker:operations`).
- Consumer group берётся из env `WORKER_CONSUMER_GROUP` (default: сохраняем текущий “боевой” дефолт из конфигурации).
- Consumer name остаётся уникальным по `WORKER_ID`.

### Orchestrator
- `enqueue_workflow_execution` публикует в `commands:worker:workflows`.
- BatchOperation операции продолжают публиковаться в `commands:worker:operations`.

## Совместимость
- Если `WORKER_STREAM_NAME` не задан, поведение не меняется (worker продолжает читать operations stream).
- Для rollout можно сначала включить чтение нового stream в отдельной реплике worker, затем переключить Orchestrator.

## Риски
- Нужны договорённости по consumer group именам для разных deployment’ов (иначе два разных deployment’а могут случайно делить одну group на одном stream).

