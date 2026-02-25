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

### Requirement: Metadata catalog retrieval MUST использовать cache-first стратегию с явным refresh
Система ДОЛЖНА (SHALL) кэшировать результат metadata catalog по выбранной ИБ для снижения нагрузки на OData endpoint.

Система ДОЛЖНА (SHALL) поддерживать:
- cache TTL;
- явный операторский refresh;
- прозрачный индикатор источника (`cache` или `live`) в ответе API.

Система НЕ ДОЛЖНА (SHALL NOT) скрывать состояние устаревшего каталога: ответ ДОЛЖЕН (SHALL) включать `fetched_at` и `catalog_version` или эквивалентный version marker.

#### Scenario: Повторный запрос каталога обслуживается из кэша
- **GIVEN** каталог метаданных ИБ уже загружен и TTL ещё не истёк
- **WHEN** UI повторно запрашивает metadata catalog
- **THEN** backend возвращает кэшированную версию
- **AND** response явно указывает, что источник данных — cache

#### Scenario: Оператор принудительно обновляет каталог после изменений в 1С
- **GIVEN** структура метаданных в 1С изменилась
- **WHEN** оператор инициирует refresh metadata catalog
- **THEN** backend повторно читает `$metadata` из OData endpoint
- **AND** в ответе возвращается обновлённый `catalog_version`

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
Система ДОЛЖНА (SHALL) при сохранении topology snapshot валидировать, что ссылки в `document_policy` указывают на существующие элементы metadata catalog выбранной ИБ:
- `entity_name`;
- `field_mapping` ключи;
- `table_parts_mapping` и `row_fields`.

Система НЕ ДОЛЖНА (SHALL NOT) сохранять snapshot, если policy ссылается на отсутствующие документы/поля/табличные части.

Ответ об ошибке ДОЛЖЕН (SHALL) содержать machine-readable код и путь до проблемного узла policy для быстрого исправления в UI.

#### Scenario: Policy с несуществующим реквизитом отклоняется до persistence
- **GIVEN** оператор сформировал policy с `field_mapping`, где указан несуществующий реквизит документа
- **WHEN** выполняется topology snapshot save
- **THEN** backend отклоняет запрос валидационной ошибкой
- **AND** snapshot в БД не изменяется
- **AND** UI получает machine-readable информацию для подсветки проблемного поля
