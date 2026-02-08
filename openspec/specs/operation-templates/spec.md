# operation-templates Specification

## Purpose
TBD - created by archiving change add-unified-templates-action-catalog-contract. Update Purpose after archive.
## Requirements
### Requirement: Templates API MUST использовать unified persistent store
Система ДОЛЖНА (SHALL) управлять template exposures через unified management API `operation-catalog` (с `surface="template"`), а не через отдельный legacy template CRUD/list API-контур.

Legacy endpoints `/api/v2/templates/list-templates/`, `/api/v2/templates/create-template/`, `/api/v2/templates/update-template/`, `/api/v2/templates/delete-template/` НЕ ДОЛЖНЫ (SHALL NOT) оставаться поддерживаемым контрактом управления templates.

#### Scenario: Template list/read идёт через unified exposure API
- **GIVEN** пользователь имеет права просмотра templates
- **WHEN** UI/клиент запрашивает `operation-catalog` exposures с `surface=template`
- **THEN** API возвращает template exposures из unified store
- **AND** ответ покрывает поля, необходимые для template management UI

#### Scenario: Template create/update/delete идёт через unified exposure API
- **GIVEN** пользователь имеет права управления templates
- **WHEN** UI/клиент выполняет upsert/publish для `surface=template`
- **THEN** изменения фиксируются в unified store
- **AND** отдельные template CRUD endpoints не используются

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
Система ДОЛЖНА (SHALL) использовать `/templates` как единый management-экран для `operation_exposure` с surfaces `template` и `action_catalog`, показывая один список exposure и единый modal editor.

Переключение между surfaces ДОЛЖНО (SHALL) выполняться через `surface` filter (синхронизированный с query-параметром URL), а не через отдельные вкладки/страницы.

#### Scenario: Staff переключает surface в одном list shell
- **GIVEN** staff пользователь открыл `/templates`
- **WHEN** выбирает `surface=action_catalog`
- **THEN** UI показывает action exposures в том же list shell
- **AND** create/edit выполняется тем же modal editor, что и для `surface=template`

#### Scenario: Non-staff запрашивает action surface
- **GIVEN** non-staff пользователь открывает `/templates?surface=action_catalog`
- **WHEN** UI применяет RBAC для surfaces
- **THEN** выбранный surface принудительно становится `template`
- **AND** action-catalog management запросы не отправляются

#### Scenario: Deep-link сохраняет выбранный surface
- **GIVEN** staff пользователь переключил фильтр на `action_catalog`
- **WHEN** обновляет страницу или делится ссылкой
- **THEN** `/templates?surface=action_catalog` открывается с тем же выбранным surface
- **AND** список и toolbar соответствуют выбранному surface

