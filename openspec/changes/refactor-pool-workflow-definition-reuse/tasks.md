## 1. Spec & Contracts
- [x] 1.1 Зафиксировать в spec разделение `PoolWorkflowDefinition` и `PoolExecutionPlanSnapshot`.
- [x] 1.2 Обновить требования deterministic compile: `definition_key` без `period_*` и `run_input`.
- [x] 1.3 Зафиксировать read-only отображение system-managed pool runtime templates в `/templates`.

## 2. Backend: definition reuse
- [x] 2.1 Обновить compiler: вычислять `definition_key` только из структурных признаков процесса.
- [x] 2.2 Обновить runtime: резолвить/создавать workflow template по `definition_key`, а не по run-specific fingerprint.
- [x] 2.3 Сохранять immutable execution snapshot (period/run_input/lineage) на каждый execution.
- [x] 2.4 Обеспечить retry-семантику: тот же definition, новый execution snapshot.
- [x] 2.5 Добавить/обновить миграционные шаги для совместимости historical run-ов и legacy template linkage.

## 3. API/UI: templates visibility
- [x] 3.1 Обновить `/templates` list: показывать `pool.*` system-managed entries с read-only indicator.
- [x] 3.2 Запретить edit/delete controls для system-managed pool runtime templates в UI.
- [x] 3.3 Проверить, что публичный write-path для `pool.*` aliases остаётся fail-closed.

## 4. Tests & Validation
- [x] 4.1 Backend тесты на reuse definition при разных `period/run_input` и новый definition при структурном изменении.
- [x] 4.2 Backend тесты на immutable execution snapshot и retry lineage.
- [x] 4.3 Frontend/API тесты на отображение и read-only поведение system-managed pool templates.
- [x] 4.4 Прогнать `openspec validate refactor-pool-workflow-definition-reuse --strict --no-interactive`.
