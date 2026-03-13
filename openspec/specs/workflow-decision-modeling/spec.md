# workflow-decision-modeling Specification

## Purpose
TBD - created by archiving change refactor-12-workflow-centric-analyst-modeling. Update Purpose after archive.
## Requirements
### Requirement: Workflow definitions MUST быть analyst-facing библиотекой схем распределения
Система ДОЛЖНА (SHALL) использовать versioned `workflow definition` как primary analyst-facing артефакт для описания схем распределения и публикации, переиспользуемых между несколькими `pool`.

Workflow definition ДОЛЖЕН (SHALL) поддерживать:
- доменные стадии и task types;
- pinned references на templates, decisions и subworkflows;
- role-aware orchestration без прямой привязки ко всем concrete organization id в самом definition;
- reusable versioned authoring независимо от конкретного `pool`.

#### Scenario: Один workflow definition переиспользуется несколькими pool bindings
- **GIVEN** аналитик создал workflow definition `services_publication_v3`
- **AND** два разных `pool` используют этот workflow через собственные bindings
- **WHEN** оператор просматривает доступные схемы для обоих pool
- **THEN** система показывает одну и ту же workflow revision как общий analyst-authored source
- **AND** runtime bindings и параметры для каждого pool остаются независимыми

### Requirement: Workflow modeling MUST разделять orchestration и decisions
Система ДОЛЖНА (SHALL) поддерживать явный decision layer для business rules, который вызывается из workflow definition как first-class reference, а не кодируется преимущественно через произвольные inline `condition` выражения.

Decision resource ДОЛЖЕН (SHALL) быть versioned, иметь explicit input/output contract и поддерживать pinned binding из workflow.

#### Scenario: Decision node выбирает вариант документной цепочки без inline business logic
- **GIVEN** workflow содержит шаг выбора варианта публикации документов
- **WHEN** аналитик настраивает этот шаг
- **THEN** шаг ссылается на versioned decision resource
- **AND** major business rules не хранятся как неструктурированная строка в edge condition

### Requirement: Workflow modeling MUST поддерживать reusable subworkflows с pinned binding
Система ДОЛЖНА (SHALL) поддерживать reusable subworkflow/call-activity semantics для повторного использования общих process fragments без копирования полного graph.

Binding subworkflow ДОЛЖЕН (SHALL) поддерживать pinned revision и explicit input/output mapping.

Runtime ДОЛЖЕН (SHALL) исполнять reusable subworkflow по pinned revision metadata из `subworkflow_ref(binding_mode="pinned_revision")` для analyst-authored workflow surfaces.

Runtime НЕ ДОЛЖЕН (SHALL NOT) silently использовать compatibility field `subworkflow_id` вместо pinned revision, если `subworkflow_ref` уже задан.

При missing/drifted/conflicting pinned metadata система ДОЛЖНА (SHALL) завершать subworkflow resolution fail-closed и возвращать lineage/diagnostics, указывающие на проблемный pinned binding.

Pinned subworkflow provenance ДОЛЖЕН (SHALL) фиксироваться в run lineage/diagnostics на момент исполнения и НЕ ДОЛЖЕН (SHALL NOT) реконструироваться постфактум из mutable latest revision.

#### Scenario: Workflow вызывает pinned subworkflow revision
- **GIVEN** analyst workflow использует reusable subprocess `approval_gate`
- **WHEN** definition сохраняется с pinned binding на revision `7`
- **THEN** runtime lineage фиксирует именно revision `7`
- **AND** последующие изменения latest revision не меняют уже сохранённый binding молча

#### Scenario: Конфликт между subworkflow_id и pinned subworkflow_ref отклоняется fail-closed
- **GIVEN** workflow node содержит `subworkflow_ref(binding_mode="pinned_revision")`
- **AND** compatibility field `subworkflow_id` указывает на другую revision или другой workflow
- **WHEN** runtime пытается исполнить subworkflow
- **THEN** система отклоняет выполнение fail-closed
- **AND** не подменяет pinned binding compatibility-полем молча

#### Scenario: Run lineage фиксирует исполненную pinned subworkflow revision
- **GIVEN** analyst-authored workflow содержит reusable subworkflow с pinned revision
- **WHEN** runtime успешно исполняет этот subworkflow
- **THEN** run lineage/diagnostics сохраняет исполненную subworkflow revision как provenance snapshot
- **AND** последующее изменение latest revision не меняет уже сохранённую диагностику

### Requirement: Workflow catalog MUST разделять user-authored definitions и system-managed runtime projections
Система ДОЛЖНА (SHALL) визуально и контрактно разделять:
- user-authored workflow definitions;
- system-managed/generated runtime workflow projections.

Generated runtime workflows НЕ ДОЛЖНЫ (SHALL NOT) отображаться в analyst-facing workflow catalog как обычные редактируемые definitions.

#### Scenario: Analyst-facing `/workflows` не смешивает authored definitions и generated runtime graphs
- **GIVEN** в системе существуют analyst-authored workflows и system-managed runtime projections
- **WHEN** пользователь открывает analyst-facing workflow catalog
- **THEN** список по умолчанию показывает только authored definitions
- **AND** generated runtime projections доступны только в отдельном read-only diagnostic surface

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

### Requirement: `/decisions` MUST hand off metadata management to `/databases`
Система ДОЛЖНА (SHALL) сохранять `/decisions` как metadata-aware decision lifecycle surface, но НЕ ДОЛЖНА (SHALL NOT) превращать его в primary operator surface для configuration profile или metadata snapshot maintenance.

`/decisions` ДОЛЖЕН (SHALL):
- показывать resolved target metadata context в read-only виде;
- различать проблемы business identity/profile и проблемы current snapshot;
- при отсутствии или устаревании metadata context давать явный CTA/handoff в `/databases`.

Система НЕ ДОЛЖНА (SHALL NOT) ограничиваться generic сообщением о необходимости "reload database-specific metadata" без указания canonical management surface.

#### Scenario: Metadata context unavailable -> UI направляет в `/databases`
- **GIVEN** аналитик открыл `/decisions` для базы, у которой отсутствует current metadata context
- **WHEN** UI блокирует edit/deactivate/rollover fail-closed
- **THEN** сообщение объясняет, что metadata management выполняется через `/databases`
- **AND** аналитик получает явный CTA/handoff вместо неадресного reload-сообщения

#### Scenario: `/decisions` остаётся consumer surface, а не mutate hub
- **GIVEN** аналитик просматривает metadata context выбранной ИБ в `/decisions`
- **WHEN** ему требуется metadata maintenance action
- **THEN** экран использует `/databases` как canonical handoff
- **AND** `/decisions` не становится primary местом для refresh/re-verify controls

