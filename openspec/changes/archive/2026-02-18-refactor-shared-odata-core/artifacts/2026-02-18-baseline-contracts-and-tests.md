# Baseline: contracts and tests for refactor-shared-odata-core

Дата фиксации baseline: 2026-02-18.

## 1) PoolRunReport contract baseline

Источники текущего контракта report endpoint:
- Формирование payload: `orchestrator/apps/api_v2/views/intercompany_pools.py:2534`
- Состав payload report: `orchestrator/apps/api_v2/views/intercompany_pools.py:2566`
- Сериализация publication attempts: `orchestrator/apps/api_v2/views/intercompany_pools.py:1141`
- Frontend typing (`PoolRunReport`, `PoolPublicationAttemptDiagnostics`): `frontend/src/api/intercompanyPools.ts:89`, `frontend/src/api/intercompanyPools.ts:152`

Зафиксированный baseline report fields:
- `run`
- `publication_attempts`
- `validation_summary`
- `publication_summary`
- `diagnostics`
- `attempts_by_status`

Зафиксированный baseline diagnostics attempt fields (канонические + alias):
- `target_database_id`, `attempt_number`, `attempt_timestamp`, `status`, `entity_name`, `documents_count`
- `payload_summary`, `http_error`, `transport_error`
- `domain_error_code`, `domain_error_message`
- `external_document_identity`, `identity_strategy`, `publication_identity_strategy`
- `posted`, `http_status`, `error_code`, `error_message`
- `request_summary`, `response_summary`, `started_at`, `finished_at`, `created_at`

## 2) Internal bridge endpoint baseline

Источники контракта bridge endpoint:
- OpenAPI path: `contracts/orchestrator-internal/openapi.yaml:502`
- 409 conflict examples: `contracts/orchestrator-internal/openapi.yaml:531`
- ErrorResponse schema: `contracts/orchestrator-internal/openapi.yaml:1791`

Зафиксированный baseline response matrix для
`POST /api/v2/internal/workflows/execute-pool-runtime-step`:
- `200`, `400`, `401`, `404`, `409`, `429`, `500`
- `409` сейчас документирует коды:
  - `POOL_RUNTIME_CONTEXT_MISMATCH`
  - `IDEMPOTENCY_KEY_CONFLICT`

## 3) Publication diagnostics/read-model baseline

Источник истины report-представления:
- `PoolPublicationAttempt` читается в report endpoint: `orchestrator/apps/api_v2/views/intercompany_pools.py:2555`
- Attempts сериализуются через `_serialize_attempt`: `orchestrator/apps/api_v2/views/intercompany_pools.py:1141`

Точки записи attempts (текущая реализация publication path в orchestrator):
- Success attempt write: `orchestrator/apps/intercompany_pools/publication.py:269`
- Failed attempt write: `orchestrator/apps/intercompany_pools/publication.py:455`

## 4) Baseline tests (contract + diagnostics)

Bridge/OpenAPI contract tests:
- `orchestrator/apps/api_internal/tests/test_pool_runtime_bridge_openapi_contract.py:28`
- `orchestrator/apps/api_internal/tests/test_views_workflows.py:530`
- `orchestrator/apps/api_internal/tests/test_views_workflows.py:646`
- `orchestrator/apps/api_internal/tests/test_views_workflows.py:782`
- `orchestrator/apps/api_internal/tests/test_views_workflows.py:825`

Pools report/diagnostics tests:
- `orchestrator/apps/api_v2/tests/test_intercompany_pool_runs.py:865`
- `orchestrator/apps/api_v2/tests/test_intercompany_pool_runs.py:953`
- `orchestrator/apps/api_v2/tests/test_intercompany_pool_runs.py:997`
- `orchestrator/apps/api_v2/tests/test_intercompany_pool_runs.py:2628`
- `orchestrator/apps/api_v2/tests/test_pool_runs_openapi_contract_parity.py:126`

Publication retry/attempt semantics tests:
- `orchestrator/apps/intercompany_pools/tests/test_publication.py:96`
- `orchestrator/apps/intercompany_pools/tests/test_publication.py:152`
- `orchestrator/apps/intercompany_pools/tests/test_publication.py:191`
- `orchestrator/apps/intercompany_pools/tests/test_publication.py:348`

## 5) Parity comparison anchors for migration

Для сравнения old/new transport behavior в рамках change использовать baseline anchors:
- Report payload shape и attempt diagnostics fields (раздел 1)
- Bridge status matrix + ErrorResponse/409 semantics (раздел 2)
- Read-model ownership (`PoolPublicationAttempt`) и attempt write/read path (раздел 3)
- Существующие contract/integration/regression tests (раздел 4)
