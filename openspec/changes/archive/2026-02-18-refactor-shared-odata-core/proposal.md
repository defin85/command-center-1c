# Change: Big-bang перенос shared OData transport core для `odataops` и `pool.publication_odata`

## Why
Сейчас OData-взаимодействие разделено между двумя transport-владельцами: `odataops` в worker и `pool.publication_odata` в Orchestrator domain runtime.

Это создаёт drift по retry/error mapping/auth/session semantics, увеличивает стоимость сопровождения и усложняет диагностику production-инцидентов.

Нужен единый transport-owner в worker и одновременный cutover без длительного mixed-mode.

## What Changes
- Ввести в worker выделенный shared слой `odata-core` как единого владельца OData transport concerns:
  - auth/session management;
  - retry/backoff policy;
  - HTTP/domain error mapping;
  - batch/upsert/posting helpers.
- **BREAKING**: выполнить Big-bang cutover в одном релизном окне:
  - одновременно переключить `odataops` (`create|update|delete|query`) и `pool.publication_odata` на worker `odata-core`;
  - отключить legacy OData transport path для `publication_odata` в Orchestrator runtime.
- Зафиксировать ownership publication transport и idempotency как contract-first требования:
  - OData side effects `pool.publication_odata` выполняются только в worker `odata-core`;
  - Orchestrator bridge path после cutover возвращает fail-closed код `POOL_RUNTIME_PUBLICATION_PATH_DISABLED` для `pool.publication_odata`.
- Сохранить доменные инварианты `pool-workflow-execution-core` (approval/state-machine/idempotency/diagnostics) без изменения публичного pools facade API.
- Зафиксировать обязательную telemetry-модель (retries, resend_count, latency/error labels) и release-gates для Big-bang.
- Удалить/деактивировать дублирующиеся transport-компоненты в рамках того же cutover.

## Impact
- Affected specs:
  - `worker-odata-transport-core` (new capability)
  - `pool-workflow-execution-core`
  - `pool-odata-publication` (контракт публикации должен остаться совместимым)
- Affected code (expected):
  - `go-services/worker/internal/odata/*`
  - `go-services/worker/internal/drivers/odataops/*`
  - `go-services/worker/internal/drivers/poolops/*`
  - `go-services/worker/internal/workflow/handlers/*`
  - `orchestrator/apps/intercompany_pools/publication.py`
  - `orchestrator/apps/intercompany_pools/pool_domain_steps.py`
  - `orchestrator/apps/api_internal/views_workflows.py`
  - `contracts/orchestrator-internal/openapi.yaml`
- Validation:
  - parity tests для `odataops` и `poolops` на общих retry/error semantics;
  - contract tests на `POOL_RUNTIME_PUBLICATION_PATH_DISABLED` и ownership enforcement;
  - release rehearsal для Big-bang cutover + rollback drill;
  - интеграционный сценарий pool run `500` на 3 организации с созданием документов;
  - регрессии generic CRUD (create/update/delete/query).

## Dependencies
- Разрешено только после стабилизации change `add-poolops-driver-workflow-runtime-fail-closed`.
- Требуется единое релизное окно (deployment freeze + rollback plan) для атомарного cutover.
- Cutover допускается только при зелёных gate-проверках: parity suite + staging rehearsal + rollback drill + compatibility preflight.

## Implementation Readiness
### Definition of Ready (DoR)
- Утверждён contract-diff для `POST /api/v2/internal/workflows/execute-pool-runtime-step`:
  - для `operation_type=pool.publication_odata` после cutover возвращается `409 Conflict`;
  - payload соответствует `ErrorResponse` (`error`, `code`, optional `details`) с `code=POOL_RUNTIME_PUBLICATION_PATH_DISABLED`.
- Зафиксирован источник истины для операторской диагностики публикации:
  - `PoolPublicationAttempt`/`pool_publication_attempts` остаётся каноническим read-model для `/api/v2/pools/runs/{run_id}/report`.
- Зафиксирован parity-baseline для старого/нового transport поведения:
  - generic CRUD (`create|update|delete|query`);
  - `pool.publication_odata` (`published|partial_success|failed`, diagnostics, idempotency).
- Подготовлены rollout artifacts: cutover checklist, rollback runbook, staging rehearsal plan.

### Definition of Done (DoD)
- Worker `odata-core` является единственным transport-owner для `odataops` и `pool.publication_odata`.
- Legacy publication OData transport в Orchestrator отключён в том же релизе.
- Bridge path для `pool.publication_odata` работает только в fail-closed режиме (`POOL_RUNTIME_PUBLICATION_PATH_DISABLED`).
- Публичный контракт pools facade не изменён:
  - структура `PoolRunReport` и publication diagnostics совместима с текущими клиентами.
- Пройдены все обязательные quality gates, зафиксированы артефакты rehearsal/rollback и post-cutover smoke.

## Quality Gates (Go/No-Go)
- `openspec validate refactor-shared-odata-core --strict --no-interactive` проходит без ошибок.
- Contract tests для fail-closed bridge path (`409` + `POOL_RUNTIME_PUBLICATION_PATH_DISABLED`) проходят.
- Compatibility preflight (`odata-compatibility-profile`) проходит для целевого окружения.
- Parity suite old/new transport не содержит критических расхождений по:
  - retry classification;
  - error mapping;
  - publication diagnostics/idempotency/status projection.
- Staging rehearsal и rollback drill завершены успешно в рамках единого release window rehearsal.

## Non-Goals
- Не меняем stream topology (`operations`/`workflows`) и queue routing.
- Не меняем публичный API pools facade.
- Не переносим всю pool domain state-machine логику в generic OData слой.
- Не переносим non-OData pool шаги (`pool.prepare_input`, `pool.distribution_calculation.*`, `pool.reconciliation_report`, `pool.approval_gate`) в этот change.
