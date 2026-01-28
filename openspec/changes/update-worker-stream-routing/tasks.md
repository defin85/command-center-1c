## 1. Implementation
- [ ] Go Worker: добавить поддержку `WORKER_STREAM_NAME` в `go-services/shared/config` и прокинуть в `queue.Consumer`.
- [ ] Go Worker: использовать `cfg.WorkerConsumerGroup` (env `WORKER_CONSUMER_GROUP`) вместо хардкода `worker-group`.
- [ ] Orchestrator: направить `execute_workflow` в stream `commands:worker:workflows` (вместо `commands:worker:operations`).
- [ ] Обновить документацию по деплою/локальной разработке: переменные окружения для двух deployment’ов.

## 2. Tests
- [ ] Go tests: consumer использует заданные stream/group (минимум unit test на конфиг/инициализацию).
- [ ] Orchestrator tests: при включённом Go workflow engine enqueue идёт в правильный stream.

## 3. Validation
- [ ] `./scripts/dev/lint.sh`
- [ ] `go test ./...` в `go-services/worker`
- [ ] `cd orchestrator && pytest apps/api_v2/tests/test_workflows_execute.py -q`

