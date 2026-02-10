## MODIFIED Requirements
### Requirement: Plan set_flags принимает apply_mask
Система ДОЛЖНА (SHALL) принимать `apply_mask` в `POST /api/v2/extensions/plan/` для `capability="extensions.set_flags"` только в template-based запуске.

Для `extensions.set_flags` обязательны поля:
- `template_id`,
- `extension_name`,
- `flags_values`,
- `apply_mask`.

`action_id` НЕ ДОЛЖЕН (SHALL NOT) использоваться как runtime-контракт.

#### Scenario: set_flags request без `template_id` отклоняется
- **GIVEN** вызов `POST /api/v2/extensions/plan/` для `extensions.set_flags`
- **WHEN** отсутствует `template_id`
- **THEN** backend возвращает `HTTP 400` с `MISSING_PARAMETER`/`VALIDATION_ERROR`
- **AND** plan не создаётся

#### Scenario: set_flags request без `apply_mask` отклоняется
- **GIVEN** вызов `POST /api/v2/extensions/plan/` для `extensions.set_flags`
- **WHEN** отсутствует `apply_mask`
- **THEN** backend возвращает `HTTP 400` с `VALIDATION_ERROR`
- **AND** plan не создаётся

### Requirement: `extensions.set_flags` MUST использовать unified target binding contract
Система ДОЛЖНА (SHALL) подставлять `extension_name` через binding, определённый в выбранном template execution payload, и завершать запрос `CONFIGURATION_ERROR` при невалидном binding до preview/execute.

#### Scenario: Невалидный binding в template блокирует запуск
- **GIVEN** выбран template для `extensions.set_flags` с невалидным binding
- **WHEN** вызывается `POST /api/v2/extensions/plan/`
- **THEN** backend возвращает `CONFIGURATION_ERROR`
- **AND** preview/execute не вызываются

### Requirement: `extensions.set_flags` MUST использовать runtime `flags_values` как единственный источник значений
Система ДОЛЖНА (SHALL) подставлять значения флагов из request/input (`flags_values`) в executor через `$flags.*` токены, резолвимые в template payload.

#### Scenario: Runtime values подставляются в template executor params
- **GIVEN** request содержит `flags_values` и `apply_mask`
- **AND** template использует `$flags.*` токены для флагов
- **WHEN** вызывается `POST /api/v2/extensions/plan/`
- **THEN** backend строит effective params только из runtime `flags_values`
- **AND** не использует preset/state из action catalog

## ADDED Requirements
### Requirement: Plan/apply MUST резолвить extensions execution через `template_id`
Система ДОЛЖНА (SHALL) в `extensions.plan/apply` резолвить executor только через выбранный published template exposure.

#### Scenario: Executor выбирается детерминированно по template_id
- **GIVEN** запрос содержит валидный `template_id`
- **WHEN** backend строит plan
- **THEN** executor резолвится только из template exposure
- **AND** дополнительные action-catalog lookup не выполняются

### Requirement: Legacy `action_id` path MUST быть удалён
Система НЕ ДОЛЖНА (SHALL NOT) поддерживать legacy path запуска `extensions.*` через `action_id`.

#### Scenario: Legacy request с `action_id` отклоняется fail-closed
- **GIVEN** клиент отправляет запрос `extensions.plan` с `action_id` без template-based полей
- **WHEN** backend валидирует request
- **THEN** backend возвращает `HTTP 400`
- **AND** plan/apply не выполняются

### Requirement: Template/capability compatibility MUST валидироваться fail-closed
Система ДОЛЖНА (SHALL) проверять совместимость выбранного template и заявленной ручной операции (`extensions.sync` или `extensions.set_flags`) до preview/execute.

#### Scenario: Несовместимый template отклоняется
- **GIVEN** template не соответствует контракту выбранной операции
- **WHEN** вызывается `POST /api/v2/extensions/plan/`
- **THEN** backend возвращает `CONFIGURATION_ERROR`
- **AND** план не создаётся

## REMOVED Requirements
### Requirement: Детерминированный выбор action через action_id
**Reason**: action catalog удаляется из runtime-контракта.
**Migration**: использовать `template_id` как единственный ключ резолва executor.

### Requirement: Plan/apply MUST резолвить extensions actions из unified exposure
**Reason**: `surface="action_catalog"` decommissioned.
**Migration**: резолвить execution только из `surface="template"`.
