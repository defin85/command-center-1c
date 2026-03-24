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
Система ДОЛЖНА (SHALL) валидировать reusable execution-pack coverage относительно structural slot contract выбранного pool topology.

Execution pack МОЖЕТ (MAY) реализовывать named slots через decision refs, но НЕ ДОЛЖЕН (SHALL NOT) silently расширять или переопределять structural slot namespace, пришедший из topology-template layer или concrete topology contract.

#### Scenario: Attachment блокируется при несовместимом execution pack coverage
- **GIVEN** structural topology contract требует slots `sale` и `receipt`
- **AND** выбранная execution-pack revision реализует только `sale`
- **WHEN** оператор attach'ит или preview'ит этот binding
- **THEN** система возвращает missing coverage diagnostics
- **AND** несовместимость не маскируется fallback логикой

#### Scenario: Extra execution slot не становится structural slot автоматически
- **GIVEN** execution-pack revision реализует `sale`, `receipt` и `internal_override`
- **AND** structural topology contract не содержит `internal_override`
- **WHEN** система оценивает compatibility attachment-а
- **THEN** extra slot не materialize'ится как новый structural topology slot
- **AND** оператор получает явный compatibility outcome

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
Система ДОЛЖНА (SHALL) трактовать `pool_workflow_binding` как versioned attachment между конкретным `pool` и pinned reusable execution-pack revision.

Operator-facing и shipped attachment semantics ДОЛЖНЫ (SHALL) описывать attached execution pack и pinned execution-pack revision без обязательного compatibility path для historical `binding_profile*` data.

Attachment НЕ ДОЛЖЕН (SHALL NOT) трактоваться как owner reusable execution logic; он остаётся pool-local activation layer.

#### Scenario: Attachment summary показывает attached execution pack
- **GIVEN** оператор открывает pool binding inspect/preview surface
- **WHEN** UI рендерит reusable execution logic summary
- **THEN** экран показывает attached execution pack и его pinned revision
- **AND** не описывает эту reusable сущность так, будто она владеет structural topology

#### Scenario: Runtime lineage не зависит от legacy binding-profile aliases
- **GIVEN** operator-facing semantics уже используют термин `Execution Pack`
- **WHEN** runtime сохраняет provenance или выполняет preview/create-run
- **THEN** immutable opaque revision id остаётся authoritative pin
- **AND** shipped contract не требует compatibility alias для pre-existing `binding_profile*` attachment refs

### Requirement: Attachment read model MUST оставаться derived projection pinned profile revision
Система ДОЛЖНА (SHALL) трактовать `binding_profile_revision_id` вместе с pool-local activation fields как единственный authoritative mutable state attachment-а в shipped path.

Operator-facing или runtime read-model МОЖЕТ (MAY) возвращать `resolved_profile` или эквивалентный convenience payload, но такая проекция:
- ДОЛЖНА (SHALL) выводиться из pinned `binding_profile_revision_id`;
- НЕ ДОЛЖНА (SHALL NOT) становиться второй primary mutable payload surface attachment-а;
- НЕ ДОЛЖНА (SHALL NOT) требовать повторной отправки reusable `workflow`, `decisions`, `parameters` или `role_mapping`, когда оператор меняет только pool-local activation fields.

Default mutate path для attachment-а ДОЛЖЕН (SHALL) принимать только pool-local activation fields и explicit repin на другой `binding_profile_revision_id`, если оператор осознанно меняет reusable схему.

#### Scenario: Pool-local mutate не требует повторной отправки reusable logic
- **GIVEN** attachment pinned на reusable `binding_profile_revision_id`
- **WHEN** оператор меняет только `status`, selector scope или effective period
- **THEN** shipped mutate contract принимает только pool-local fields и pinned profile reference
- **AND** authoritative `workflow`, `decisions`, `parameters` и `role_mapping` продолжают резолвиться из pinned profile revision

#### Scenario: Read model показывает derived resolved profile без второй mutable payload surface
- **GIVEN** attachment pinned на reusable `binding_profile_revision_id`
- **WHEN** оператор или runtime path читает attachment detail, collection или preview
- **THEN** response МОЖЕТ (MAY) включать `resolved_profile` как convenience summary
- **AND** этот payload derived из pinned profile revision, а не из отдельного attachment-local mutable source-of-truth

### Requirement: Default attachment reads MUST быть side-effect-free и не включать remediation/backfill compatibility path
Система ДОЛЖНА (SHALL) обеспечивать, что default shipped list/detail/preview/runtime path для attachment-ов не меняет canonical binding/profile state как implicit remediation.

Default shipped path НЕ ДОЛЖЕН (SHALL NOT):
- создавать generated `binding_profile` или `binding_profile_revision`;
- дописывать missing profile refs в canonical attachment row;
- silently чинить legacy residue как побочный эффект operator read или runtime resolution.

Если canonical attachment row не может быть корректно прочитан из-за отсутствующих или неразрешимых profile refs, shipped path ДОЛЖЕН (SHALL):
- fail-closed;
- вернуть blocking remediation state или machine-readable diagnostic.

Этот refactor НЕ ДОЛЖЕН (SHALL NOT) требовать shipped remediation/backfill compatibility flow для rows без resolvable profile refs; rollout допускает предварительное удаление или пересоздание затронутых historical данных вместо in-place repair.

#### Scenario: Missing profile refs не materialize'ятся молча на read path
- **GIVEN** canonical `pool_workflow_binding` существует, но не содержит корректных profile refs
- **WHEN** оператор открывает binding workspace, attachment detail или preview в shipped path
- **THEN** система возвращает blocking remediation или fail-closed diagnostic
- **AND** generated profile/revision не создаётся как побочный эффект этого чтения

#### Scenario: Legacy residue без profile refs остаётся fail-closed после rollout
- **GIVEN** historical `pool_workflow_binding` сохранился без resolvable profile refs после destructive rollout
- **WHEN** оператор или runtime path читает attachment detail, collection или preview
- **THEN** система возвращает blocking diagnostic
- **AND** не пытается materialize'ить generated profile/revision или repair canonical row

