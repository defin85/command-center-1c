# pool-workflow-bindings Specification

## Purpose
TBD - created by archiving change refactor-12-workflow-centric-analyst-modeling. Update Purpose after archive.
## Requirements
### Requirement: Pools MUST поддерживать несколько workflow bindings в одном организационном контуре
Система ДОЛЖНА (SHALL) поддерживать `pool_workflow_binding` как versioned attachment между конкретным `pool` и pinned `binding_profile_revision_id`.

Attachment ДОЛЖЕН (SHALL) хранить как минимум:
- `pool_id`;
- `binding_id`;
- `status`;
- `effective_from`;
- `effective_to`;
- `direction`;
- `mode`;
- `binding_profile_id`;
- `binding_profile_revision_id`;
- read-only `binding_profile_revision_number` или эквивалентный display marker;
- `revision`;
- `created_by`;
- `updated_by`.

Один `pool` МОЖЕТ (MAY) иметь несколько одновременно активных attachment-ов, если они различимы по selector/effective period и не создают ambiguity.

Canonical store `pool_workflow_binding` ДОЛЖЕН (SHALL) оставаться единым source-of-truth для:
- list/detail/upsert/delete API pool-scoped attachment-ов;
- runtime attachment resolution;
- operator-facing read models и lineage.

Reusable поля binding logic (`workflow`, `decisions`, `parameters`, `role_mapping`) НЕ ДОЛЖНЫ (SHALL NOT) оставаться primary mutable payload attachment-а после rollout profile model; authoritative source-of-truth для них ДОЛЖЕН (SHALL) находиться в pinned `binding_profile_revision_id`.

`pool.metadata` НЕ ДОЛЖЕН (SHALL NOT) оставаться canonical или единственным runtime source-of-truth для workflow bindings после hardening cutover.

Snapshot binding provenance для конкретного запуска НЕ ДОЛЖЕН (SHALL NOT) читаться retroactively из mutable attachment row или latest profile revision после старта run; он ДОЛЖЕН (SHALL) фиксироваться в `PoolRun`/execution lineage на момент preview/create-run.

#### Scenario: Один pool использует две разные profile revision одновременно
- **GIVEN** один `pool` имеет attachment `top_down_services` на `binding_profile_revision_id services_v3_id`
- **AND** attachment `bottom_up_import` на `binding_profile_revision_id import_v2_id`
- **WHEN** оператор открывает список доступных схем для этого pool
- **THEN** интерфейс показывает оба attachment-а
- **AND** каждый attachment указывает на собственную pinned profile revision

#### Scenario: Обновление metadata пула не переписывает attachment и profile reference
- **GIVEN** для `pool` уже созданы canonical workflow attachment-ы
- **WHEN** оператор меняет `name`, `description` или другую pool metadata через pool upsert path
- **THEN** attachment-ы остаются доступными через dedicated binding API и runtime resolution
- **AND** pool upsert path не переписывает canonical attachment payload как побочный эффект

### Requirement: Pool workflow binding resolution MUST быть детерминированной и fail-closed
Система ДОЛЖНА (SHALL) резолвить attachment для запуска run явно по выбранному `pool_workflow_binding_id`.

Selector matching МОЖЕТ (MAY) использоваться только для UI prefill/assistive filtering pool-local attachment-ов и НЕ ДОЛЖЕН (SHALL NOT) silently подменять explicit runtime reference.

Если запрос запуска не содержит explicit attachment reference или ссылка указывает на attachment вне active/effective scope, система НЕ ДОЛЖНА (SHALL NOT) молча выбирать другой attachment.

#### Scenario: Отсутствие explicit attachment reference блокирует запуск run
- **GIVEN** для одного `pool` существует один или несколько активных attachment-ов
- **WHEN** оператор или внешний клиент пытается запустить run без `pool_workflow_binding_id`
- **THEN** система отклоняет запуск fail-closed
- **AND** возвращает machine-readable диагностику о missing explicit attachment reference

### Requirement: Pool workflow binding MUST предоставлять preview effective runtime projection
Система ДОЛЖНА (SHALL) предоставлять preview attachment-а до запуска, достаточный для понимания:
- какой pool attachment будет использован;
- на какую `binding_profile_revision_id` он pinned;
- какой workflow revision будет выполнен;
- какие decisions/parameters будут применены;
- какая concrete runtime projection будет собрана;
- какой lineage получит run.

#### Scenario: Binding preview показывает attachment provenance и pinned profile revision
- **GIVEN** аналитик или оператор открывает binding attachment перед запуском
- **WHEN** система строит preview
- **THEN** preview показывает pool attachment, pinned profile revision, workflow lineage и compiled projection summary
- **AND** пользователь видит, какой attachment и какая reusable profile revision будут исполнены до старта run

### Requirement: Pool workflow binding mutating MUST быть conflict-safe и audit-friendly
Система ДОЛЖНА (SHALL) предоставлять conflict-safe mutating semantics для `pool_workflow_binding`, достаточные для конкурентного редактирования и audit trail.

Concurrent update одного и того же binding НЕ ДОЛЖЕН (SHALL NOT) приводить к silent last-write-wins без явного conflict outcome.

Binding read contract ДОЛЖЕН (SHALL) возвращать server-managed `revision`, а single-binding mutating contract ДОЛЖЕН (SHALL) требовать этот `revision` для update/delete.

Для default workspace-save, который меняет несколько bindings одного `pool`, система ДОЛЖНА (SHALL) предоставлять collection-level atomic replace semantics через публичный contract `PUT /api/v2/pools/workflow-bindings/`.

`PUT /api/v2/pools/workflow-bindings/` ДОЛЖЕН (SHALL) принимать payload:
- `pool_id`;
- `expected_collection_etag`;
- полный целевой набор `workflow_bindings[]`.

`PUT /api/v2/pools/workflow-bindings/` ДОЛЖЕН (SHALL) возвращать:
- `pool_id`;
- полный canonical набор `workflow_bindings[]` после применения save;
- новый `collection_etag`.

`workflow_bindings[]` в collection read/save ДОЛЖЕН (SHALL) использовать один и тот же read-model shape. Для existing bindings payload содержит `binding_id` и `revision`, но collection conflict semantics этого change определяются только `expected_collection_etag`.

Collection replace path ДОЛЖЕН (SHALL):
- принимать полный целевой набор bindings для выбранного `pool`;
- вычислять create/update/delete diff на backend;
- применять изменения в одной транзакции;
- возвращать machine-readable `409 Conflict` при устаревшем `expected_collection_etag` с code `POOL_WORKFLOW_BINDING_COLLECTION_CONFLICT`;
- НЕ ДОЛЖЕН (SHALL NOT) оставлять частично применённые изменения, если любой элемент набора конфликтует или не проходит validation.

Существующие compatibility endpoint'ы `POST /api/v2/pools/workflow-bindings/upsert/`, `GET /api/v2/pools/workflow-bindings/{binding_id}/`, `DELETE /api/v2/pools/workflow-bindings/{binding_id}/` МОГУТ (MAY) оставаться compatibility surface, но default `/pools/catalog` workspace НЕ ДОЛЖЕН (SHALL NOT) использовать их как основную save semantics.

Другие mutating endpoint'ы для default workspace-save НЕ ДОЛЖНЫ (SHALL NOT) вводиться этим change.

#### Scenario: Конкурентное редактирование binding возвращает явный conflict
- **GIVEN** два оператора редактируют один и тот же `pool_workflow_binding`
- **AND** первый оператор уже зафиксировал новую ревизию binding
- **WHEN** второй оператор пытается сохранить устаревшее состояние
- **THEN** система возвращает machine-readable conflict
- **AND** canonical binding store сохраняет только выигравшее изменение

#### Scenario: Lineage snapshot сохраняет binding provenance независимо от последующих правок
- **GIVEN** оператор выполнил preview или create-run для binding с определёнными `decisions`, `parameters` и `workflow_revision`
- **WHEN** позже этот же binding изменяется в canonical store
- **THEN** inspect/read-model уже созданного run показывает исходный binding lineage snapshot
- **AND** provenance не реконструируется постфактум из новой mutable версии binding

#### Scenario: Workspace-save применяет create update delete как одну атомарную операцию
- **GIVEN** оператор в `/pools/catalog` изменил один binding, удалил второй и добавил третий в рамках одной save-сессии
- **WHEN** UI отправляет collection replace запрос с актуальным `expected_collection_etag`
- **THEN** backend фиксирует весь набор изменений как одну атомарную операцию
- **AND** response возвращает полностью обновлённую canonical collection и новый `collection_etag`
- **AND** последующий list/read-model возвращает то же canonical состояние

#### Scenario: Устаревший collection token блокирует save без partial apply
- **GIVEN** оператор открыл binding workspace и получил `collection_etag`
- **AND** другой оператор уже изменил binding collection того же `pool`
- **WHEN** первый оператор отправляет collection replace запрос со старым `expected_collection_etag`
- **THEN** backend возвращает machine-readable `409 Conflict`
- **AND** canonical binding collection остаётся в последнем согласованном состоянии без частичного применения запроса

### Requirement: Default binding workspace MUST использовать canonical binding collection без legacy fallback
Система ДОЛЖНА (SHALL) считать dedicated binding collection API единственным default read/write path для workflow bindings после workflow-centric hardening cutover.

Default collection read contract ДОЛЖЕН (SHALL) быть `GET /api/v2/pools/workflow-bindings/?pool_id=<uuid>` и возвращать:
- `pool_id`;
- полный canonical набор `workflow_bindings[]`;
- `collection_etag`.

`pool.metadata["workflow_bindings"]` МОЖЕТ (MAY) использоваться только в:
- `backfill_pool_workflow_bindings`;
- dedicated compatibility import tooling вне default `/pools/catalog` workspace;
- tests/fixtures, если они не подменяют shipped default behavior.

`pool.metadata["workflow_bindings"]` НЕ ДОЛЖЕН (SHALL NOT) silently гидрировать default binding workspace, operator read model или runtime path.

Если canonical binding collection пуста, а legacy metadata payload присутствует, shipped UI/operator path ДОЛЖЕН (SHALL) входить в blocking remediation state вместо неявного fallback.

#### Scenario: Legacy metadata не репопулирует binding workspace молча
- **GIVEN** у `pool` остался legacy `metadata.workflow_bindings`
- **AND** canonical binding collection для этого `pool` пуста
- **WHEN** оператор открывает default binding workspace на `/pools/catalog`
- **THEN** shipped path не читает bindings из legacy metadata автоматически
- **AND** интерфейс показывает пустое canonical состояние и blocking remediation warning
- **AND** normal workspace-save disabled до завершения explicit remediation вне shipped workspace
- **AND** runtime path не получает bindings через silent metadata fallback

#### Scenario: Workspace load возвращает collection etag для последующего atomic save
- **GIVEN** оператор открывает default binding workspace для `pool`
- **WHEN** UI читает canonical binding collection
- **THEN** response содержит полный canonical набор `workflow_bindings[]`
- **AND** response содержит `collection_etag`
- **AND** этот `collection_etag` используется в следующем default workspace-save

### Requirement: Pool workflow binding decisions MUST выступать именованными publication slots
Система ДОЛЖНА (SHALL) хранить в `pool_workflow_binding.decisions[]`:
- `decision_key` как identity reusable decision revision/resource;
- `slot_key` как canonical binding slot name для policy-bearing decisions внутри binding.

Binding МОЖЕТ (MAY) pin-ить несколько publication slot decisions одновременно.

`slot_key` ДОЛЖЕН (SHALL) быть уникальным в пределах одного binding для policy-bearing decisions.

Topology edge selector `edge.metadata.document_policy_key` ДОЛЖЕН (SHALL) резолвиться только против `slot_key`, pinned в выбранном binding.

#### Scenario: Один binding pin-ит несколько publication slots
- **GIVEN** binding содержит policy decisions с `decision_key=document_policy`
- **AND** эти refs имеют `slot_key=sale` и `slot_key=purchase`
- **WHEN** оператор открывает binding preview
- **THEN** preview показывает оба slot'а как часть effective projection
- **AND** runtime может использовать их независимо на разных topology edges

#### Scenario: Duplicate slot_key отклоняется fail-closed
- **GIVEN** оператор или backend пытается сохранить binding, где два policy-bearing decision refs имеют одинаковый `slot_key`
- **WHEN** выполняется validation binding contract
- **THEN** запрос отклоняется fail-closed
- **AND** canonical binding store не сохраняет ambiguous slot mapping

### Requirement: Binding workspace UI MUST быть analyst-friendly slot-oriented surface
Система ДОЛЖНА (SHALL) предоставлять binding workspace как analyst-friendly surface для управления named publication slots, а не как low-level editor raw decision refs.

Binding UI ДОЛЖЕН (SHALL):
- показывать `slot_key` как primary slot identity;
- показывать pinned decision revision для каждого slot;
- показывать coverage slot'а относительно topology edge selectors выбранного пула;
- явно показывать missing или ambiguous slot coverage до preview/create-run.

Raw identifiers (`decision_table_id`, внутренние ids) МОГУТ (MAY) оставаться в advanced/read-only diagnostics, но НЕ ДОЛЖНЫ (SHALL NOT) быть primary editing model.

#### Scenario: Аналитик видит binding как набор named slots, а не raw ids
- **GIVEN** оператор или аналитик открыл binding workspace
- **WHEN** UI рендерит decisions section
- **THEN** основная модель экрана показывает named slots и pinned revisions
- **AND** ручной ввод raw decision ids не является основным способом редактирования

#### Scenario: Binding workspace показывает непокрытые topology selectors до preview
- **GIVEN** активная topology содержит edge с `document_policy_key=return`
- **AND** binding не содержит matching slot `return`
- **WHEN** аналитик открывает binding workspace
- **THEN** UI показывает missing coverage до запуска preview
- **AND** normal save/run path блокируется или помечается blocking remediation diagnostic

#### Scenario: Binding workspace показывает ambiguous coverage context отдельно от missing slot
- **GIVEN** topology coverage зависит от binding context, который не выбран детерминированно
- **WHEN** аналитик открывает binding workspace
- **THEN** UI показывает ambiguous coverage context как отдельное состояние
- **AND** не смешивает его с missing `slot_key` внутри выбранного binding

### Requirement: Pool attachment MUST оставаться pool-local activation layer без local logic overrides в MVP
Система ДОЛЖНА (SHALL) трактовать `pool_workflow_binding` как pool-local activation layer.

В MVP attachment МОЖЕТ (MAY) редактировать только:
- `status`;
- selector scope;
- `effective_from/effective_to`;
- reference на `binding_profile_revision`;
- optional display/provenance metadata, не влияющую на runtime logic.

Attachment НЕ ДОЛЖЕН (SHALL NOT) локально переопределять:
- workflow revision;
- publication slot map;
- parameters;
- role mapping.

Для pool-specific вариации reusable схемы система ДОЛЖНА (SHALL) требовать новую `binding_profile_revision` или отдельный `binding_profile`.

#### Scenario: Оператор не может quietly изменить slot map только для одного pool attachment
- **GIVEN** attachment pinned на reusable profile revision
- **WHEN** оператор пытается изменить workflow/slot logic только внутри attachment-а
- **THEN** система отклоняет такой mutate path или направляет к созданию новой profile revision
- **AND** существующая reusable profile revision остаётся неизменной

#### Scenario: Attachment на deactivated profile revision остаётся читаемым, но не переиспользуется для нового attach
- **GIVEN** attachment уже pinned на `binding_profile_revision_id`
- **AND** source profile позже деактивирован в catalog
- **WHEN** оператор читает attachment collection или inspect lineage
- **THEN** attachment остаётся видимым и читаемым с profile lifecycle warning
- **AND** новый attach/re-attach на этот deactivated profile через default path недоступен

