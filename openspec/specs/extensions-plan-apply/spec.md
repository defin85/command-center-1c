# extensions-plan-apply Specification

## Purpose
TBD - created by archiving change add-tenancy-extensions-plan-apply. Update Purpose after archive.
## Requirements
### Requirement: Plan/apply для extensions с drift check
Система ДОЛЖНА (SHALL) поддерживать plan/apply для extensions операций с drift check.

#### Scenario: Selective apply set_flags применяет только выбранные флаги
- **GIVEN** оператор запускает plan для `capability="extensions.set_flags"` и передаёт `apply_mask` (например, `active=true`, `safe_mode=false`, `unsafe_action_protection=false`)
- **WHEN** оператор выполняет apply по этому plan
- **THEN** executor получает параметры только для выбранных флагов (в примере — только `active`)
- **AND** невыбранные флаги НЕ должны модифицироваться на таргет-базах

### Requirement: Tenant-scoped mapping для extensions inventory
Система ДОЛЖНА (SHALL) позволять tenant-admin настроить mapping нормализованного extensions snapshot в канонический `extensions_inventory`.

#### Scenario: Mapping применяется в preview
- **GIVEN** tenant A настроил mapping для `extensions_inventory`
- **WHEN** пользователь делает preview snapshot
- **THEN** результат отображается в каноническом формате и валидируется по schema, где `extensions[]` поддерживает поля:
  - `name` (обязательно)
  - `purpose` (опционально)
  - `is_active` (опционально)
  - `safe_mode` (опционально)
  - `unsafe_action_protection` (опционально)

### Requirement: Drift check для применения флагов
Система ДОЛЖНА (SHALL) выполнять drift check при применении policy флагов расширений.

#### Scenario: Планирование фиксирует preconditions
- **WHEN** пользователь делает plan для `extensions.set_flags` по списку баз
- **THEN** plan содержит preconditions по snapshot hash/updated_at, чтобы apply мог detect drift (изменение snapshots между plan и apply)

### Requirement: Plan set_flags принимает apply_mask
Система ДОЛЖНА (SHALL) принимать `apply_mask` в `POST /api/v2/extensions/plan/` для `capability="extensions.set_flags"`.

#### Scenario: apply_mask валидируется fail-closed
- **WHEN** пользователь делает plan для `extensions.set_flags` с `apply_mask`, где все флаги выключены
- **THEN** API возвращает ошибку валидации (400) и не создаёт plan

