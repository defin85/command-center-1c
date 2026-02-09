## ADDED Requirements
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
