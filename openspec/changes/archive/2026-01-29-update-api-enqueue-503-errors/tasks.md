## 1. API behaviour
- [x] `/api/v2/operations/execute-ibcmd-cli/`: при Redis/XADD enqueue failure возвращать `503` и `error.code=REDIS_ERROR`.
- [x] `/api/v2/dlq/retry/`: при Redis-ошибках (чтение DLQ и enqueue) возвращать `503` и `error.code=REDIS_ERROR`.
- [x] Для не-Redis ошибок enqueue сохранить текущую семантику (коды/ошибки) и при необходимости уточнить `error.code`.

## 2. OpenAPI contracts
- [x] `contracts/orchestrator/openapi.yaml`: добавить `503` ответы для:
  - `POST /api/v2/operations/execute-ibcmd-cli/`
  - `POST /api/v2/dlq/retry/`

## 3. Tests
- [x] API test: `execute-ibcmd-cli` возвращает `503` на Redis enqueue failure и содержит `error.code=REDIS_ERROR`.
- [x] API test: `dlq.retry` возвращает `503` на Redis read failure и содержит `error.code=REDIS_ERROR`.
- [x] (опционально) API test: `dlq.retry` возвращает `503` на Redis enqueue failure и содержит `error.code=REDIS_ERROR`.

## 4. Validation
- [x] `./scripts/dev/lint.sh`
- [x] `./scripts/dev/pytest.sh apps/api_v2/tests -q` (минимум затронутые тесты)
