## MODIFIED Requirements
### Requirement: Document policy authoring MUST использовать configuration-scoped metadata snapshots
Система ДОЛЖНА (SHALL) валидировать и preview'ить новый `document_policy` против canonical metadata snapshot, разделяемого между ИБ с одинаковой business configuration identity.

Система НЕ ДОЛЖНА (SHALL NOT) требовать отдельный database-local snapshot для каждого policy, если shared canonical snapshot уже существует для той же пары `config_name + config_version`.

Compatibility `document_policy` revision ДОЛЖНА (SHALL) определяться только по:
- `config_name`;
- `config_version`.

Система НЕ ДОЛЖНА (SHALL NOT) считать hard incompatibility marker'ами:
- имя ИБ;
- `metadata_hash`;
- `extensions_fingerprint`;
- `config_generation_id`.

Каждая versioned decision revision, materializing `document_policy`, ДОЛЖНА (SHALL) сохранять provenance/diagnostics markers metadata resolution, включая `metadata_hash`, `extensions_fingerprint` и `config_generation_id` при наличии, но эти markers НЕ ДОЛЖНЫ (SHALL NOT) блокировать reuse revision между ИБ одной и той же business configuration identity.

Если publication drift обнаружен для выбранной ИБ, builder/preview ДОЛЖЕН (SHALL):
- сохранять business-compatible reuse revision;
- показывать drift как diagnostics/warning;
- не переводить revision в incompatible только из-за drift.

#### Scenario: Policy builder переиспользует decision revision между ИБ одной конфигурации
- **GIVEN** canonical metadata snapshot и `document_policy` revision уже существуют для `config_name + config_version`
- **AND** аналитик выбирает другую ИБ с той же business configuration identity
- **WHEN** открывается builder, preview или binding selection
- **THEN** система использует тот же shared canonical snapshot и ту же compatible revision
- **AND** не требует отдельную revision только из-за другого имени ИБ

#### Scenario: Разный metadata hash не блокирует reuse decision revision
- **GIVEN** stored decision revision и выбранная ИБ совпадают по `config_name + config_version`
- **AND** их `metadata_hash` различается
- **WHEN** система оценивает compatibility для `/decisions` или binding selection
- **THEN** revision остаётся compatible
- **AND** различие `metadata_hash` показывается как diagnostics/warning
- **AND** revision не скрывается из default compatible selection

#### Scenario: Decision revision сохраняет publication markers как provenance, а не как compatibility key
- **GIVEN** аналитик публикует новый `document_policy`
- **WHEN** backend сохраняет resulting decision revision
- **THEN** revision сохраняет resolved `metadata_hash`, `extensions_fingerprint` и `config_generation_id` при наличии
- **AND** последующий compatibility check использует для reuse только `config_name + config_version`
