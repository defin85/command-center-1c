# operation-templates Specification

## Purpose
TBD - created by archiving change add-unified-templates-action-catalog-contract. Update Purpose after archive.
## Requirements
### Requirement: Templates API MUST использовать unified persistent store
Система ДОЛЖНА (SHALL) обслуживать `/api/v2/templates/*` через `operation_exposure(surface="template")` и связанный `operation_definition`, а не через отдельный изолированный источник данных.

#### Scenario: List templates возвращает unified exposures
- **GIVEN** в unified store есть опубликованные template exposures
- **WHEN** пользователь вызывает `/api/v2/templates/list-templates/`
- **THEN** API возвращает шаблоны, материализованные из unified exposures
- **AND** response shape определяется unified templates контрактом

### Requirement: Templates write-path MUST поддерживать dedup execution definitions
Система ДОЛЖНА (SHALL) при create/update template переиспользовать существующий `operation_definition`, если execution payload идентичен (fingerprint match).

#### Scenario: Создание template с уже существующим execution payload
- **GIVEN** в unified store уже есть `operation_definition` с тем же fingerprint
- **WHEN** создаётся новый template exposure
- **THEN** система создаёт только новый exposure
- **AND** existing definition переиспользуется

### Requirement: Templates RBAC MUST сохраниться при переходе на unified persistence
Система ДОЛЖНА (SHALL) сохранить текущие ограничения доступа templates API (view/manage) после перехода на unified модель.

#### Scenario: Пользователь без manage права не может изменить template exposure
- **GIVEN** пользователь не имеет `templates.manage_operation_template`
- **WHEN** пользователь вызывает create/update/delete template endpoint
- **THEN** API возвращает отказ по правам
- **AND** unified persistent store не изменяется

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

