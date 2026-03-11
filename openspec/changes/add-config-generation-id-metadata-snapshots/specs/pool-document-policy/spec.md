## MODIFIED Requirements
### Requirement: Document policy authoring MUST использовать configuration-scoped metadata snapshots
Система ДОЛЖНА (SHALL) валидировать и preview'ить новый `document_policy` против canonical metadata snapshot, разделяемого между ИБ с совместимой configuration signature.

Система НЕ ДОЛЖНА (SHALL NOT) требовать отдельный database-local snapshot для каждого policy, если compatible canonical snapshot уже существует.

Система НЕ ДОЛЖНА (SHALL NOT) silently reuse snapshot только по совпадению `config_version`, если metadata surface differs.

Каждая versioned decision revision, materializing `document_policy`, ДОЛЖНА (SHALL) сохранять resolved metadata snapshot provenance/compatibility markers, чтобы builder, preview и binding selection использовали один и тот же auditable configuration-scoped context.

Если для выбранной ИБ в момент resolution доступен Designer-derived `config_generation_id`, он ДОЛЖЕН (SHALL) сохраняться в decision metadata context как отдельный technical provenance marker.

`config_generation_id` в этом change:
- НЕ ДОЛЖЕН (SHALL NOT) подменять `config_version`;
- НЕ ДОЛЖЕН (SHALL NOT) трактоваться как canonical shared snapshot identity marker;
- МОЖЕТ (MAY) отсутствовать у legacy revisions или у revisions, созданных без успешного Designer probe.

#### Scenario: Policy builder переиспользует shared metadata snapshot для другой ИБ той же конфигурации
- **GIVEN** canonical metadata snapshot уже существует для configuration signature
- **AND** оператор или аналитик выбирает другую ИБ с той же configuration signature
- **WHEN** открывается builder или preview в `/decisions`
- **THEN** UI/backend используют тот же canonical metadata snapshot
- **AND** не требуют отдельный manual refresh только из-за другого `database_id`

#### Scenario: Diverged metadata surface блокирует reuse в policy builder
- **GIVEN** выбранная ИБ имеет ту же `config_version`, но другой published metadata payload
- **WHEN** система пытается резолвить metadata snapshot для `/decisions`
- **THEN** reuse чужого canonical snapshot не происходит
- **AND** UI получает новый resolved snapshot scope или fail-closed indication о несовместимой metadata surface

#### Scenario: Decision revision сохраняет config generation id отдельно от config version
- **GIVEN** аналитик сохраняет новый `document_policy` через `/decisions`
- **AND** resolved metadata context содержит `config_generation_id`, полученный через Designer probe выбранной ИБ
- **WHEN** backend публикует resulting decision revision
- **THEN** revision сохраняет `config_generation_id` как отдельный provenance marker
- **AND** `config_version` остаётся отдельным полем и не подменяется generation id
