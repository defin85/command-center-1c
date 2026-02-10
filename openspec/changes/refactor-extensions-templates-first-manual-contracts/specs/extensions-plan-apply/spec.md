## MODIFIED Requirements
### Requirement: Plan set_flags принимает apply_mask
Система ДОЛЖНА (SHALL) принимать `apply_mask` в `POST /api/v2/extensions/plan/` для `capability="extensions.set_flags"` в template-based запуске.

Для template-based запуска required fields:
- `template_id`,
- `flags_values`,
- `apply_mask`.

`action_id` из `action_catalog` НЕ ДОЛЖЕН (SHALL NOT) быть primary runtime source для `extensions.set_flags`.

#### Scenario: Template-based request без `template_id` отклоняется
- **GIVEN** вызов `POST /api/v2/extensions/plan/` для `extensions.set_flags`
- **WHEN** отсутствует `template_id`
- **THEN** backend возвращает `HTTP 400` с `MISSING_PARAMETER`
- **AND** план не создаётся

#### Scenario: Template-based request без `flags_values` отклоняется
- **GIVEN** вызов `POST /api/v2/extensions/plan/` для `extensions.set_flags`
- **WHEN** отсутствует `flags_values` или schema невалидна
- **THEN** backend возвращает `HTTP 400` с `VALIDATION_ERROR`
- **AND** план не создаётся

### Requirement: Детерминированный выбор executor через template_id
Система ДОЛЖНА (SHALL) обеспечивать детерминированный выбор executor для `extensions.set_flags` через `template_id` в template-based contract.

`action_id` НЕ ДОЛЖЕН (SHALL NOT) использоваться как runtime-контракт для `extensions.set_flags`.

#### Scenario: Template-based path детерминирован без action catalog lookup
- **GIVEN** запрос содержит валидный `template_id`
- **WHEN** backend строит plan
- **THEN** executor резолвится только из выбранного template exposure
- **AND** ambiguity по множеству `action_catalog` записей не влияет на результат

#### Scenario: Legacy `action_id` request отклоняется
- **GIVEN** вызов `POST /api/v2/extensions/plan/` для `extensions.set_flags` содержит только `action_id` без template-based полей
- **WHEN** backend валидирует request
- **THEN** backend возвращает `HTTP 400` с `VALIDATION_ERROR`/`MISSING_PARAMETER`
- **AND** plan не создаётся

## ADDED Requirements
### Requirement: `extensions.set_flags` MUST валидировать template/capability compatibility
Система ДОЛЖНА (SHALL) fail-closed валидировать совместимость выбранного `template_id` с `capability="extensions.set_flags"` до preview/execute.

#### Scenario: Несовместимый template отклоняется до preview
- **GIVEN** оператор выбрал template, не совместимый с `capability="extensions.set_flags"`
- **WHEN** вызывается `POST /api/v2/extensions/plan/`
- **THEN** backend возвращает `CONFIGURATION_ERROR`
- **AND** preview/execute не вызываются
