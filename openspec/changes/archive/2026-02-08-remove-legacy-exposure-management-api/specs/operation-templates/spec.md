# Spec Delta: operation-templates

## MODIFIED Requirements
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
