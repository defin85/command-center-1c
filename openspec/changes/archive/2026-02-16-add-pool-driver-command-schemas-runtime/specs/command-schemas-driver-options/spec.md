## ADDED Requirements
### Requirement: Command schemas MUST поддерживать driver `pool` для runtime шагов распределения
Система ДОЛЖНА (SHALL) поддерживать schema-driven driver `pool` с driver-level schema и набором command schemas для pool runtime pipeline.

Минимально обязательный набор `command_id`:
- `prepare_input`
- `distribution_calculation.top_down`
- `distribution_calculation.bottom_up`
- `reconciliation_report`
- `approval_gate`
- `publication_odata`

#### Scenario: Effective catalog возвращает driver `pool` и его команды
- **WHEN** оператор запрашивает effective command catalog
- **THEN** ответ содержит driver `pool`
- **AND** в `commands_by_id` присутствуют обязательные pool runtime command_id

### Requirement: Pool command params MUST валидироваться через command schema fail-closed
Система ДОЛЖНА (SHALL) валидировать `pool_driver` template params строго по `pool` command schema.

При несовпадении схемы система ДОЛЖНА (SHALL) отклонять сохранение template и запуск исполнения fail-closed.

#### Scenario: Неизвестный параметр pool команды отклоняется
- **GIVEN** template с `executor_kind=pool_driver` и `command_id=distribution_calculation.top_down`
- **WHEN** пользователь сохраняет template с параметром, отсутствующим в schema
- **THEN** система возвращает ошибку валидации
- **AND** template не публикуется
