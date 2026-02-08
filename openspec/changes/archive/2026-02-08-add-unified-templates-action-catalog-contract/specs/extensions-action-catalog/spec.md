# Spec Delta: extensions-action-catalog

## MODIFIED Requirements
### Requirement: RuntimeSetting для каталога действий расширений
Система ДОЛЖНА (SHALL) использовать unified persistent store как единственный source of truth для каталога действий расширений.

RuntimeSetting `ui.action_catalog` НЕ ДОЛЖЕН (SHALL NOT) использоваться как active storage/read path после cutover.

#### Scenario: Effective action catalog строится из unified exposures
- **GIVEN** в unified store есть published exposures с `surface="action_catalog"`
- **WHEN** пользователь вызывает endpoint получения action catalog
- **THEN** система возвращает effective catalog из unified exposures
- **AND** runtime setting `ui.action_catalog` не читается в runtime

## ADDED Requirements
### Requirement: Unified action exposure MUST хранить capability-specific binding contract
Система ДОЛЖНА (SHALL) хранить capability-specific поля (`target_binding`, preset-поля и т.п.) на уровне exposure, с fail-closed валидацией для reserved capability.

#### Scenario: `extensions.set_flags` exposure без target binding не публикуется
- **GIVEN** exposure имеет `capability="extensions.set_flags"`
- **AND** не содержит валидного `target_binding.extension_name_param`
- **WHEN** exposure валидируется перед публикацией
- **THEN** exposure получает статус `invalid`
- **AND** не попадает в effective action catalog

### Requirement: `extensions.set_flags` binding MUST валидироваться против схемы команды
Система ДОЛЖНА (SHALL) для `capability="extensions.set_flags"` проверять, что `target_binding.extension_name_param` существует в `params_by_name` команды, привязанной к definition/exposure.

#### Scenario: Binding указывает на неизвестный параметр команды
- **GIVEN** exposure `extensions.set_flags` ссылается на command definition
- **AND** `target_binding.extension_name_param` отсутствует в `params_by_name` этой команды
- **WHEN** exposure проходит validate/publish
- **THEN** система возвращает ошибку валидации по пути binding-поля
- **AND** exposure остаётся в статусе `invalid`
