## 0. Зависимости и перенос scope
- [x] 0.1 Зафиксировать prerequisite: foundation из `add-intercompany-pool-distribution-module` (catalog/data/contracts/UI baseline) доступен как входной baseline.
- [x] 0.2 Принять deferred execution scope из `add-intercompany-pool-distribution-module` и убрать дубли/расщепление ответственности между change-ами.
- [x] 0.3 Зафиксировать cross-reference между change-ами в proposal/design/tasks.
- [x] 0.4 Зафиксировать anti-drift инварианты runtime state machine и правила синхронного обновления `proposal/design/tasks/spec`.

## 1. Spec и контрактная фиксация
- [ ] 1.1 Зафиксировать в OpenSpec, что execution runtime для `pools` = `workflows`.
- [ ] 1.2 Уточнить API-контракт `pools/runs`: явная связь с workflow run reference и статусной проекцией.
- [ ] 1.3 Зафиксировать migration/compatibility требования для исторических run-ов и audit.
- [ ] 1.4 Зафиксировать канонический status mapping `pool <-> workflow` без двусмысленностей.
- [ ] 1.5 Зафиксировать tenant boundary контракт (`pool_run.tenant_id == workflow_execution.tenant_id`).
- [ ] 1.6 Зафиксировать `safe/unsafe` approval gate как явный контракт (`confirm-publication` / `abort-publication`) без второго runtime.
- [ ] 1.7 Зафиксировать подстатусы `validated` через `status_reason` (`preparing`, `awaiting_approval`, `queued`) и явный `approval_state`.
- [ ] 1.8 Зафиксировать retry-контракт полностью: `max_attempts_total=5`, конфигурируемый интервал, cap 120 секунд.
- [ ] 1.9 Зафиксировать OData identity strategy (`GUID` primary, `ExternalRunKey` fallback) и канонический diagnostic payload.
- [ ] 1.10 Зафиксировать source-of-truth правило между change-ами и preflight-контракт decommission.
- [ ] 1.11 Зафиксировать API-контракт safe-команд (`POST /api/v2/pools/runs/{run_id}/confirm-publication`, `POST /api/v2/pools/runs/{run_id}/abort-publication`) с idempotency/error моделью и запретом `abort` после старта `publication_odata`.
- [ ] 1.12 Зафиксировать lineage-семантику provenance (`workflow_run_id` как root, `workflow_status` как active attempt, структура `retry_chain`, nullable `legacy_reference`).

## 2. Backend: execution-core интеграция
- [ ] 2.1 Реализовать compiler `PoolImportSchemaTemplate + run_context -> PoolExecutionPlan/WorkflowTemplate` с детерминированным mapping шагов.
- [ ] 2.2 Реализовать запуск `Pool Run` через workflow runtime (enqueue, lifecycle, retry policy, provenance).
- [ ] 2.3 Реализовать status projection из workflow run в pool-доменные статусы без потери диагностики.
- [ ] 2.4 Реализовать publication retry contract: `max_attempts_total=5`, retry только failed subset.
- [ ] 2.5 Зафиксировать queueing contract phase 1: `commands:worker:workflows`, `priority=normal`.
- [ ] 2.6 Реализовать approval gate в workflow graph (`safe`: ожидание confirm, `unsafe`: auto-confirm).
- [ ] 2.7 Добавить и применить поля `workflow_execution.tenant_id` и `workflow_execution.execution_consumer` с правилом обязательности для `pools`.
- [ ] 2.8 Реализовать validator/normalizer `retry_interval_seconds` с верхней границей 120 секунд.
- [ ] 2.9 Реализовать strategy-based resolver внешнего document identity в шаге `publication_odata`.
- [ ] 2.10 Реализовать safe-flow порядок шагов: pre-publish (`prepare_input`, `distribution_calculation`, `reconciliation_report`) до `approval_gate`, публикация только после confirm.
- [ ] 2.11 Реализовать `approval_state` lifecycle (`preparing -> awaiting_approval -> approved/not_required`) и детерминированную status projection для safe-flow.

## 3. Backend: pools как domain facade
- [ ] 3.1 Сохранить `pools/*` API как фасад над unified execution core.
- [ ] 3.2 Сохранить доменную идемпотентность (`pool_id + period + direction + source_hash`) и прокинуть её в workflow idempotency/metadata.
- [ ] 3.3 Обеспечить, что publication service (OData) вызывается как step adapter внутри workflow, а не как отдельный orchestrator runtime.
- [ ] 3.4 Добавить provenance block в `/pools/runs*` (`workflow_run_id`, `workflow_status`, `execution_backend`, `retry_chain`).
- [ ] 3.5 Добавить `status_reason` для статуса `validated` (`preparing`, `awaiting_approval`, `queued`) и команды фасада `confirm-publication`/`abort-publication`.
- [ ] 3.6 Зафиксировать nullable/legacy правила provenance для historical run (`execution_backend=legacy_pool_runtime`).
- [ ] 3.7 Вернуть канонический набор полей diagnostics по попыткам публикации в API facade.
- [ ] 3.8 Поддержать compatibility `workflow_binding` на import templates как optional compiler hint без отдельного runtime-смысла.

## 4. Миграция и совместимость
- [ ] 4.1 Добавить миграцию/бекфилл связей `pool_run -> workflow_run` для существующих/переходных записей.
- [ ] 4.2 Обеспечить чтение historical runs/details/audit через единый view без регрессий UI/API.
- [ ] 4.3 Подготовить deprecation-plan для legacy execution path в `pools` (без немедленного удаления `workflows`).
- [ ] 4.4 Добавить tenant linkage/backfill для workflow execution записей, связанных с pools.
- [ ] 4.5 Добавить `execution_consumers_registry` и preflight-проверку готовности к decommission `workflows`.
- [ ] 4.6 Зафиксировать переходный режим для non-pools consumers с `tenant_id=null` до их миграции.

## 5. Frontend
- [ ] 5.1 Адаптировать `/pools/runs` и `/pools/templates` к unified status/provenance модели.
- [ ] 5.2 Показать прозрачный execution provenance (workflow run reference, step diagnostics) в pool UI.
- [ ] 5.3 Добавить UI для `safe` режима: `preparing`/`awaiting_approval`, действия `confirm-publication` и `abort-publication`.

## 6. Качество и валидация
- [ ] 6.1 Добавить unit/integration тесты на compiler, статусную проекцию, идемпотентность и retry.
- [ ] 6.2 Добавить API regression тесты на совместимость `pools/runs*`.
- [ ] 6.3 Добавить тесты `safe/unsafe` approval gate, `approval_state` и `status_reason` проекции.
- [ ] 6.4 Добавить тесты retry interval clamp (<=120), OData identity strategy и diagnostic fields.
- [ ] 6.5 Добавить тесты decommission preflight (`Go/No-Go`) на базе `execution_consumers_registry`.
- [ ] 6.6 Добавить API/интеграционные тесты на idempotency команд confirm/abort и provenance retry-lineage.
- [x] 6.7 Прогнать `openspec validate refactor-unify-pools-workflow-execution-core --strict --no-interactive`.
- [x] 6.8 Выполнить anti-drift self-check: подтвердить, что инварианты state machine согласованы между `proposal/design/spec/tasks`.
