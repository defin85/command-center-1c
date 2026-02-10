## MODIFIED Requirements
### Requirement: `/templates` MUST быть единым UI управления template и action exposures
Система ДОЛЖНА (SHALL) использовать `/templates` как templates-only реестр `operation_exposure(surface="template")`.

Экран НЕ ДОЛЖЕН (SHALL NOT) показывать/управлять `action_catalog` surface.

#### Scenario: `/templates` отображает только templates
- **GIVEN** пользователь открывает `/templates`
- **WHEN** список загружается
- **THEN** UI показывает только template exposures
- **AND** controls `Action Catalog`/`New Action` отсутствуют

#### Scenario: Legacy deep-link `surface=action_catalog` не активирует удалённый режим
- **GIVEN** пользователь открывает `/templates?surface=action_catalog`
- **WHEN** страница инициализируется
- **THEN** UI нормализует режим к templates-only
- **AND** action-catalog запросы не отправляются

### Requirement: `/templates` list MUST использовать server-driven unified exposures contract
Система ДОЛЖНА (SHALL) использовать server-driven list контракт `operation-catalog/exposures` для template-only выборки.

#### Scenario: Table state обрабатывается backend-ом
- **GIVEN** пользователь применил search/filters/sort/pagination на `/templates`
- **WHEN** UI выполняет list запрос
- **THEN** backend возвращает paged template-only результат
- **AND** UI не выполняет client-side merge surfaces

## ADDED Requirements
### Requirement: Templates editor MUST переиспользовать существующий unified editor shell
Система ДОЛЖНА (SHALL) использовать существующий editor shell (бывший unified/action editor) как единственный flow редактирования templates.

#### Scenario: Create/Edit template выполняется в одном modal shell
- **GIVEN** пользователь создаёт или редактирует template
- **WHEN** открывается editor modal
- **THEN** используется тот же общий editor shell
- **AND** доступны только template-поля и template-валидация
