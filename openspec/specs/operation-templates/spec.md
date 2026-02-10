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
Система ДОЛЖНА (SHALL) использовать `/templates` как templates-only реестр `operation_exposure(surface="template")`.

#### Scenario: `/templates` не показывает action-catalog controls
- **WHEN** пользователь открывает `/templates`
- **THEN** UI показывает только templates
- **AND** controls `Action Catalog`/`New Action` отсутствуют

#### Scenario: Legacy deep-link `surface=action_catalog` нормализуется
- **WHEN** пользователь открывает `/templates?surface=action_catalog`
- **THEN** UI нормализует состояние к templates-only
- **AND** action-catalog запросы не отправляются

### Requirement: `/templates` list MUST использовать server-driven unified exposures contract
Система ДОЛЖНА (SHALL) использовать server-driven list контракт `operation-catalog/exposures` для template-only выборки.

#### Scenario: Table state обрабатывается backend-ом
- **GIVEN** пользователь применил search/filters/sort/pagination
- **WHEN** UI выполняет list запрос
- **THEN** backend возвращает paged template-only результат
- **AND** UI не делает client-side merge разных surfaces

### Requirement: Template editor MUST быть универсальным по executor kinds
Система ДОЛЖНА (SHALL) поддерживать в templates editor executor kinds `ibcmd_cli`, `designer_cli`, `workflow` в едином editor shell.

#### Scenario: Один editor shell конфигурирует разные executor kinds
- **WHEN** пользователь переключает executor kind в template editor
- **THEN** UI остаётся в одном modal flow
- **AND** shape payload валидируется как template contract

### Requirement: Template MUST быть явно совместим с manual operation
Система ДОЛЖНА (SHALL) явно маркировать template exposure для manual operation совместимости через `capability` template exposure.

#### Scenario: Template помечен как compatible с manual operation
- **GIVEN** template предназначен для `extensions.set_flags`
- **WHEN** template сохраняется
- **THEN** `exposure.capability` фиксируется как `extensions.set_flags`
- **AND** template может использоваться только этим manual operation key

