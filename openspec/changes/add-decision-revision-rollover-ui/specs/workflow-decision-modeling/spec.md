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
- показывать produced `document_policy` output и pinned provenance;
- позволять workflow/binding editor'ам выбирать resulting decision revision из first-class списка, а не требовать manual raw ids как primary UX;
- предоставлять guided rollover flow для создания новой `decision_revision` из существующей revision под metadata context выбранной ИБ;
- позволять аналитику использовать revision вне default compatible selection как explicit source для rollover flow без превращения этой revision в default candidate для новых pins;
- явно показывать `source revision`, `target database` и resolved target metadata context до публикации новой revision.

`/workflows` ДОЛЖЕН (SHALL) использовать `/decisions` как reference catalog для выбора pinned decision revisions внутри workflow composition и НЕ ДОЛЖЕН (SHALL NOT) быть единственным decision CRUD surface.

#### Scenario: Аналитик импортирует legacy edge policy в decision resource
- **GIVEN** в topology edge существует legacy `document_policy`
- **WHEN** аналитик или оператор запускает import/migration action на `/decisions`
- **THEN** система создаёт или обновляет versioned decision resource с эквивалентным `document_policy` output
- **AND** UI возвращает resulting `decision_table_id` и `decision_revision` для pin в workflow/binding

#### Scenario: Workflow и binding editor используют список decision revisions
- **GIVEN** в tenant уже есть decision resource revisions для `document_policy`
- **WHEN** аналитик редактирует workflow или оператор редактирует binding
- **THEN** UI выбирает decision revision из списка/search surface
- **AND** manual raw id entry не является primary authoring path

#### Scenario: Workflow composer использует `/decisions` и `/templates` как разные reference-каталоги
- **GIVEN** аналитик открыл `/workflows`
- **WHEN** он добавляет operation node или decision-bound rule
- **THEN** operation building blocks выбираются из template catalog
- **AND** pinned decision revisions выбираются из route `/decisions`
- **AND** `/workflows` остаётся composition surface, а не decision CRUD surface

#### Scenario: `/decisions` показывает configuration-scoped metadata provenance для policy authoring
- **GIVEN** аналитик открывает decision resource для `document_policy`
- **WHEN** UI подгружает metadata-aware builder context
- **THEN** экран показывает resolved configuration-scoped snapshot markers
- **AND** provenance не ограничивается только `database_id`, если snapshot shared между несколькими ИБ

#### Scenario: Decision revision сохраняет auditable compatibility context
- **GIVEN** аналитик публикует revision для `document_policy`
- **WHEN** revision появляется в `/decisions` и в binding selector
- **THEN** UI/read-model показывают resolved metadata snapshot provenance/compatibility markers этой revision
- **AND** дальнейшие compatibility checks опираются на сохранённый configuration-scoped context, а не на mutable latest database-local snapshot

#### Scenario: Аналитик архивирует или деактивирует устаревший decision resource без потери lineage
- **GIVEN** decision resource для `document_policy` больше не должен использоваться для новых bindings
- **WHEN** аналитик выполняет archive/deactivate action в decision lifecycle UI
- **THEN** decision resource исчезает из default selection для новых workflow/binding edits
- **AND** historical lineage и уже pinned revisions остаются читаемыми для diagnostics/audit

#### Scenario: Аналитик создаёт новую revision под новый релиз ИБ из старой revision
- **GIVEN** аналитик выбрал target database с новым metadata context
- **AND** подходящая compatible revision отсутствует или аналитик осознанно хочет взять revision предыдущего релиза как основу
- **WHEN** он запускает guided rollover flow из существующей revision в `/decisions`
- **THEN** UI открывает editor с policy из source revision, `parent_version_id` source revision и target metadata context выбранной ИБ
- **AND** экран явно показывает, какая revision используется как source и для какой ИБ публикуется новая revision

#### Scenario: Revision вне target compatible set доступна как source, но не как default pin candidate
- **GIVEN** существующая revision относится к предыдущему релизу или иначе не входит в target compatible selection выбранной ИБ
- **WHEN** аналитик просматривает список revisions в default compatible режиме
- **THEN** эта revision остаётся вне default ready-to-pin списка
- **AND** может быть выбрана только через explicit diagnostics/source-selection flow для создания новой revision

#### Scenario: Rollover flow не перепривязывает consumers автоматически
- **GIVEN** аналитик успешно опубликовал новую revision через rollover flow
- **WHEN** публикация завершена
- **THEN** система возвращает новую pinned `decision_revision` как отдельный результат authoring
- **AND** существующие workflow definitions, workflow bindings и runtime projections не обновляются автоматически только из-за публикации новой revision
