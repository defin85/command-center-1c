## 1. Spec & Contracts
- [ ] 1.1 Добавить spec deltas в `command-schemas-driver-options`, `operation-templates`, `pool-workflow-execution-core`.
- [ ] 1.2 Зафиксировать contract для нового driver `pool` и executor kind `pool_driver`.
- [ ] 1.3 Обновить OpenAPI и generated clients для новых полей/enum (driver/executor).

## 2. Backend: command-schemas + template model
- [ ] 2.1 Добавить driver `pool` в base/effective command catalogs.
- [ ] 2.2 Добавить command schemas для обязательных pool runtime commands.
- [ ] 2.3 Реализовать валидацию template payload `pool_driver` по схеме выбранной команды.
- [ ] 2.4 Обновить normalize/validation pipeline executor payload для `pool_driver`.
- [ ] 2.5 Реализовать routing backend/adapter для `pool_driver` (schema-driven execution path).

## 3. Pool workflow integration
- [ ] 3.1 Обновить mapping pool workflow steps -> pool driver command templates.
- [ ] 3.2 Обновить компиляцию execution plan с provenance `driver=pool`, `command_id`.
- [ ] 3.3 Обеспечить fail-closed поведение при отсутствии command schema или template binding.

## 4. UI `/templates` и DX
- [ ] 4.1 Добавить поддержку `pool_driver` в template editor (`driver`, `command_id`, params form).
- [ ] 4.2 Добавить preview "что будет выполнено" для pool driver templates (argv/bindings или эквивалент execution plan preview).
- [ ] 4.3 Убедиться, что `sync from registry` корректно синхронизирует pool runtime template aliases на базе pool command catalog.

## 5. Tests & Validation
- [ ] 5.1 Backend тесты на загрузку/валидацию `pool` driver schema и command schemas.
- [ ] 5.2 Backend тесты на template create/update для `pool_driver` (валидные/невалидные params).
- [ ] 5.3 Backend тесты на pool workflow execution routing через schema-driven backend.
- [ ] 5.4 Frontend тесты template editor для `pool_driver`.
- [ ] 5.5 Прогнать `openspec validate add-pool-driver-command-schemas-runtime --strict --no-interactive`.
