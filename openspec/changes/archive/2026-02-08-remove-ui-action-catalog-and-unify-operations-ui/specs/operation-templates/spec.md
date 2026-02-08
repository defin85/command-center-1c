## ADDED Requirements
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
