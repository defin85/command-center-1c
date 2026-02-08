# Spec Delta: ui-action-catalog-editor

## ADDED Requirements
### Requirement: Editor MUST записывать action exposures в unified persistent store
Система ДОЛЖНА (SHALL) сохранять изменения editor-а в unified exposure-модель (`surface="action_catalog"`), а не в isolated legacy JSON источник.

#### Scenario: Save action обновляет unified exposure
- **GIVEN** staff сохраняет action из editor modal
- **WHEN** backend принимает payload
- **THEN** обновляется/создаётся соответствующий action exposure
- **AND** изменения доступны в runtime только через unified storage path

### Requirement: Editor MUST использовать shared command-config contract с Templates UI
Система ДОЛЖНА (SHALL) использовать общий adapter/контракт command-конфигурации между `/templates` и `/settings/action-catalog`, чтобы исключить дублирование executor-логики.

#### Scenario: Одинаковая command-конфигурация сериализуется одинаково в обеих страницах
- **GIVEN** оператор задаёт одинаковые `command_id`, `params`, `additional_args`, `stdin`, safety-поля
- **WHEN** сохраняет template и action
- **THEN** serialized execution payload в unified definition совпадает по контракту
- **AND** не возникает surface-specific расхождения executor shape

### Requirement: Editor hints MUST включать `target_binding` schema для `extensions.set_flags`
Система ДОЛЖНА (SHALL) возвращать в editor hints capability schema для `target_binding`, чтобы UI строил guided-поле binding без хардкода структуры.

#### Scenario: Hints содержат `target_binding.extension_name_param`
- **GIVEN** staff открывает editor для action catalog
- **WHEN** UI получает hints для capability `extensions.set_flags`
- **THEN** hints содержит schema для `target_binding.extension_name_param`
- **AND** UI отображает guided-поле для настройки binding

### Requirement: Editor MUST показывать migration/validation diagnostics для unified exposure
Система ДОЛЖНА (SHALL) показывать оператору ошибки валидации unified exposure по точному пути поля и не выполнять silent fallback.

#### Scenario: Ошибка в `target_binding` отображается по пути unified поля
- **GIVEN** action `extensions.set_flags` сохранён с невалидным binding
- **WHEN** backend возвращает validation error
- **THEN** UI показывает ошибку по пути до binding-поля
- **AND** UI не выполняет автозаполнение/автокоррекцию без явного действия оператора
