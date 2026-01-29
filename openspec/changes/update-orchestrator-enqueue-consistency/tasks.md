## 1. Implementation
- [x] Инвентаризировать все места, где вызывается `redis_client.enqueue_operation(...)` в orchestrator.
- [x] Перевести enqueue на `enqueue_operation_stream(...)` (или эквивалент с exception propagation) и убрать игнорирование результата.
- [x] Обновлять `BatchOperation.status=queued` только после успешного XADD.
- [x] Выравнять обработку ошибок: единый формат логирования/`EnqueueResult` при Redis ошибках.

## 2. Tests
- [x] Тест: при исключении на enqueue операция НЕ становится `queued` в БД (`OperationsServiceCore.enqueue_operation`).
- [x] Тест: enqueue_workflow_execution возвращает ошибку при Redis failure и не “маскирует” успешный запуск.

## 3. Validation
- [x] `./scripts/dev/lint.sh`
- [x] `cd orchestrator && pytest apps/operations/tests -q` (минимум покрыть изменённые сервисы)
