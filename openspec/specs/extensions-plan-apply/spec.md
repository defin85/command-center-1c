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
Система ДОЛЖНА (SHALL) принимать `apply_mask` в `POST /api/v2/extensions/plan/` для `capability="extensions.set_flags"` только из runtime request/input и НЕ ДОЛЖНА (SHALL NOT) использовать capability/action preset как fallback.

#### Scenario: apply_mask обязателен и берётся только из request
- **GIVEN** вызывается `POST /api/v2/extensions/plan/` для `extensions.set_flags`
- **WHEN** в request отсутствует `apply_mask`
- **THEN** backend возвращает `HTTP 400` с `VALIDATION_ERROR`
- **AND** plan не создаётся

#### Scenario: preset apply_mask в action игнорируется и запрещён
- **GIVEN** action `extensions.set_flags` содержит `executor.fixed.apply_mask` или exposure-level `capability_config.apply_mask`
- **WHEN** вызывается `POST /api/v2/extensions/plan/`
- **THEN** backend не использует этот preset как runtime source
- **AND** backend возвращает `CONFIGURATION_ERROR` до preview/execute

### Requirement: Детерминированный выбор action через action_id
Система ДОЛЖНА (SHALL) требовать `action_id` для `extensions.set_flags` и НЕ ДОЛЖНА (SHALL NOT) выполнять неявный выбор action только по `capability`.

#### Scenario: Отсутствует action_id для set_flags
- **GIVEN** request для `extensions.set_flags` без `action_id`
- **WHEN** вызывается `POST /api/v2/extensions/plan/`
- **THEN** backend возвращает `HTTP 400` с `MISSING_PARAMETER` (action_id is required)
- **AND** plan не создаётся

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

### Requirement: `extensions.set_flags` MUST использовать runtime `flags_values` как единственный источник значений
Система ДОЛЖНА (SHALL) для `extensions.set_flags` принимать значения флагов из request/input (`flags_values`) и подставлять их в executor через `$flags.*` токены.

#### Scenario: Runtime values подставляются в executor params
- **GIVEN** request содержит `flags_values` и `apply_mask`
- **AND** action `extensions.set_flags` использует `$flags.active`, `$flags.safe_mode`, `$flags.unsafe_action_protection`
- **WHEN** вызывается `POST /api/v2/extensions/plan/`
- **THEN** backend строит effective params только из runtime `flags_values`
- **AND** не использует policy/preset source для резолва значений

