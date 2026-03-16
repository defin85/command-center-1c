## MODIFIED Requirements

### Requirement: Pool catalog workflow bindings MUST использовать isolated attachment workspace и canonical CRUD
Система ДОЛЖНА (SHALL) управлять workflow bindings на `/pools/catalog` через dedicated attachment workspace и dedicated attachment endpoints, backed by the same canonical store, который использует runtime resolution.

`/pools/catalog` ДОЛЖЕН (SHALL) трактовать `pool_workflow_binding` как pool-scoped attachment к pinned `binding_profile_revision_id`, а не как primary inline authoring surface для reusable workflow/slot logic.

Pool upsert contract НЕ ДОЛЖЕН (SHALL NOT) нести canonical attachment payload и НЕ ДОЛЖЕН (SHALL NOT) переписывать attachment state как side effect редактирования базовых полей пула.

Attachment read path ДОЛЖЕН (SHALL) возвращать server-managed `revision`, pinned `binding_profile_revision_id`, optional display `binding_profile_revision_number` и достаточный read-only summary resolved profile для lineage visibility и topology slot coverage diagnostics.

UI ДОЛЖЕН (SHALL) разделять:
- mutating операции над базовыми полями `pool`;
- mutating операции над `pool_workflow_binding` как attachment;
- authoring reusable binding profile revisions в dedicated profile catalog.

Для default multi-attachment save UI ДОЛЖЕН (SHALL) использовать публичный collection-level atomic save contract `PUT /api/v2/pools/workflow-bindings/` поверх canonical attachment store и НЕ ДОЛЖЕН (SHALL NOT) полагаться на последовательность client-side `upsert/delete`, которая допускает partial apply.

Default collection-save UI ДОЛЖЕН (SHALL) использовать `collection_etag` / `expected_collection_etag` как единственный workspace concurrency contract. Per-attachment `revision` НЕ ДОЛЖЕН (SHALL NOT) использоваться как primary conflict token для default multi-binding save.

При collection conflict UI ДОЛЖЕН (SHALL) сохранять введённые данные формы, показывать причину конфликта и предлагать reload canonical collection без потери локального edit state.

Если оператору требуется изменить reusable workflow/slot logic pinned profile revision, `/pools/catalog` НЕ ДОЛЖЕН (SHALL NOT) quietly редактировать эту логику inline внутри attachment workspace и ДОЛЖЕН (SHALL) направлять на отдельный route `/pools/binding-profiles`.

#### Scenario: Сохранение базовых полей пула не переписывает workflow attachments
- **GIVEN** оператор редактирует `code` или `name` пула в `/pools/catalog`
- **AND** у пула уже есть active workflow attachments
- **WHEN** оператор сохраняет только базовые поля пула
- **THEN** UI использует pool upsert path без canonical attachment payload
- **AND** существующие workflow attachments не теряются и не переписываются

#### Scenario: Attachment editor использует тот же canonical CRUD, что и runtime
- **GIVEN** оператор добавляет attachment или меняет pinned profile revision в `/pools/catalog`
- **WHEN** изменение сохраняется
- **THEN** UI читает и сохраняет canonical collection через `GET/PUT /api/v2/pools/workflow-bindings/`
- **AND** следующий create-run/read-model видит это же изменение без дополнительного metadata sync шага

#### Scenario: Workspace направляет в profile catalog для правки reusable логики
- **GIVEN** оператор открыл attachment в `/pools/catalog`
- **AND** attachment pinned на existing `binding_profile_revision`
- **WHEN** оператору нужно изменить workflow/slot mapping этой схемы
- **THEN** UI направляет его на `/pools/binding-profiles`
- **AND** attachment workspace сохраняет только pool-local scope и profile reference

#### Scenario: Stale collection etag в catalog editor возвращает conflict без потери формы
- **GIVEN** оператор редактирует workflow attachments в `/pools/catalog`
- **AND** другой оператор уже сохранил новую canonical collection
- **WHEN** первый оператор пытается отправить состояние со старым `expected_collection_etag`
- **THEN** backend возвращает machine-readable conflict по `expected_collection_etag`
- **AND** UI сохраняет введённые данные для повторной попытки
