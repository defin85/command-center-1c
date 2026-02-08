## MODIFIED Requirements
### Requirement: `/templates` MUST быть единым UI управления template и action exposures
Система ДОЛЖНА (SHALL) использовать `/templates` как единственный операторский экран управления `operation_exposure` для surfaces `template` и `action_catalog`, и ДОЛЖНА (SHALL) предоставлять единый modal editor shell для обоих surfaces.

Отдельный экран `/settings/action-catalog` НЕ ДОЛЖЕН (SHALL NOT) оставаться поддерживаемой точкой редактирования.

#### Scenario: Staff редактирует template/action в одном editor shell
- **GIVEN** staff пользователь открывает `/templates`
- **WHEN** переключается между surfaces `template` и `action_catalog`
- **THEN** create/edit выполняется через единый tabbed modal editor (`Basics`, `Executor`, `Params`, `Safety & Fixed`, `Preview`)
- **AND** surface-specific поля отображаются внутри того же editor shell без отдельной ветки legacy modal

#### Scenario: Template surface использует тот же pipeline, что и action surface
- **GIVEN** staff редактирует template exposure
- **WHEN** сохраняет изменения
- **THEN** UI использует тот же adapter/serializer/validation pipeline, что и для action exposure
- **AND** execution payload materialize-ится в unified contract без surface-specific расхождений формы executor

#### Scenario: Editor не требует ручной выбор driver для canonical executor kinds
- **GIVEN** staff редактирует exposure в `/templates`
- **WHEN** выбирает `executor.kind` из `ibcmd_cli`, `designer_cli`, `workflow`
- **THEN** UI не запрашивает отдельный manual выбор `driver` для canonical kinds
- **AND** выбор `executor.kind` однозначно определяет runtime driver mapping в сохранённом контракте
