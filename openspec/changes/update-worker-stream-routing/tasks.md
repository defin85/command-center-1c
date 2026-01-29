## 1. Implementation
- [x] Go Worker: добавить поддержку `WORKER_STREAM_NAME` в `go-services/shared/config` и прокинуть в `queue.Consumer`.
- [x] Go Worker: использовать `cfg.WorkerConsumerGroup` (env `WORKER_CONSUMER_GROUP`) вместо хардкода `worker-group`.
- [x] Orchestrator: направить `execute_workflow` в stream `commands:worker:workflows` (вместо `commands:worker:operations`).
- [x] Обновить документацию по деплою/локальной разработке: переменные окружения для двух deployment’ов.

## 2. Tests
- [x] Go tests: consumer использует заданные stream/group (минимум unit test на конфиг/инициализацию).
- [x] Orchestrator tests: при включённом Go workflow engine enqueue идёт в правильный stream.

## 3. Validation
- [x] `./scripts/dev/lint.sh`
- [x] `go test ./...` в `go-services/worker`
- [x] `cd orchestrator && pytest apps/api_v2/tests/test_workflows_execute.py -q`
