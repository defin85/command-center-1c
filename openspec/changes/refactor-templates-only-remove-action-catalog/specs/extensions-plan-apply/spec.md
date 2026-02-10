## MODIFIED Requirements
### Requirement: Plan/apply для extensions с drift check
Система ДОЛЖНА (SHALL) поддерживать plan/apply для extensions через manual-operations контракт с drift check.

#### Scenario: set_flags selective apply применяет только выбранные флаги
- **GIVEN** оператор запускает `manual_operation="extensions.set_flags"` и передаёт `apply_mask`
- **WHEN** выполняется apply по плану
- **THEN** executor получает параметры только выбранных флагов
- **AND** невыбранные флаги не модифицируются

### Requirement: Plan set_flags принимает apply_mask
Система ДОЛЖНА (SHALL) принимать `apply_mask` в template-based запуске `extensions.set_flags`.

Для `extensions.set_flags` обязательны:
- `manual_operation`,
- template resolve (`template_id` override или preferred binding),
- `extension_name`,
- `flags_values`,
- `apply_mask`.

#### Scenario: set_flags request без template resolve отклоняется
- **GIVEN** вызов `POST /api/v2/extensions/plan/` для `extensions.set_flags`
- **WHEN** отсутствует и `template_id`, и preferred binding
- **THEN** backend возвращает `HTTP 400` (`MISSING_TEMPLATE_BINDING`)
- **AND** plan не создаётся

#### Scenario: set_flags request без `apply_mask` отклоняется
- **GIVEN** вызов `POST /api/v2/extensions/plan/` для `extensions.set_flags`
- **WHEN** отсутствует `apply_mask`
- **THEN** backend возвращает `HTTP 400` (`VALIDATION_ERROR`)
- **AND** plan не создаётся

## ADDED Requirements
### Requirement: Extensions plan MUST использовать `manual_operation` hardcoded registry
Система ДОЛЖНА (SHALL) принимать `manual_operation` из поддерживаемого hardcoded набора keys и валидировать его fail-closed.

Поддерживаемые keys для этого change:
- `extensions.sync`
- `extensions.set_flags`

`extensions.list` НЕ ДОЛЖЕН (SHALL NOT) поддерживаться.

#### Scenario: Неподдерживаемый `manual_operation` отклоняется
- **WHEN** клиент отправляет `manual_operation`, отсутствующий в registry
- **THEN** backend возвращает `HTTP 400` (`INVALID_PARAMETER`)
- **AND** plan не создаётся

#### Scenario: `extensions.list` отклоняется
- **WHEN** клиент отправляет `manual_operation="extensions.list"`
- **THEN** backend возвращает `HTTP 400` (`INVALID_PARAMETER`)
- **AND** запуск не выполняется

### Requirement: Template resolve order MUST быть детерминированным
Система ДОЛЖНА (SHALL) резолвить template в строгом порядке:
1. request `template_id`,
2. tenant preferred binding для `manual_operation`,
3. иначе ошибка.

`template_id` трактуется как `operation_exposure.alias` (string).

#### Scenario: Request override имеет приоритет над preferred binding
- **GIVEN** у tenant настроен preferred template для `extensions.sync`
- **AND** request содержит другой `template_id`
- **WHEN** backend строит plan
- **THEN** используется template из request
- **AND** preferred binding не переопределяет этот запуск

#### Scenario: Stale preferred binding после rename/delete alias отклоняется
- **GIVEN** preferred binding указывает на `template_id`, которого больше нет среди template exposures
- **WHEN** backend строит plan без request override
- **THEN** backend возвращает `HTTP 400` (`MISSING_TEMPLATE_BINDING`)
- **AND** plan не создаётся

#### Scenario: Request override с неизвестным `template_id` отклоняется
- **WHEN** клиент передаёт `template_id`, отсутствующий в template exposures
- **THEN** backend возвращает `HTTP 400` (`INVALID_PARAMETER`)
- **AND** plan не создаётся

### Requirement: Template/manual-operation compatibility MUST валидироваться fail-closed
Система ДОЛЖНА (SHALL) проверять, что выбранный template совместим с `manual_operation`.

#### Scenario: Несовместимый template отклоняется
- **GIVEN** template exposure имеет `capability`, отличное от `manual_operation`
- **WHEN** вызывается `POST /api/v2/extensions/plan/`
- **THEN** backend возвращает `HTTP 400` (`CONFIGURATION_ERROR`)
- **AND** plan не создаётся

### Requirement: `extensions.set_flags` MUST использовать template binding contract
Система ДОЛЖНА (SHALL) подставлять `extension_name` через `template_data.target_binding.extension_name_param` выбранного template.

#### Scenario: Невалидный binding блокирует запуск
- **GIVEN** template `extensions.set_flags` без валидного `target_binding.extension_name_param`
- **WHEN** вызывается `POST /api/v2/extensions/plan/`
- **THEN** backend возвращает `HTTP 400` (`CONFIGURATION_ERROR`)
- **AND** preview/execute не вызываются

### Requirement: Legacy `action_id` path MUST быть удалён
Система НЕ ДОЛЖНА (SHALL NOT) поддерживать запуск `extensions.*` через `action_id`.

#### Scenario: Legacy request с `action_id` отклоняется
- **WHEN** клиент отправляет request c `action_id`
- **THEN** backend возвращает `HTTP 400` (`VALIDATION_ERROR`)
- **AND** legacy path не выполняется

### Requirement: Legacy планы старого формата MUST отклоняться на apply
Система ДОЛЖНА (SHALL) отклонять `extensions.apply`, если план не соответствует metadata-контракту `template_manual_operation`.

Legacy формат определяется как любой plan, где выполняется хотя бы одно условие:
- отсутствует `metadata.execution_source=template_manual_operation`,
- отсутствуют `metadata.manual_operation` или `metadata.template_id`,
- присутствуют legacy-поля `action_id` или `action_capability`.

#### Scenario: Apply для legacy plan возвращает `PLAN_INVALID_LEGACY`
- **GIVEN** в БД присутствует план, созданный до cutover без manual-operations metadata
- **WHEN** клиент вызывает `POST /api/v2/extensions/apply/` с таким `plan_id`
- **THEN** backend возвращает `HTTP 400` с `PLAN_INVALID_LEGACY`
- **AND** выполнение не запускается
