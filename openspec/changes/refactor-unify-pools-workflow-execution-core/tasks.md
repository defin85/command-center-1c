## 0. Зависимости и перенос scope
- [x] 0.1 Зафиксировать prerequisite: foundation из `add-intercompany-pool-distribution-module` (catalog/data/contracts/UI baseline) доступен как входной baseline.
- [x] 0.2 Принять deferred execution scope из `add-intercompany-pool-distribution-module` и убрать дубли/расщепление ответственности между change-ами.
- [x] 0.3 Зафиксировать cross-reference между change-ами в proposal/design/tasks.
- [x] 0.4 Зафиксировать anti-drift инварианты runtime state machine и правила синхронного обновления `proposal/design/tasks/spec`.
- [x] 0.5 Зафиксировать dependency-gate: OData compatibility profile (endpoint/posting fields) обязателен до production rollout unified publication.

## 1. Spec и контрактная фиксация
- [x] 1.1 Зафиксировать в OpenSpec, что execution runtime для `pools` = `workflows`.
- [x] 1.2 Уточнить API-контракт `pools/runs`: явная связь с workflow run reference и статусной проекцией.
- [x] 1.3 Зафиксировать migration/compatibility требования для исторических run-ов и audit.
- [x] 1.4 Зафиксировать канонический status mapping `pool <-> workflow` без двусмысленностей.
- [x] 1.5 Зафиксировать tenant boundary контракт (`pool_run.tenant_id == workflow_execution.tenant_id`).
- [x] 1.6 Зафиксировать `safe/unsafe` approval gate как явный контракт (`confirm-publication` / `abort-publication`) без второго runtime.
- [x] 1.7 Зафиксировать подстатусы `validated` через `status_reason` (`preparing`, `awaiting_approval`, `queued`) и явный `approval_state`.
- [x] 1.8 Зафиксировать retry-контракт полностью: `max_attempts_total=5`, конфигурируемый интервал, cap 120 секунд.
- [x] 1.9 Зафиксировать OData identity strategy (`GUID` primary, `ExternalRunKey` fallback) и канонический diagnostic payload.
- [x] 1.10 Зафиксировать source-of-truth правило между change-ами и preflight-контракт decommission.
- [x] 1.11 Зафиксировать API-контракт safe-команд (`POST /api/v2/pools/runs/{run_id}/confirm-publication`, `POST /api/v2/pools/runs/{run_id}/abort-publication`) с idempotency/error моделью, safe-only применимостью и запретом `abort` после старта `publication_odata`.
- [x] 1.12 Зафиксировать lineage-семантику provenance (`workflow_run_id` как root, `workflow_status` как active attempt, структура `retry_chain`, nullable `legacy_reference`).
- [x] 1.13 Зафиксировать state-matrix `confirm/abort` по всем ключевым состояниям (`approval_state` + facade-status: `validated/*`, `publishing`, terminal) без implicit интерпретаций.
- [x] 1.14 Зафиксировать `approval_state` как runtime source-of-truth и обязательное поле unified API details.
- [x] 1.15 Зафиксировать явные HTTP response-коды safe-команд (`400`, `202`, `200`, `409`) и канонический error payload (`error_code`, `error_message`, `conflict_reason`, `retryable`, `run_id`).
- [x] 1.16 Зафиксировать preflight-gate совместимости `compatibility mode` целевой ИБ и media-type policy из OData profile (legacy `<=8.3.7` требует отдельной approved записи).
- [x] 1.17 Зафиксировать приоритет projection-сигналов (`approval_state`, `approved_at`, `publication_odata started/not started`) над `workflow.status`.
- [x] 1.18 Зафиксировать fail-closed tenant confidentiality: cross-tenant и unknown `run_id` неразличимы во внешнем API (`404 RUN_NOT_FOUND`).
- [x] 1.19 Зафиксировать command-level idempotency safe-команд через обязательный `Idempotency-Key` и conflict-case `idempotency_key_reused`.
- [x] 1.20 Зафиксировать machine-readable source-of-truth артефакты: `execution-consumers-registry.yaml` + schema и `odata-compatibility-profile.yaml` + schema.
- [x] 1.21 Зафиксировать dual-write/dual-read cutover и rollback criteria/runbook в migration-контракте.
- [x] 1.22 Зафиксировать выбор Variant A (transactional command log + transactional outbox + single-winner CAS) как обязательную архитектуру safe-команд и cutover-атомарности.

## 2. Backend: execution-core интеграция
- [x] 2.1 Реализовать compiler `PoolImportSchemaTemplate + run_context -> PoolExecutionPlan/WorkflowTemplate` с детерминированным mapping шагов.
- [x] 2.2 Реализовать запуск `Pool Run` через workflow runtime (enqueue, lifecycle, retry policy, provenance).
- [x] 2.3 Реализовать status projection из workflow run в pool-доменные статусы без потери диагностики.
- [x] 2.4 Реализовать publication retry contract: `max_attempts_total=5`, retry только failed subset.
- [x] 2.5 Зафиксировать queueing contract phase 1: `commands:worker:workflows`, `priority=normal`.
- [x] 2.6 Реализовать approval gate в workflow graph (`safe`: ожидание confirm, `unsafe`: auto-confirm).
- [x] 2.7 Добавить и применить поля `workflow_execution.tenant_id` и `workflow_execution.execution_consumer` с правилом обязательности для `pools`.
- [x] 2.8 Реализовать validator/normalizer `retry_interval_seconds` с верхней границей 120 секунд.
- [x] 2.9 Реализовать strategy-based resolver внешнего document identity в шаге `publication_odata`.
- [x] 2.10 Реализовать safe-flow порядок шагов: pre-publish (`prepare_input`, `distribution_calculation`, `reconciliation_report`) до `approval_gate`, публикация только после confirm.
- [x] 2.11 Реализовать `approval_state` lifecycle (`preparing -> awaiting_approval -> approved/not_required`) и детерминированную status projection для safe-flow.
- [x] 2.12 Реализовать и хранить `publication_step_state` в runtime metadata для детерминированной проекции `validated/queued -> publishing`.
- [x] 2.13 Реализовать таблицу `pool_run_command_log` для `Idempotency-Key` (scope `(run_id, command_type, key)`, deterministic replay, response snapshot, TTL/retention).
- [x] 2.14 Реализовать таблицу `pool_run_command_outbox` и dispatcher в `commands:worker:workflows` (at-least-once + idempotent republish + retry/backoff).
- [x] 2.15 Реализовать single-winner CAS для гонки `confirm-publication` vs `abort-publication` на одном run без duplicate side effects.

## 3. Backend: pools как domain facade
- [x] 3.1 Сохранить `pools/*` API как фасад над unified execution core.
- [x] 3.2 Сохранить доменную идемпотентность (`pool_id + period + direction + source_hash`) и прокинуть её в workflow idempotency/metadata.
- [x] 3.3 Обеспечить, что publication service (OData) вызывается как step adapter внутри workflow, а не как отдельный orchestrator runtime.
- [x] 3.4 Добавить provenance block в `/pools/runs*` (`workflow_run_id`, `workflow_status`, `execution_backend`, `retry_chain`).
- [x] 3.5 Добавить `status_reason` для статуса `validated` (`preparing`, `awaiting_approval`, `queued`) и команды фасада `confirm-publication`/`abort-publication`.
- [x] 3.6 Зафиксировать nullable/legacy правила provenance для historical run (`execution_backend=legacy_pool_runtime`).
- [x] 3.7 Вернуть канонический набор полей diagnostics по попыткам публикации в API facade.
- [x] 3.8 Поддержать compatibility `workflow_binding` на import templates как optional compiler hint без отдельного runtime-смысла.
- [x] 3.9 Добавить в API details поля `approval_state` и `terminal_reason` для unified execution с nullable-совместимостью для legacy.
- [x] 3.10 Обеспечить fail-closed поведение facade API: cross-tenant/unknown `run_id` возвращает одинаковый `404 RUN_NOT_FOUND` без утечки причины.

## 4. Миграция и совместимость
- [x] 4.1 Добавить миграцию/бекфилл связей `pool_run -> workflow_run` для существующих/переходных записей.
- [x] 4.2 Обеспечить чтение historical runs/details/audit через единый view без регрессий UI/API.
- [x] 4.3 Подготовить deprecation-plan для legacy execution path в `pools` (без немедленного удаления `workflows`).
- [x] 4.4 Добавить tenant linkage/backfill для workflow execution записей, связанных с pools.
- [x] 4.5 Добавить `execution-consumers-registry.yaml` (+ `execution-consumers-registry.schema.yaml`) и preflight-проверку готовности к decommission `workflows`.
- [x] 4.6 Зафиксировать переходный режим для non-pools consumers с `tenant_id=null` до их миграции.
- [ ] 4.7 Поддерживать и версионировать `odata-compatibility-profile.yaml` (+ `odata-compatibility-profile.schema.yaml`) как prerequisite rollout.
- [ ] 4.8 Внедрить dual-write/dual-read cutover-план и зафиксировать rollback criteria/runbook (SLO, tenant boundary, projection drift).
- [ ] 4.9 Зафиксировать и внедрить операционные SLI для Variant A (`command_log write errors`, `outbox lag`, `dispatch retry saturation`) как rollback trigger.

## 5. Frontend
- [ ] 5.1 Адаптировать `/pools/runs` и `/pools/templates` к unified status/provenance модели.
- [ ] 5.2 Показать прозрачный execution provenance (workflow run reference, step diagnostics) в pool UI.
- [ ] 5.3 Добавить UI для `safe` режима: `preparing`/`awaiting_approval`, действия `confirm-publication` и `abort-publication`.

## 6. Качество и валидация
- [ ] 6.1 Добавить unit/integration тесты на compiler, статусную проекцию, идемпотентность и retry.
- [ ] 6.2 Добавить API regression тесты на совместимость `pools/runs*`.
- [ ] 6.3 Добавить тесты `safe/unsafe` approval gate, `approval_state` и `status_reason` проекции.
- [ ] 6.4 Добавить тесты retry interval clamp (<=120), OData identity strategy и diagnostic fields.
- [ ] 6.5 Добавить тесты decommission preflight (`Go/No-Go`) на базе `execution-consumers-registry.yaml`.
- [ ] 6.6 Добавить API/интеграционные тесты на idempotency команд confirm/abort и provenance retry-lineage.
- [x] 6.7 Прогнать `openspec validate refactor-unify-pools-workflow-execution-core --strict --no-interactive`.
- [x] 6.8 Выполнить anti-drift self-check: подтвердить, что инварианты state machine согласованы между `proposal/design/spec/tasks`.
- [ ] 6.9 Добавить контрактные тесты command state-matrix (`confirm/abort`: `400|202|200|409`) и idempotent-replay кейса `aborted_by_operator`.
- [ ] 6.10 Добавить API contract-тесты на error payload safe-команд (`error_code`, `error_message`, `conflict_reason`, `retryable`, `run_id`) и точные HTTP-коды (`400|202|200|409`).
- [ ] 6.11 Добавить preflight-тесты на блокировку rollout при несовместимости media-type policy profile и compatibility mode (`<=8.3.7` без legacy entry).
- [ ] 6.12 Добавить security-тесты на неразличимость ответов для unknown/cross-tenant `run_id` (`404 RUN_NOT_FOUND`).
- [ ] 6.13 Добавить интеграционные тесты `Idempotency-Key` для safe-команд (deterministic replay + `idempotency_key_reused`).
- [ ] 6.14 Добавить CI-проверки schema-валидации для `execution-consumers-registry.yaml` и `odata-compatibility-profile.yaml`.
- [ ] 6.15 Добавить интеграционные тесты Variant A на атомарность `command_log + outbox` (нет enqueue без committed command outcome).
- [ ] 6.16 Добавить race-тесты `confirm` vs `abort` на single-winner CAS и отсутствие duplicate enqueue/cancel side effects.
