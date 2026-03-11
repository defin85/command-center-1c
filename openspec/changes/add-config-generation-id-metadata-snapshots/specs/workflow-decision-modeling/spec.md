## MODIFIED Requirements
### Requirement: Decision resources MUST быть first-class authoring surface для workflow-centric document rules
Система ДОЛЖНА (SHALL) предоставлять first-class authoring/read-model surface для versioned decision resources, используемых workflow-centric `document_policy`.

Frontend surface ДОЛЖЕН (SHALL):
- использовать отдельный route `/decisions` как canonical decision lifecycle surface;
- поддерживать lifecycle `list/detail/create/revise/archive-deactivate` без ручного API-клиента;
- создавать и ревизировать decision resources без ручного API-клиента;
- импортировать legacy `edge.metadata.document_policy` в decision resource revision;
- использовать shared configuration-scoped metadata snapshots для document-policy builder/preview;
- сохранять и показывать resolved metadata snapshot provenance/compatibility markers для `document_policy` revisions;
- показывать `config_generation_id` как отдельный technical marker, если он доступен для выбранной ИБ;
- показывать produced `document_policy` output и pinned provenance;
- позволять workflow/binding editor'ам выбирать resulting decision revision из first-class списка, а не требовать manual raw ids как primary UX.

`/workflows` ДОЛЖЕН (SHALL) использовать `/decisions` как reference catalog для выбора pinned decision revisions внутри workflow composition и НЕ ДОЛЖЕН (SHALL NOT) быть единственным decision CRUD surface.

`/decisions` НЕ ДОЛЖЕН (SHALL NOT) переименовывать `config_generation_id` в `config_version` или скрывать resolved generation marker только потому, что display field `config_version` пустой.

#### Scenario: Аналитик импортирует legacy edge policy в decision resource
- **GIVEN** в topology edge существует legacy `document_policy`
- **WHEN** аналитик или оператор запускает import/migration action на `/decisions`
- **THEN** система создаёт или обновляет versioned decision resource с эквивалентным `document_policy` output
- **AND** UI возвращает resulting `decision_table_id` и `decision_revision` для pin в workflow/binding

#### Scenario: `/decisions` показывает config generation id отдельно от config version
- **GIVEN** аналитик открыл decision resource для `document_policy`
- **AND** для выбранной ИБ resolved `config_generation_id`, а `config_version` пустой или отсутствует
- **WHEN** UI подгружает metadata-aware builder context
- **THEN** экран отдельно показывает `Config generation ID`
- **AND** пустой `Config version` не скрывает resolved generation marker

#### Scenario: Decision revision сохраняет auditable compatibility context
- **GIVEN** аналитик публикует revision для `document_policy`
- **WHEN** revision появляется в `/decisions` и в binding selector
- **THEN** UI/read-model показывают resolved metadata snapshot provenance/compatibility markers этой revision, включая `config_generation_id` при наличии
- **AND** дальнейшие compatibility checks опираются на сохранённый configuration-scoped context, а не на mutable latest database-local snapshot
