## MODIFIED Requirements
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

## ADDED Requirements
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
