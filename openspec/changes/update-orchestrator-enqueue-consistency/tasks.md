## 1. Implementation
- [ ] Инвентаризировать все места, где вызывается `redis_client.enqueue_operation(...)` в orchestrator.
- [ ] Перевести enqueue на `enqueue_operation_stream(...)` (или эквивалент с exception propagation) и убрать игнорирование результата.
- [ ] Обновлять `BatchOperation.status=queued` только после успешного XADD.
- [ ] Выравнять обработку ошибок: единый формат логирования/`EnqueueResult` при Redis ошибках.

## 2. Tests
- [ ] Тест: при исключении на enqueue операция НЕ становится `queued` в БД (`OperationsServiceCore.enqueue_operation`).
- [ ] Тест: enqueue_workflow_execution возвращает ошибку при Redis failure и не “маскирует” успешный запуск.

## 3. Validation
- [ ] `./scripts/dev/lint.sh`
- [ ] `cd orchestrator && pytest apps/operations/tests -q` (минимум покрыть изменённые сервисы)

