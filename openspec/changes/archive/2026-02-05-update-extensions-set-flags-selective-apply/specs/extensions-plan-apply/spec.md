## MODIFIED Requirements

### Requirement: Plan/apply для extensions с drift check
Система ДОЛЖНА (SHALL) поддерживать plan/apply для extensions операций с drift check.

#### Scenario: Selective apply set_flags применяет только выбранные флаги
- **GIVEN** оператор запускает plan для `capability="extensions.set_flags"` и передаёт `apply_mask` (например, `active=true`, `safe_mode=false`, `unsafe_action_protection=false`)
- **WHEN** оператор выполняет apply по этому plan
- **THEN** executor получает параметры только для выбранных флагов (в примере — только `active`)
- **AND** невыбранные флаги НЕ должны модифицироваться на таргет-базах

## ADDED Requirements

### Requirement: Plan set_flags принимает apply_mask
Система ДОЛЖНА (SHALL) принимать `apply_mask` в `POST /api/v2/extensions/plan/` для `capability="extensions.set_flags"`.

#### Scenario: apply_mask валидируется fail-closed
- **WHEN** пользователь делает plan для `extensions.set_flags` с `apply_mask`, где все флаги выключены
- **THEN** API возвращает ошибку валидации (400) и не создаёт plan

