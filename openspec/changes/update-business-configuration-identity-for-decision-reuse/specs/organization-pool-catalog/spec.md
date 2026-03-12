## MODIFIED Requirements
### Requirement: Metadata catalog retrieval MUST использовать persisted snapshot в БД и Redis только как ускоритель
Система ДОЛЖНА (SHALL) хранить нормализованный metadata catalog как canonical persisted snapshot, пригодный для reuse между несколькими ИБ в рамках одной tenant-scoped business configuration identity, а не как database-local current snapshot по `database_id` alone.

Canonical metadata snapshot identity ДОЛЖНА (SHALL) включать только:
- `config_name`;
- `config_version`.

`config_name` и `config_version` в рамках этого requirement:
- ДОЛЖНЫ (SHALL) описывать business-level identity конфигурации;
- НЕ ДОЛЖНЫ (SHALL NOT) вычисляться из `Database.base_name`, `Database.infobase_name`, `Database.name` или `Database.version`;
- ДОЛЖНЫ (SHALL) резолвиться из root configuration properties через существующий Designer path или эквивалентный root configuration export path.

`config_name` ДОЛЖЕН (SHALL) резолвиться в порядке:
- root configuration `Synonym` для локали `ru`;
- первый доступный synonym entry;
- root configuration `Name`.

`config_version` ДОЛЖЕН (SHALL) резолвиться из root configuration `Version`.

Canonical snapshot identity НЕ ДОЛЖНА (SHALL NOT) включать:
- `database_id`;
- имя ИБ;
- `metadata_hash`;
- `extensions_fingerprint`;
- `config_generation_id`.

Read/refresh path МОЖЕТ (MAY) стартовать от выбранной ИБ, но:
- конкретная ИБ ДОЛЖНА (SHALL) использоваться только как auth/probe source и provenance anchor;
- ИБ с одинаковыми `config_name + config_version` ДОЛЖНЫ (SHALL) переиспользовать один canonical business-scoped snapshot;
- различие published OData metadata surface НЕ ДОЛЖНО (SHALL NOT) создавать отдельную compatibility identity.

`metadata_hash`, `extensions_fingerprint` и `config_generation_id` ДОЛЖНЫ (SHALL) сохраняться и возвращаться как provenance/diagnostics markers publication state.

Если выбранная ИБ отличается по published metadata surface от canonical business-scoped snapshot, API ДОЛЖЕН (SHALL):
- возвращать canonical business-scoped snapshot;
- сохранять provenance последней ИБ, подтвердившей этот snapshot;
- возвращать явную diagnostics indication publication drift для выбранной ИБ.

#### Scenario: Две ИБ с одинаковой конфигурацией и релизом переиспользуют один snapshot независимо от имени ИБ
- **GIVEN** в tenant есть две ИБ с разными именами
- **AND** root configuration properties у них дают одинаковые `config_name` и `config_version`
- **WHEN** оператор запрашивает metadata catalog для второй ИБ после refresh первой
- **THEN** backend возвращает тот же canonical business-scoped snapshot
- **AND** имя ИБ не участвует в compatibility identity

#### Scenario: Одинаковая business identity переиспользует snapshot при publication drift
- **GIVEN** две ИБ имеют одинаковые `config_name` и `config_version`
- **AND** состав опубликованных через OData metadata objects у них различается
- **WHEN** backend refresh'ит metadata catalog для второй ИБ
- **THEN** система не создаёт новую compatibility identity только из-за отличия `metadata_hash`
- **AND** response содержит diagnostics indication publication drift
- **AND** provenance указывает, какая ИБ подтвердила canonical business-scoped snapshot

#### Scenario: Business identity конфигурации снимается из root configuration properties
- **GIVEN** backend выполняет Designer-based probe/export для выбранной ИБ
- **WHEN** он резолвит configuration identity
- **THEN** `config_name` берётся из root configuration `Synonym` или fallback `Name`
- **AND** `config_version` берётся из root configuration `Version`
- **AND** identity не зависит от имени ИБ
