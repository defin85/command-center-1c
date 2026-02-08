# Spec Delta: extensions-plan-apply

## ADDED Requirements
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
