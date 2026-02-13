## 0. Зависимости и перенос scope
- [x] 0.1 Зафиксировать prerequisite: foundation из `add-intercompany-pool-distribution-module` (catalog/data/contracts/UI baseline) доступен как входной baseline.
- [x] 0.2 Принять deferred execution scope из `add-intercompany-pool-distribution-module` и убрать дубли/расщепление ответственности между change-ами.
- [x] 0.3 Зафиксировать cross-reference между change-ами в proposal/design/tasks.

## 1. Spec и контрактная фиксация
- [ ] 1.1 Зафиксировать в OpenSpec, что execution runtime для `pools` = `workflows`.
- [ ] 1.2 Уточнить API-контракт `pools/runs`: явная связь с workflow run reference и статусной проекцией.
- [ ] 1.3 Зафиксировать migration/compatibility требования для исторических run-ов и audit.
- [ ] 1.4 Зафиксировать канонический status mapping `pool <-> workflow` без двусмысленностей.
- [ ] 1.5 Зафиксировать tenant boundary контракт (`pool_run.tenant_id == workflow_execution.tenant_id`).

## 2. Backend: execution-core интеграция
- [ ] 2.1 Реализовать compiler `PoolTemplate -> WorkflowTemplate/ExecutionPlan` с детерминированным mapping шагов.
- [ ] 2.2 Реализовать запуск `Pool Run` через workflow runtime (enqueue, lifecycle, retry policy, provenance).
- [ ] 2.3 Реализовать status projection из workflow run в pool-доменные статусы без потери диагностики.
- [ ] 2.4 Реализовать publication retry contract: `max_attempts_total=5`, retry только failed subset.
- [ ] 2.5 Зафиксировать queueing contract phase 1: `commands:worker:workflows`, `priority=normal`.

## 3. Backend: pools как domain facade
- [ ] 3.1 Сохранить `pools/*` API как фасад над unified execution core.
- [ ] 3.2 Сохранить доменную идемпотентность (`pool_id + period + direction + source_hash`) и прокинуть её в workflow idempotency/metadata.
- [ ] 3.3 Обеспечить, что publication service (OData) вызывается как step adapter внутри workflow, а не как отдельный orchestrator runtime.
- [ ] 3.4 Добавить provenance block в `/pools/runs*` (`workflow_run_id`, `workflow_status`, `execution_backend`, `retry_chain`).

## 4. Миграция и совместимость
- [ ] 4.1 Добавить миграцию/бекфилл связей `pool_run -> workflow_run` для существующих/переходных записей.
- [ ] 4.2 Обеспечить чтение historical runs/details/audit через единый view без регрессий UI/API.
- [ ] 4.3 Подготовить deprecation-plan для legacy execution path в `pools` (без немедленного удаления `workflows`).
- [ ] 4.4 Добавить tenant linkage/backfill для workflow execution записей, связанных с pools.

## 5. Frontend
- [ ] 5.1 Адаптировать `/pools/runs` и `/pools/templates` к unified status/provenance модели.
- [ ] 5.2 Показать прозрачный execution provenance (workflow run reference, step diagnostics) в pool UI.

## 6. Качество и валидация
- [ ] 6.1 Добавить unit/integration тесты на compiler, статусную проекцию, идемпотентность и retry.
- [ ] 6.2 Добавить API regression тесты на совместимость `pools/runs*`.
- [x] 6.3 Прогнать `openspec validate refactor-unify-pools-workflow-execution-core --strict --no-interactive`.
