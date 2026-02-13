## 0. Scope и dependency-gates
- [x] 0.1 Зафиксировать dependency на `refactor-orchestrator-openapi-modularization`: контрактные правки pools/runs выполняются в совместимом формате OpenAPI.
- [x] 0.2 Подтвердить критерии готовности: закрыты contract drift, archive-sensitive preflight drift, provenance lineage gap, diagnostics gap, retry-runtime gap.
- [x] 0.3 Зафиксировать source-of-truth цепочку для pools/runs: `runtime serializers + extend_schema -> contracts/orchestrator/openapi.yaml -> frontend/src/api/generated/**`.

## 1. Source-of-truth артефакты и preflight
- [x] 1.1 Перенести machine-readable артефакты в стабильный путь capability:
  - `openspec/specs/pool-workflow-execution-core/artifacts/execution-consumers-registry.yaml`
  - `openspec/specs/pool-workflow-execution-core/artifacts/execution-consumers-registry.schema.yaml`
  - `openspec/specs/pool-workflow-execution-core/artifacts/odata-compatibility-profile.yaml`
  - `openspec/specs/pool-workflow-execution-core/artifacts/odata-compatibility-profile.schema.yaml`
- [x] 1.2 Ввести единый resolver artifact-путей для preflight/CI (без хардкода `openspec/changes/<id>/...` и без зависимости от архивных датированных путей).
- [x] 1.3 Обновить `workflow_decommission_preflight.py` и `odata_compatibility_preflight.py` на использование единого resolver.
- [x] 1.4 Добавить тесты preflight на archive-safe поведение и отрицательный кейс (если артефакт доступен только в archived change path, preflight должен падать).
- [x] 1.5 Добавить CI-валидацию schema для новых artifact paths и immutable-проверку `profile_version/registry_version` в release pipeline.

## 2. API/OpenAPI contract parity
- [x] 2.1 Синхронизировать OpenAPI paths для safe-команд:
  - `POST /api/v2/pools/runs/{run_id}/confirm-publication/`
  - `POST /api/v2/pools/runs/{run_id}/abort-publication/`
  - точные response-коды `400|200|202|404|409`.
- [x] 2.2 Синхронизировать `PoolRun` schema в OpenAPI с runtime payload (`status_reason`, `workflow_execution_id`, `workflow_status`, `approval_state`, `publication_step_state`, `terminal_reason`, `execution_backend`, `provenance`).
- [x] 2.3 Синхронизировать OpenAPI schema для provenance с объектной `retry_chain[]` lineage-моделью и root/active semantics.
- [x] 2.4 Синхронизировать OpenAPI schema для `publication_attempts[]` с canonical diagnostics payload и transitional alias-полями.
- [x] 2.5 Добавить contract-тест(ы) parity `drf-spectacular/runtime serializers -> contracts/orchestrator/openapi.yaml`.
- [x] 2.6 Добавить проверку parity `contracts/orchestrator/openapi.yaml -> frontend/src/api/generated/**` и обновить generated client.
- [x] 2.7 Расширить `contracts/scripts/check-breaking-changes.sh` на `contracts/orchestrator/openapi.yaml` с fail-fast при breaking diff.

## 3. Runtime hardening: lineage, diagnostics, retry path
- [x] 3.1 Реализовать канонический provenance lineage для unified runs:
  - `workflow_run_id` как root execution id;
  - `workflow_status` как active attempt status;
  - `retry_chain[]` с полями `workflow_run_id`, `parent_workflow_run_id`, `attempt_number`, `attempt_kind`, `status`.
- [x] 3.2 Добавить/обновить runtime metadata и linkage так, чтобы lineage собирался детерминированно для initial и retry попыток (включая backfill historical unified runs).
- [x] 3.3 Довести serialization `publication_attempts[]` до канонических полей diagnostics (`payload_summary`, `http_error|transport_error`, `domain_error_code`, `domain_error_message`, `attempt_timestamp`), сохранив совместимость legacy consumers через transitional alias-поля.
- [x] 3.4 Ввести redaction/data-minimization policy для diagnostics и error payload (без утечки секретов, tenant-sensitive данных и сырых OData/traceback деталей).
- [x] 3.5 Перевести `POST /api/v2/pools/runs/{run_id}/retry` на workflow-only execution path (без direct OData orchestration из API path) и `202 Accepted` семантику ответа.
- [x] 3.6 Гарантировать retry только для failed subset в новом workflow retry path без повтора already successful targets.
- [x] 3.7 Гарантировать idempotent replay retry-запроса (при повторе `Idempotency-Key` возвращается детерминированный accepted response без дублирующего enqueue).

## 4. Frontend и typed client
- [x] 4.1 Обновить `frontend/src/api/intercompanyPools.ts` под объектную `retry_chain[]`, `202 Accepted` retry response и канонический diagnostics payload.
- [x] 4.2 Обновить `frontend/src/api/generated/**` и адаптеры вызовов pools/runs под новые safe/retry контракты.
- [x] 4.3 Обновить `PoolRunsPage` для отображения lineage (root/active attempt, attempt kind/number/status) и новых diagnostics полей.
- [x] 4.4 Обеспечить backward-compatible рендер historical/legacy runs (nullable workflow-поля, пустая цепочка, legacy alias diagnostics).

## 5. Тесты, anti-drift и валидация
- [x] 5.1 Добавить backend API/интеграционные тесты на structured lineage, parent-linkage, root/active semantics и deterministic ordering `retry_chain`.
- [x] 5.2 Добавить тесты на `202 Accepted` и idempotent replay семантику `POST /api/v2/pools/runs/{run_id}/retry`.
- [x] 5.3 Добавить тесты на запрет direct OData вызова из retry API path.
- [x] 5.4 Добавить тесты на полноту canonical diagnostics payload и redaction policy в `GET /api/v2/pools/runs/{run_id}`.
- [x] 5.5 Добавить тесты на OpenAPI parity для safe-команд, retry semantics и `PoolRun`/`publication_attempts` schema.
- [x] 5.6 Добавить frontend тесты на рендер structured lineage и canonical diagnostics + backward compatibility для legacy runs.
- [x] 5.7 Выполнить `openspec validate update-pools-workflow-execution-readiness --strict --no-interactive`.
