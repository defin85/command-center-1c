## 1. Gateway budget model
- [x] 1.1 Добавить checked-in runtime model для class-aware request budgets и устранить drift между `api-gateway` runtime и `configs/config.yaml`/shared config.
- [x] 1.2 Ввести explicit route-to-budget classification для `/api/v2` traffic с bounded default class и сохранением special handling для streaming/ticket endpoints.
- [x] 1.3 Добавить machine-readable `429` payload metadata: минимум `rate_limit_class`, `retry_after_seconds` и стабильный correlation context.

## 2. Gateway implementation
- [x] 2.1 Заменить один per-user bucket на budget isolation по `(tenant, user, budget_class)` с fail-closed fallback для unauthenticated/IP-only traffic.
- [x] 2.2 Выделить независимый `shell_critical` budget для `/system/bootstrap/` и других shell/control reads, чтобы heavy background class не starving'ил shell path.
- [x] 2.3 Выделить bounded `telemetry` class для `/ui/incident-telemetry/ingest/`, чтобы telemetry не делила budget с shell и interactive traffic.
- [x] 2.4 Добавить gateway logs/metrics по `429` и budget-class verdicts.

## 3. Frontend/runtime alignment
- [x] 3.1 Сохранить fail-closed retry policy: deterministic `4xx`/`429` не должны blindly retry как transient failures.
- [x] 3.2 Уменьшить mount-time burst хотя бы для первого confirmed heavy route (`Pool Master Data Sync`) через staged secondary reads или consolidated route bootstrap.
- [x] 3.3 Показать class-aware `429` diagnostics без toast flood и без подмены route-level failure state.

## 4. Verification
- [x] 4.1 Добавить Go tests для budget-class resolution, isolated buckets и `429` metadata contract.
- [x] 4.2 Добавить targeted frontend tests для `429` handling и отсутствия retry storm на telemetry/background surfaces.
- [x] 4.3 Добавить browser/live smoke: heavy background route в одной tab/session не должен делать `/api/v2/system/bootstrap/` `429` normal behavior в другой authenticated tab/session того же пользователя.
- [x] 4.4 Прогнать `cd go-services/api-gateway && go test ./...`.
- [x] 4.5 Прогнать targeted frontend tests и релевантный browser smoke.
- [x] 4.6 Прогнать `openspec validate add-gateway-request-budget-isolation --strict --no-interactive`.
