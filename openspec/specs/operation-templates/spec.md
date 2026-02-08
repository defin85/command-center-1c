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
Система ДОЛЖНА (SHALL) использовать `/templates` как единственный операторский экран управления `operation_exposure` для surfaces `template` и `action_catalog`.

Отдельный экран `/settings/action-catalog` НЕ ДОЛЖЕН (SHALL NOT) оставаться поддерживаемой точкой редактирования.

#### Scenario: Staff управляет action exposures из `/templates`
- **GIVEN** staff пользователь открывает `/templates`
- **WHEN** выбирает surface `action_catalog`
- **THEN** UI показывает список и операции редактирования для action exposures из unified store
- **AND** изменения сохраняются через unified API без runtime setting adapters

#### Scenario: Пользователь без staff прав работает только с template surface
- **GIVEN** пользователь имеет template permissions, но не является staff
- **WHEN** открывает `/templates`
- **THEN** UI показывает только template surface
- **AND** не запрашивает action-catalog management paths

#### Scenario: Legacy route action catalog больше не доступен
- **WHEN** пользователь открывает `/settings/action-catalog`
- **THEN** приложение не предоставляет editor этого экрана как поддерживаемый UX flow

