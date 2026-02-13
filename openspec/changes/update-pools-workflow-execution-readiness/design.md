## Context
После `refactor-unify-pools-workflow-execution-core` ядро unified runtime внедрено, но production readiness блокируется несколькими системными расхождениями:
- runtime API и OpenAPI контракт расходятся;
- preflight читает machine-readable артефакты из неустойчивого пути `openspec/changes/<change-id>/...`, который исчезает после archive;
- provenance `retry_chain` не содержит структурного lineage;
- diagnostics публикации в API не полностью совпадает с каноническим набором полей;
- retry path в facade обходит workflow runtime и выполняет direct publication orchestration.
- generated frontend client отстаёт от runtime contract и не покрывает часть pools/runs surface.

## Goals / Non-Goals
- Goals:
  - Устранить drift между runtime, контрактом и spec.
  - Сделать preflight/archive path стабильным и предсказуемым.
  - Довести provenance/diagnostics до канонической модели.
  - Гарантировать workflow-only execution для retry.
  - Добавить anti-drift проверки в тестах и CI.
- Non-Goals:
  - Удаление legacy runtime.
  - Изменение domain-алгоритмов распределения.
  - Введение нового worker stream/lane.

## Decisions
- Decision: machine-readable source-of-truth артефакты capability переносятся в стабильный путь:
  - `openspec/specs/pool-workflow-execution-core/artifacts/execution-consumers-registry.yaml`
  - `openspec/specs/pool-workflow-execution-core/artifacts/execution-consumers-registry.schema.yaml`
  - `openspec/specs/pool-workflow-execution-core/artifacts/odata-compatibility-profile.yaml`
  - `openspec/specs/pool-workflow-execution-core/artifacts/odata-compatibility-profile.schema.yaml`
  - preflight/CI читают только этот путь как canonical.
- Decision: source-of-truth для pools/runs contract фиксируется как:
  - runtime serializers + `extend_schema` в `orchestrator/apps/api_v2/views/intercompany_pools.py`;
  - экспорт в `contracts/orchestrator/openapi.yaml` как versioned release artifact;
  - синхронная регенерация `frontend/src/api/generated/**` и fail при drift.
- Decision: OpenAPI parity становится release-gate:
  - safe-команды и все runtime-поля `PoolRun`/provenance обязаны присутствовать в `contracts/orchestrator/openapi.yaml`;
  - drift между runtime schema и контрактом считается блокирующим;
  - drift между контрактом и generated frontend client также считается блокирующим.
- Decision: provenance lineage приводится к структурной модели:
  - `workflow_run_id` в facade = root execution id;
  - `workflow_status` = active attempt status;
  - `retry_chain[]` = список попыток с parent linkage (`workflow_run_id`, `parent_workflow_run_id`, `attempt_number`, `attempt_kind`, `status`);
  - lineage хранится в runtime metadata детерминированно для initial/retry попыток и может быть восстановлен backfill-скриптом для historical unified runs.
- Decision: diagnostics публикации в API нормализуется до канонического payload:
  - обязательные поля `target_database_id`, `payload_summary`, `domain_error_code`, `domain_error_message`, `attempt_number`, `attempt_timestamp`;
  - одно из полей `http_error` или `transport_error` обязательно для failed-attempt;
  - совместимые alias-поля сохраняются только как transitional compatibility layer;
  - `payload_summary` и error details проходят redaction/data-minimization policy (без секретов, сырых payload и stack traces).
- Decision: retry endpoint facade выполняет orchestration только через workflow runtime:
  - `POST /api/v2/pools/runs/{run_id}/retry` создаёт/enqueue workflow execution для failed subset;
  - endpoint возвращает `202 Accepted` с accepted payload (`workflow_execution_id`, `operation_id`, `accepted=true`) вместо синхронного publish-summary;
  - direct OData invocation из API path запрещён;
  - итог retries наблюдается через run details/provenance, а не через синхронный direct publish loop;
  - при повторе с тем же `Idempotency-Key` возвращается детерминированный replay accepted-response без повторного enqueue.
- Decision: error/conflict envelope сохраняет tenant confidentiality:
  - cross-tenant и unknown run остаются неразличимыми по коду/форме ошибки;
  - payload ошибки не раскрывает tenant identifiers и чувствительные детали инфраструктуры.

## Architecture Invariants (Readiness Gate)
- Invariant 1: OpenAPI для `pools/runs*` и runtime serializers не расходятся по endpoint-ам/кодам/полям.
- Invariant 2: preflight не зависит от location конкретного archived change.
- Invariant 3: `retry_chain` для unified run всегда структурирован и содержит initial attempt.
- Invariant 4: diagnostics failed-attempt всегда включает канонические поля.
- Invariant 5: retry API path не вызывает OData клиент напрямую.
- Invariant 6: `POST /api/v2/pools/runs/{run_id}/retry` возвращает `202 Accepted` и execution reference, а не синхронный direct publish result.
- Invariant 7: generated frontend client для pools/runs синхронизирован с `contracts/orchestrator/openapi.yaml`.

## Migration Plan
1. Перенести profile/registry артефакты в `openspec/specs/pool-workflow-execution-core/artifacts/`.
2. Обновить preflight loaders и тесты на новые canonical paths.
3. Обновить runtime lineage/diagnostics serialization и backfill linkage для historical unified runs.
4. Перевести retry orchestration на workflow runtime, зафиксировать `202 Accepted` + failed-subset semantics.
5. Обновить OpenAPI контракт и generated frontend client в одной транзакции изменений.
6. Обновить frontend API types/UI для structured lineage и diagnostics.
7. Добавить parity/anti-drift тесты и CI-gates.

## Risks / Trade-offs
- Риск: изменение provenance/diagnostics формата может затронуть consumers.
  - Mitigation: transitional alias-поля + versioned contract update + regression tests.
- Риск: asynchronous retry через workflow runtime изменит ожидания API клиентов.
  - Mitigation: явный контракт endpoint semantics, UI messaging и migration notes.
- Риск: перенос artifact paths может сломать ad-hoc скрипты.
  - Mitigation: documented migration + preflight command updates + CI validation.
- Риск: backfill lineage для historical unified runs может дать неполную цепочку.
  - Mitigation: quality metric в backfill-отчёте + fallback маркер `lineage_partial=true` + ручная доочистка.
- Риск: усиленный anti-drift gate увеличит количество fail в CI на переходный период.
  - Mitigation: staged rollout gate (warn -> fail), но с фиксированной датой перехода в fail-hard режим.
