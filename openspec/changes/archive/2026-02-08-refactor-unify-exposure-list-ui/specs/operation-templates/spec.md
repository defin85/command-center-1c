# Spec Delta: operation-templates

## MODIFIED Requirements
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
