## ADDED Requirements
### Requirement: Pool catalog API MUST предоставлять полный каталог OData-метаданных для выбранной ИБ
Система ДОЛЖНА (SHALL) предоставлять read endpoint каталога метаданных для выбранной информационной базы, достаточный для интерактивной сборки `Document policy` и `Edge metadata`.

Каталог ДОЛЖЕН (SHALL) включать минимум:
- список документов (`entity_name`, `display_name`);
- список реквизитов документа (`fields[]`);
- список табличных частей (`table_parts[]`);
- список реквизитов строки табличной части (`row_fields[]`).

Каталог ДОЛЖЕН (SHALL) возвращаться в нормализованном machine-readable формате, пригодном для UI form-builder без дополнительного парсинга CSDL на клиенте.

#### Scenario: UI получает каталог документов и реквизитов для builder-режима
- **GIVEN** оператор выбрал ИБ в topology editor
- **WHEN** UI запрашивает metadata catalog через публичный endpoint
- **THEN** backend возвращает документы, реквизиты и табличные части в нормализованной структуре
- **AND** UI может построить интерактивные селекторы без ручного ввода имён полей

### Requirement: Metadata catalog retrieval MUST использовать persisted snapshot в БД и Redis только как ускоритель
Система ДОЛЖНА (SHALL) хранить нормализованный metadata catalog в persisted snapshot в БД как source-of-truth для выбранной ИБ.

Система ДОЛЖНА (SHALL) поддерживать:
- version markers для snapshot: `config_name`, `config_version`, `metadata_hash` (или эквивалент);
- явный признак текущей версии snapshot (`is_current` или эквивалент);
- Redis read-through cache как ускоритель чтения (не источник истины);
- cache TTL для Redis-слоя;
- явный операторский refresh;
- прозрачный индикатор источника (`redis`, `db`, `live_refresh`) в ответе API.

Система НЕ ДОЛЖНА (SHALL NOT) скрывать состояние каталога: ответ ДОЛЖЕН (SHALL) включать `fetched_at`, `catalog_version`, `config_name`, `config_version` и `metadata_hash` (или эквивалентные маркеры версии).

#### Scenario: Повторный запрос каталога обслуживается из Redis-ускорителя
- **GIVEN** каталог метаданных ИБ уже загружен и TTL ещё не истёк
- **WHEN** UI повторно запрашивает metadata catalog
- **THEN** backend возвращает версию current snapshot через Redis-слой
- **AND** response явно указывает, что источник данных — `redis`

#### Scenario: При недоступности Redis чтение продолжается из БД snapshot
- **GIVEN** Redis временно недоступен или cache key отсутствует
- **WHEN** UI запрашивает metadata catalog
- **THEN** backend читает current snapshot из БД
- **AND** response явно указывает, что источник данных — `db`

#### Scenario: Оператор принудительно обновляет каталог после изменений в 1С
- **GIVEN** структура метаданных в 1С изменилась
- **WHEN** оператор инициирует refresh metadata catalog
- **THEN** backend повторно читает `$metadata` из OData endpoint и сохраняет/обновляет snapshot в БД
- **AND** в ответе возвращается обновлённый `catalog_version` и актуальные version markers

### Requirement: Topology editor UI MUST поддерживать интерактивное создание Document policy и Edge metadata
Система ДОЛЖНА (SHALL) предоставлять в `/pools/catalog` builder-режим, в котором оператор выбирает документы, реквизиты и табличные части из metadata catalog и формирует:
- `edge.metadata.document_policy`;
- произвольные поля `edge.metadata`.

Система ДОЛЖНА (SHALL) поддерживать минимум:
- добавление/удаление chain и документов внутри chain;
- выбор `entity_name` из каталога;
- настройку `field_mapping` и `table_parts_mapping` из доступных metadata-полей;
- настройку link-полей (`link_to`, `link_rules`) между документами цепочки.

#### Scenario: Оператор собирает цепочку документов без ручного ввода JSON-ключей
- **GIVEN** metadata catalog успешно загружен
- **WHEN** оператор в builder-режиме добавляет документы и заполняет mappings через UI
- **THEN** UI формирует валидный JSON `document_policy.v1`
- **AND** сохраняемый snapshot содержит собранный `edge.metadata.document_policy`

### Requirement: UI MUST сохранять raw JSON fallback и round-trip совместимость metadata
Система ДОЛЖНА (SHALL) поддерживать переключение между builder-режимом и raw JSON редактированием для `Document policy` и `Edge metadata`.

Система ДОЛЖНА (SHALL) сохранять round-trip совместимость:
- пользовательские/неизвестные ключи metadata не теряются;
- переключение режимов не разрушает корректный JSON.

Система ДОЛЖНА (SHALL) блокировать сохранение при невалидном JSON и показывать operator-friendly ошибку с указанием проблемного участка.

#### Scenario: Переключение builder/raw не теряет нестандартные metadata ключи
- **GIVEN** оператор добавил в `edge.metadata` кастомный ключ, не описанный builder-формой
- **WHEN** оператор переключается между builder и raw JSON режимами
- **THEN** кастомный ключ сохраняется без потери
- **AND** итоговый snapshot содержит исходные пользовательские поля

### Requirement: Topology mutating validation MUST проверять соответствие policy актуальному metadata catalog
Система ДОЛЖНА (SHALL) при сохранении topology snapshot валидировать, что ссылки в `document_policy` указывают на существующие элементы current metadata snapshot выбранной ИБ/конфигурации:
- `entity_name`;
- `field_mapping` ключи;
- `table_parts_mapping` и `row_fields`.

Система НЕ ДОЛЖНА (SHALL NOT) сохранять snapshot, если policy ссылается на отсутствующие документы/поля/табличные части.
Система НЕ ДОЛЖНА (SHALL NOT) сохранять snapshot, если для выбранной ИБ/конфигурации отсутствует current metadata snapshot.

Ответ об ошибке ДОЛЖЕН (SHALL) содержать machine-readable код и путь до проблемного узла policy для быстрого исправления в UI.

#### Scenario: Policy с несуществующим реквизитом отклоняется до persistence
- **GIVEN** оператор сформировал policy с `field_mapping`, где указан несуществующий реквизит документа
- **WHEN** выполняется topology snapshot save
- **THEN** backend отклоняет запрос валидационной ошибкой
- **AND** snapshot в БД не изменяется
- **AND** UI получает machine-readable информацию для подсветки проблемного поля

#### Scenario: Сохранение topology блокируется при отсутствии current metadata snapshot
- **GIVEN** для выбранной ИБ/конфигурации нет актуального metadata snapshot
- **WHEN** выполняется topology snapshot save
- **THEN** backend отклоняет запрос fail-closed ошибкой
- **AND** UI получает machine-readable код причины и путь до проблемного policy context
