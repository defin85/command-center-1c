## MODIFIED Requirements
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
- позволять workflow/binding editor'ам выбирать resulting decision revision из first-class списка, а не требовать manual raw ids как primary UX.

`/workflows` ДОЛЖЕН (SHALL) использовать `/decisions` как reference catalog для выбора pinned decision revisions внутри workflow composition и НЕ ДОЛЖЕН (SHALL NOT) быть единственным decision CRUD surface.

#### Scenario: Аналитик импортирует legacy edge policy в decision resource
- **GIVEN** в topology edge существует legacy `document_policy`
- **WHEN** аналитик или оператор запускает import/migration action на `/decisions`
- **THEN** система создаёт или обновляет versioned decision resource с эквивалентным `document_policy` output
- **AND** canonical UI path использует action `Import legacy edge`
- **AND** action `Import raw JSON` остаётся explicit compatibility-only fallback, а не primary edge-migration path
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
