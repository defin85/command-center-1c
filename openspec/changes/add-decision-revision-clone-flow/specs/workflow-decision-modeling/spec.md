## MODIFIED Requirements
### Requirement: Decision resources MUST быть first-class authoring surface для workflow-centric document rules
Система ДОЛЖНА (SHALL) предоставлять first-class authoring/read-model surface для versioned decision resources, используемых workflow-centric `document_policy`.

Frontend surface ДОЛЖЕН (SHALL):
- использовать отдельный route `/decisions` как canonical decision lifecycle surface;
- поддерживать lifecycle `list/detail/create/clone/revise/archive-deactivate` без ручного API-клиента;
- создавать, клонировать и ревизировать decision resources без ручного API-клиента;
- импортировать legacy `edge.metadata.document_policy` в decision resource revision;
- использовать shared configuration-scoped metadata snapshots для document-policy builder/preview;
- сохранять и показывать resolved metadata snapshot provenance/compatibility markers для `document_policy` revisions;
- показывать produced `document_policy` output и pinned provenance;
- позволять workflow/binding editor'ам выбирать resulting decision revision из first-class списка, а не требовать manual raw ids как primary UX;
- предоставлять guided rollover flow для создания новой `decision_revision` из существующей revision под metadata context выбранной ИБ;
- позволять аналитику использовать revision вне default compatible selection как explicit source для rollover flow без превращения этой revision в default candidate для новых pins;
- явно показывать `source revision`, `target database` и resolved target metadata context до публикации новой revision;
- предоставлять отдельный clone flow для публикации нового independent decision resource из существующей revision без reuse `parent_version_id`.

`/workflows` ДОЛЖЕН (SHALL) использовать `/decisions` как reference catalog для выбора pinned decision revisions внутри workflow composition и НЕ ДОЛЖЕН (SHALL NOT) быть единственным decision CRUD surface.

#### Scenario: Аналитик клонирует revision в новый independent decision resource
- **GIVEN** аналитик выбрал существующую `document_policy` revision в `/decisions`
- **WHEN** он запускает `Clone selected revision`
- **THEN** UI открывает editor с policy из source revision как editable seed
- **AND** `decision_table_id` доступен для редактирования как новый identity cloned resource
- **AND** publish отправляет новый create payload без `parent_version_id`
- **AND** resulting revision публикуется как independent decision resource, а не как новая revision исходного `decision_table_id`

#### Scenario: Clone flow не подменяет rollover semantics
- **GIVEN** аналитик сравнивает actions `Rollover selected revision` и `Clone selected revision`
- **WHEN** он открывает соответствующие editor flows
- **THEN** rollover явно создаёт новую revision существующего resource с `parent_version_id`
- **AND** clone явно создаёт новый independent resource без `parent_version_id`
- **AND** UI copy не допускает двусмысленности между этими режимами

#### Scenario: Clone flow не перепривязывает existing consumers автоматически
- **GIVEN** source revision уже pinned в workflow definitions или bindings
- **WHEN** аналитик успешно публикует cloned decision resource
- **THEN** существующие workflow definitions, workflow bindings и runtime projections не обновляются автоматически
- **AND** clone появляется как отдельный pin candidate только после явного выбора пользователем
