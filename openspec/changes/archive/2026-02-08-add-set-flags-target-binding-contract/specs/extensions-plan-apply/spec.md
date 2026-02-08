# Spec Delta: extensions-plan-apply

## ADDED Requirements
### Requirement: Plan/apply `extensions.set_flags` MUST использовать target binding для подстановки `extension_name`
Система ДОЛЖНА (SHALL) при plan/apply для `capability="extensions.set_flags"` подставлять request `extension_name` в `executor.params[executor.target_binding.extension_name_param]` до preview/execute.

#### Scenario: Команда требует `name`, binding указывает на `name`
- **GIVEN** выбран action `extensions.set_flags` с `executor.target_binding.extension_name_param="name"`
- **AND** request содержит `extension_name="ExtA"`
- **WHEN** вызывается `POST /api/v2/extensions/plan/`
- **THEN** effective executor params содержит `name="ExtA"` перед сборкой execution plan
- **AND** preview/execute не завершается ошибкой драйвера о пропущенном обязательном target-параметре

### Requirement: Plan/apply `extensions.set_flags` MUST fail-closed при невалидном binding
Система ДОЛЖНА (SHALL) останавливать plan/apply для `extensions.set_flags` с `CONFIGURATION_ERROR`, если binding отсутствует или невалиден, и НЕ ДОЛЖНА (SHALL NOT) выполнять неявное угадывание target mapping по токенам.

#### Scenario: Binding отсутствует
- **GIVEN** выбран action `extensions.set_flags` без `executor.target_binding.extension_name_param`
- **WHEN** вызывается `POST /api/v2/extensions/plan/`
- **THEN** backend возвращает `HTTP 400` с кодом `CONFIGURATION_ERROR`
- **AND** execution preview/operation не создаётся

#### Scenario: Binding ссылается на параметр вне схемы команды
- **GIVEN** `executor.target_binding.extension_name_param="name"`
- **AND** в `params_by_name` выбранной команды нет параметра `name`
- **WHEN** вызывается `POST /api/v2/extensions/plan/`
- **THEN** backend возвращает `HTTP 400` с кодом `CONFIGURATION_ERROR`
- **AND** запрос останавливается до вызова слоя выполнения `ibcmd_cli`
