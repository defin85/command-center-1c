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

#### Scenario: apply_mask может быть задан preset-ом action
- **GIVEN** `POST /api/v2/extensions/plan/` вызывается для `extensions.set_flags`
- **AND** `apply_mask` отсутствует в request
- **AND** выбранный action содержит preset mask (`executor.fixed.apply_mask`)
- **THEN** effective `apply_mask` берётся из action preset

### Requirement: Детерминированный выбор action через action_id
Система ДОЛЖНА (SHALL) поддерживать выбор конкретного extensions action для plan/apply через `action_id`, а не только через `capability`.

#### Scenario: action_id выбирает конкретный action при нескольких candidates по capability
- **GIVEN** в `operation_exposure(surface="action_catalog")` есть 3 actions с `capability="extensions.set_flags"`
- **WHEN** UI делает `POST /api/v2/extensions/plan/` с `action_id`, указывающим на один из них
- **THEN** backend строит plan на основе executor выбранного action

#### Scenario: capability без action_id возвращает ambiguity
- **GIVEN** в `operation_exposure(surface="action_catalog")` есть 2+ actions с `capability="extensions.set_flags"`
- **WHEN** UI делает `POST /api/v2/extensions/plan/` без `action_id`, но с `capability="extensions.set_flags"`
- **THEN** backend возвращает `HTTP 400` с кодом ошибки ambiguity (например `AMBIGUOUS_ACTION`)

### Requirement: Plan/apply MUST резолвить extensions actions из unified exposure
Система ДОЛЖНА (SHALL) при `POST /api/v2/extensions/plan/` и `POST /api/v2/extensions/apply/` резолвить action только через published `operation_exposure(surface="action_catalog")`.

#### Scenario: action_id выбирает published exposure в unified store
- **GIVEN** запрос содержит `action_id`
- **AND** в unified store есть published exposure с таким alias
- **WHEN** backend строит plan
- **THEN** используется executor из связанного `operation_definition`
- **AND** capability/preset/binding берутся из exposure-level данных

### Requirement: `extensions.set_flags` MUST использовать unified target binding contract
Система ДОЛЖНА (SHALL) для `extensions.set_flags` подставлять `extension_name` только через валидный binding, сохранённый в unified exposure, и завершать запрос `CONFIGURATION_ERROR` при невалидном binding до preview/execute.

#### Scenario: exposure invalid по target binding
- **GIVEN** action exposure для `extensions.set_flags` имеет невалидный или отсутствующий binding
- **WHEN** вызывается `POST /api/v2/extensions/plan/`
- **THEN** backend возвращает `HTTP 400` с `CONFIGURATION_ERROR`
- **AND** запрос останавливается до вызова preview/execute слоя

#### Scenario: `extension_name` подставляется в bound param до preview/execute
- **GIVEN** exposure `extensions.set_flags` содержит валидный `target_binding.extension_name_param`
- **AND** request содержит `extension_name`
- **WHEN** вызывается `POST /api/v2/extensions/plan/`
- **THEN** backend подставляет `extension_name` в `executor.params[bound_param]` до preview/execute
- **AND** backend НЕ выполняет неявный token-based guess mapping по `$extension_name`

