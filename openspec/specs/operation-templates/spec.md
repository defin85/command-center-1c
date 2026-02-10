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

#### Scenario: Action-specific binding настраивается в том же unified editor flow
- **GIVEN** staff пользователь редактирует action exposure `extensions.set_flags` в `/templates`
- **WHEN** открывает modal editor из общего списка
- **THEN** target binding настраивается в этом же modal editor как action-specific поле
- **AND** для настройки binding не требуется отдельный page-level flow

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

### Requirement: `/templates` list MUST использовать server-driven unified exposures contract
Система ДОЛЖНА (SHALL) для staff-режима `/templates` использовать server-driven list contract `operation-catalog/exposures`, чтобы избежать client-side full merge/filter как основного механизма.

UI ДОЛЖЕН (SHALL) передавать в backend текущие параметры list state (`surface`, search, filters, sort, pagination) и получать консистентный paged-result.

#### Scenario: Staff list state резолвится на сервере
- **GIVEN** staff пользователь открыл `/templates` и применил search/filters/sort
- **WHEN** UI выполняет list запрос
- **THEN** backend применяет фильтрацию/сортировку/пагинацию
- **AND** UI отображает результат без client-side пересборки полного набора записей

#### Scenario: UI использует side-loaded definitions из list ответа
- **GIVEN** staff пользователь работает с unified list `/templates`
- **WHEN** UI загружает страницу списка с `include=definitions`
- **THEN** необходимые definition данные приходят в top-level `definitions[]` list response
- **AND** UI связывает их с `exposures[]` по `definition_id` без inline definition в exposure
- **AND** отдельный обязательный round-trip на definitions для list screen не требуется

#### Scenario: Non-staff template flow не изменяется
- **GIVEN** non-staff пользователь с template view правами
- **WHEN** открывает `/templates`
- **THEN** UI использует `surface=template`
- **AND** поведение permissions и список доступных template exposures остаются корректными

