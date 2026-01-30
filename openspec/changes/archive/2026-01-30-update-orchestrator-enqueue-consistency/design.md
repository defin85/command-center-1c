# Design: DB↔Redis enqueue consistency (fail-closed)

## Инвариант
Если Orchestrator возвращает успех enqueue и/или переводит `BatchOperation.status` в `queued`, то сообщение ДОЛЖНО быть успешно записано в Redis Stream.

## Текущее поведение (as-is)
- Вызовы enqueue часто не проверяют результат:
  - `orchestrator/apps/operations/services/operations_service/core.py:180-195`
  - `orchestrator/apps/operations/services/operations_service/workflow.py:75-91`
  - и другие места (см. `rg "enqueue_operation("`).
- `enqueue_operation()` скрывает исключения и возвращает `False`:
  - `orchestrator/apps/operations/redis_client.py:107-127`
- При этом `BatchOperation.status` переводится в `queued` без гарантии успешного XADD.

## Предлагаемое решение
Минимальный consistency-first вариант:
- Для всех enqueue‑путей использовать `enqueue_operation_stream()` (который `raise` на ошибке) или эквивалентный механизм, который не скрывает ошибку.
- Любое обновление `BatchOperation.status = queued` делать **только после успешного XADD**.
- Ошибки enqueue должны приводить к:
  - возвращению ошибки (или `EnqueueResult.success=false`) вверх по стеку;
  - отсутствию “ложного” queued в БД.

## Риски/компромиссы
- При нестабильном Redis пользователи увидят больше ошибок вместо “зависших queued”. Это намеренно: консистентность важнее.
- В будущем более надёжный вариант — outbox (Postgres таблица + ретраящий паблишер), но это отдельный change.

