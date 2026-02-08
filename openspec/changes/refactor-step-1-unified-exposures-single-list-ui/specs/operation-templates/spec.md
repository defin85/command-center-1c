## MODIFIED Requirements
### Requirement: `/templates` MUST быть единым UI управления template и action exposures
Система ДОЛЖНА (SHALL) использовать `/templates` как единый реестр `operation_exposure` с общей таблицей и общим toolbar для surfaces `template` и `action_catalog`.

`surface` ДОЛЖЕН (SHALL) быть фасетным фильтром списка, а не page-level режимом экрана.

- Для staff доступны значения фильтра: `all`, `template`, `action_catalog`.
- Для non-staff доступно только `template`.
- В mixed-list ДОЛЖНО (SHALL) быть явное отображение surface в строке.

Create/Edit ДОЛЖНЫ (SHALL) выполняться через единый modal editor flow для обеих surfaces.

#### Scenario: Staff видит mixed-surface реестр в одном списке
- **GIVEN** staff пользователь открывает `/templates`
- **WHEN** выбран фильтр `surface=all`
- **THEN** UI показывает единый список exposures разных surfaces
- **AND** каждая строка явно указывает `surface`

#### Scenario: Staff фильтрует список по surface без смены page-level flow
- **GIVEN** staff пользователь работает в `/templates`
- **WHEN** переключает фильтр `all -> action_catalog -> template`
- **THEN** обновляется набор строк в той же таблице
- **AND** структура страницы и editor flow остаются едиными

#### Scenario: Non-staff не получает action surface в unified list
- **GIVEN** non-staff пользователь открывает `/templates`
- **WHEN** в URL передан `surface=all` или `surface=action_catalog`
- **THEN** UI принудительно использует `surface=template`
- **AND** action-catalog management запросы не отправляются

#### Scenario: Deep-link сохраняет выбранный фильтр surface
- **GIVEN** staff пользователь выбрал `surface=action_catalog`
- **WHEN** обновляет страницу или открывает ссылку `/templates?surface=action_catalog`
- **THEN** UI восстанавливает тот же фильтр
- **AND** отображает соответствующий subset списка
