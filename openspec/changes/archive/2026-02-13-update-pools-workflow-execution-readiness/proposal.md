# Change: Довести unified pools workflow execution до production-ready состояния

## Why
Реализация `pool-workflow-execution-core` покрывает основную архитектуру, но остаются критичные gaps между спецификацией, API-контрактом и runtime-поведением. Эти gaps блокируют безопасный rollout и повышают риск регрессий в multi-tenant окружении.

## What Changes
- Закрыть contract drift для `/api/v2/pools/runs*`:
  - зафиксировать source-of-truth цепочку `runtime serializers + extend_schema -> contracts/orchestrator/openapi.yaml -> generated client`;
  - синхронизировать `contracts/orchestrator/openapi.yaml` с фактическими endpoint-ами и payload-моделью;
  - добавить в контракт safe-команды `confirm-publication`/`abort-publication` с точными HTTP-кодами и canonical conflict payload;
  - синхронизировать контрактные поля `PoolRun`/provenance (`status_reason`, `approval_state`, `publication_step_state`, `terminal_reason`, `execution_backend`, `workflow_*`, `retry_chain`);
  - синхронизировать generated frontend client (`frontend/src/api/generated/**`) с обновлённым контрактом.
- Закрыть archive-sensitive preflight drift:
  - убрать зависимость preflight от неархивного пути change-папки;
  - ввести устойчивый source-of-truth для machine-readable артефактов (`execution-consumers-registry`, `odata-compatibility-profile`) и единый resolver для preflight/CI;
  - зафиксировать immutable policy для `profile_version`/`registry_version` в release gate.
- Довести provenance до канонической lineage-модели:
  - `workflow_run_id` = root execution chain id;
  - `workflow_status` = active attempt;
  - `retry_chain[]` как структурированный список попыток (`workflow_run_id`, `parent_workflow_run_id`, `attempt_number`, `attempt_kind`, `status`);
  - детерминированная сборка lineage для initial/retry попыток и historical runs.
- Довести diagnostics публикации до канонического payload:
  - фиксированные поля `payload_summary`, `http_error|transport_error`, `domain_error_code`, `domain_error_message`, `attempt_timestamp` и совместимость с текущими consumers;
  - политика data minimization/redaction (без утечки секретов, tenant-sensitive данных, сырых OData payload/stack traces).
- Зафиксировать workflow-only retry исполнение:
  - `POST /api/v2/pools/runs/{run_id}/retry` выполняется только через workflow runtime;
  - API endpoint возвращает `202 Accepted` и ссылку на workflow execution/operation вместо синхронного direct publish loop;
  - direct OData orchestration из API-path для retry исключается.
- Добавить anti-drift quality gates:
  - контрактные и интеграционные тесты на parity `runtime API <-> OpenAPI <-> generated client`;
  - preflight/CI проверки на корректный artifact resolution;
  - тесты lineage и canonical diagnostics на API-ответах;
  - CI-проверку breaking changes для `contracts/orchestrator/openapi.yaml`.

## Impact
- Affected specs:
  - `pool-workflow-execution-core`
- Affected code:
  - `orchestrator/apps/api_v2/views/intercompany_pools.py`
  - `orchestrator/apps/api_v2/urls.py`
  - `orchestrator/apps/intercompany_pools/{workflow_runtime.py,publication.py,safe_commands.py}`
  - `orchestrator/apps/templates/{workflow_decommission_preflight.py,odata_compatibility_preflight.py}`
  - `contracts/orchestrator/openapi.yaml`
  - `contracts/scripts/{validate-specs.sh,check-breaking-changes.sh}`
  - `frontend/src/api/generated/**`
  - `frontend/src/api/intercompanyPools.ts`
  - `frontend/src/pages/Pools/PoolRunsPage.tsx`
  - соответствующие backend/frontend тесты

## Non-Goals
- Введение нового runtime помимо `workflow_core`.
- Удаление legacy runtime в рамках этого change.
- Изменение бизнес-алгоритмов top-down/bottom-up.
