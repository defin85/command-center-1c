## 1. API behaviour
- [ ] `/api/v2/operations/execute-ibcmd-cli/`: при Redis/XADD enqueue failure возвращать `503` и `error.code=REDIS_ERROR`.
- [ ] `/api/v2/dlq/retry/`: при Redis-ошибках (чтение DLQ и enqueue) возвращать `503` и `error.code=REDIS_ERROR`.
- [ ] Для не-Redis ошибок enqueue сохранить текущую семантику (коды/ошибки) и при необходимости уточнить `error.code`.

## 2. OpenAPI contracts
- [ ] `contracts/orchestrator/openapi.yaml`: добавить `503` ответы для:
  - `POST /api/v2/operations/execute-ibcmd-cli/`
  - `POST /api/v2/dlq/retry/`

## 3. Tests
- [ ] API test: `execute-ibcmd-cli` возвращает `503` на Redis enqueue failure и содержит `error.code=REDIS_ERROR`.
- [ ] API test: `dlq.retry` возвращает `503` на Redis read failure и содержит `error.code=REDIS_ERROR`.
- [ ] (опционально) API test: `dlq.retry` возвращает `503` на Redis enqueue failure и содержит `error.code=REDIS_ERROR`.

## 4. Validation
- [ ] `./scripts/dev/lint.sh`
- [ ] `./scripts/dev/pytest.sh apps/api_v2/tests -q` (минимум затронутые тесты)

