## MODIFIED Requirements
### Requirement: Plan set_flags принимает apply_mask
Система ДОЛЖНА (SHALL) принимать `apply_mask` в `POST /api/v2/extensions/plan/` для `capability="extensions.set_flags"` в template-based manual contract запуске.

Для template-based запуска required contract:
- `manual_contract_id`,
- `template_id`,
- `bindings`,
- `flags_values`,
- `apply_mask`.

`action_id` из `action_catalog` НЕ ДОЛЖЕН (SHALL NOT) быть primary runtime source для `extensions.set_flags`.

#### Scenario: Template-based request без `template_id` отклоняется
- **GIVEN** вызов `POST /api/v2/extensions/plan/` для `extensions.set_flags`
- **WHEN** отсутствует `template_id`
- **THEN** backend возвращает `HTTP 400` с `MISSING_PARAMETER`
- **AND** план не создаётся

#### Scenario: Template-based request без `bindings` отклоняется
- **GIVEN** вызов `POST /api/v2/extensions/plan/` для `extensions.set_flags`
- **WHEN** отсутствует `bindings` или binding schema невалидна
- **THEN** backend возвращает `HTTP 400` с `VALIDATION_ERROR`
- **AND** план не создаётся

### Requirement: Детерминированный выбор action через action_id
Система ДОЛЖНА (SHALL) обеспечивать детерминированный выбор executor для `extensions.set_flags` через `template_id` в template-based contract.

`action_id` ДОЛЖЕН (SHALL) рассматриваться только как legacy compatibility путь на время миграции (если явно включён), но НЕ ДОЛЖЕН (SHALL NOT) быть основным контрактом.

#### Scenario: Template-based path детерминирован без action catalog lookup
- **GIVEN** запрос содержит валидный `template_id` и `manual_contract_id`
- **WHEN** backend строит plan
- **THEN** executor резолвится только из выбранного template exposure
- **AND** ambiguity по множеству `action_catalog` записей не влияет на результат

## ADDED Requirements
### Requirement: `extensions.set_flags` MUST валидировать contract/template compatibility
Система ДОЛЖНА (SHALL) fail-closed валидировать совместимость выбранного `template_id` с `manual_contract_id` и binding slots до preview/execute.

#### Scenario: Несовместимый template отклоняется до preview
- **GIVEN** оператор выбрал template, не удовлетворяющий правилам контракта `extensions.set_flags.v1`
- **WHEN** вызывается `POST /api/v2/extensions/plan/`
- **THEN** backend возвращает `CONFIGURATION_ERROR`
- **AND** preview/execute не вызываются

