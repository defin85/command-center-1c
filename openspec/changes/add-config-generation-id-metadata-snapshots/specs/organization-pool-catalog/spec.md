## MODIFIED Requirements
### Requirement: Metadata catalog retrieval MUST использовать persisted snapshot в БД и Redis только как ускоритель
Система ДОЛЖНА (SHALL) хранить нормализованный metadata catalog как canonical persisted snapshot, пригодный для reuse между несколькими ИБ в рамках одной tenant-scoped configuration signature, а не как database-local current snapshot по `database_id` alone.

Canonical metadata snapshot scope ДОЛЖЕН (SHALL) включать:
- `config_name`;
- `config_version`;
- `extensions_fingerprint` или эквивалентный marker extensions/applicability state;
- `metadata_hash` или эквивалентный fingerprint опубликованной OData metadata surface.

Canonical snapshot identity НЕ ДОЛЖНА (SHALL NOT) включать `database_id` после cutover. Конкретная ИБ ДОЛЖНА (SHALL) использоваться только как live refresh/probe source и provenance anchor для shared snapshot.

Read/refresh path МОЖЕТ (MAY) стартовать от выбранной ИБ, но:
- конкретная ИБ ДОЛЖНА (SHALL) использоваться только как auth/probe source и provenance anchor;
- identical normalized metadata payload ДОЛЖЕН (SHALL) переиспользовать один canonical snapshot across compatible infobases;
- система НЕ ДОЛЖНА (SHALL NOT) считать одинаковый `config_version` достаточным условием reuse, если published OData metadata surface различается.

В дополнение к canonical shared snapshot markers система ДОЛЖНА (SHALL) уметь резолвить для выбранной ИБ отдельный database-scoped technical marker `config_generation_id` через существующий Designer path командой `GetConfigGenerationID`.

`config_generation_id`:
- ДОЛЖЕН (SHALL) возвращаться как отдельное поле read-model/provenance для выбранной ИБ, когда probe успешно выполнен;
- НЕ ДОЛЖЕН (SHALL NOT) становиться частью canonical shared snapshot identity в рамках этого change;
- НЕ ДОЛЖЕН (SHALL NOT) подменять `config_version`;
- НЕ ДОЛЖЕН (SHALL NOT) синтетически вычисляться из OData, `Database.version`, RAS или другого runtime source.

Ответ metadata catalog API ДОЛЖЕН (SHALL) возвращать resolved snapshot scope/version markers, provenance о последней ИБ, подтвердившей snapshot, и указывать, что snapshot shared/reused на configuration scope, если это применимо.

Если `config_generation_id` был успешно получен для выбранной ИБ, API ДОЛЖЕН (SHALL) возвращать его рядом с canonical snapshot markers как отдельный technical marker.

#### Scenario: Shared snapshot возвращается вместе с database-scoped config generation id
- **GIVEN** для выбранной ИБ доступен OData metadata snapshot
- **AND** Designer probe `GetConfigGenerationID` выполнен успешно
- **WHEN** UI запрашивает metadata catalog для этой ИБ
- **THEN** backend возвращает canonical shared snapshot markers
- **AND** response отдельно содержит resolved `config_generation_id`
- **AND** `config_generation_id` не подменяет `config_version`

#### Scenario: Отсутствующий Designer marker не подменяется synthetic значением
- **GIVEN** metadata snapshot для выбранной ИБ успешно резолвится
- **AND** Designer probe `GetConfigGenerationID` не выполнялся или завершился без результата
- **WHEN** UI запрашивает metadata catalog
- **THEN** API не вычисляет `config_generation_id` из `config_version`, OData или другого source
- **AND** canonical shared snapshot contract остаётся валидным без неявной подмены marker'а
