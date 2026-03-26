# pool-binding-profiles Specification

## Purpose
TBD - created by archiving change add-binding-profiles-and-pool-attachments. Update Purpose after archive.
## Requirements
### Requirement: Binding profiles MUST быть tenant-scoped reusable versioned resources
Система ДОЛЖНА (SHALL) предоставлять reusable execution-pack catalog как tenant-scoped versioned resource для reusable execution logic.

Primary operator/domain термином для этой capability ДОЛЖЕН (SHALL) быть `Execution Pack`.

Execution-pack revision ДОЛЖНА (SHALL) хранить reusable executable contract:
- pinned workflow revision;
- decision refs, реализующие named slot implementations;
- default parameters;
- role mapping;
- revision metadata/provenance.

Execution-pack revision НЕ ДОЛЖНА (SHALL NOT) считаться owner-ом topology shape или structural slot namespace.

Immutable opaque revision id ДОЛЖЕН (SHALL) оставаться authoritative runtime pin в execution-pack semantics.

#### Scenario: Один execution pack используется несколькими pool attachment-ами
- **GIVEN** аналитик создал reusable execution pack revision
- **WHEN** оператор attach'ит эту revision к нескольким pool
- **THEN** все attachment-ы используют одну и ту же reusable execution-pack revision
- **AND** pool-local activation state остаётся независимым

#### Scenario: Operator-facing catalog использует термин Execution Pack
- **GIVEN** аналитик или оператор открывает reusable catalog surface
- **WHEN** UI рендерит list/detail/create/revise flows
- **THEN** основная operator-facing терминология использует `Execution Pack`
- **AND** shipped contract не зависит от обязательного legacy alias `Binding Profile`

### Requirement: Binding profile authoring MUST использовать dedicated catalog surface
Система ДОЛЖНА (SHALL) предоставлять dedicated catalog surface для list/detail/create/revise/deactivate reusable execution packs.

Primary operator-facing route для этого catalog ДОЛЖЕН (SHALL) быть `/pools/execution-packs`.

Shipped contract НЕ ДОЛЖЕН (SHALL NOT) требовать legacy route `/pools/binding-profiles` как обязательный redirect или compatibility alias после rollout этого change.

#### Scenario: Оператор открывает reusable execution logic catalog по новому route
- **WHEN** пользователь открывает `/pools/execution-packs`
- **THEN** UI показывает catalog reusable execution packs
- **AND** create/revise/deactivate flows доступны на этом route как primary path

#### Scenario: Primary navigation больше не зависит от binding-profiles route
- **GIVEN** rollout execution-pack catalog завершён после hard reset данных
- **WHEN** оператор использует primary navigation и handoff links
- **THEN** они указывают на `/pools/execution-packs`
- **AND** shipped path не требует `/pools/binding-profiles` для корректной работы catalog surface

### Requirement: Profile deactivation MUST сохранять reproducible runtime для уже pinned attachments
Система ДОЛЖНА (SHALL) трактовать `deactivate` как reusable catalog lifecycle action, а не как retroactive runtime kill switch.

После `deactivate`:
- новые attach/re-attach к revision этого profile НЕ ДОЛЖНЫ (SHALL NOT) выполняться;
- публикация новых revisions этого profile НЕ ДОЛЖНА (SHALL NOT) выполняться;
- уже существующие attachment-ы, pinned на существующие `binding_profile_revision_id`, ДОЛЖНЫ (SHALL) продолжать preview/create-run/retry на default path, если их pool-local attachment остаётся active и попадает в effective scope.

Если later понадобится аварийно отключать уже pinned reusable revisions, это ДОЛЖЕН (SHALL) быть отдельный lifecycle state/flow вне этого change.

#### Scenario: Deactivated profile не ломает уже pinned attachment
- **GIVEN** `pool-A` уже pinned на `binding_profile_revision_id=bp_rev_123`
- **WHEN** аналитик деактивирует profile в catalog
- **THEN** existing attachment `pool-A` остаётся runnable на default path
- **AND** UI показывает, что reusable source deactivated и требует плановой миграции

#### Scenario: Deactivated profile нельзя attach'ить заново
- **GIVEN** reusable profile деактивирован в catalog
- **WHEN** оператор пытается attach'ить его revision к новому pool
- **THEN** система отклоняет attach fail-closed
- **AND** требует выбрать active profile revision

### Requirement: Profile rollout MUST сохранять текущее поведение existing pool bindings
Система ДОЛЖНА (SHALL) предоставлять conservative migration path от existing pool bindings к generated `binding_profile_revision` без автоматического semantic merge между пулами.

Migration/backfill НЕ ДОЛЖЕН (SHALL NOT) автоматически считать два исторических binding-а одинаковыми reusable profile только на основе похожего payload.

#### Scenario: Existing binding materialize'ится в generated one-off profile
- **GIVEN** в системе уже существует historical `pool_workflow_binding`
- **WHEN** выполняется rollout profile model
- **THEN** система создаёт generated profile revision, эквивалентную текущему binding payload
- **AND** текущий pool binding становится attachment-ом к этой generated revision

#### Scenario: Похожие binding-ы из двух пулов не merge'ятся автоматически
- **GIVEN** в двух пулах есть визуально похожие binding-ы
- **WHEN** выполняется migration/backfill
- **THEN** система не объединяет их автоматически в один shared profile
- **AND** дальнейшая консолидация выполняется только явным operator/analyst действием

### Requirement: Binding profile authoring MUST использовать structured selectors вместо ручного ввода opaque references на default path
Система ДОЛЖНА (SHALL) предоставлять на `/pools/binding-profiles` structured authoring path для выбора pinned workflow revision и decision revisions, используемых в reusable binding profile revision.

Default authoring form ДОЛЖНА (SHALL):
- выбирать workflow revision из searchable catalog/picker;
- выбирать decision revisions через slot-oriented editor;
- автоматически заполнять связанные workflow reference fields из выбранной revision;
- направлять пользователя к `/workflows` и `/decisions` как к canonical reference catalogs без необходимости ручного копирования ids.

Default authoring form НЕ ДОЛЖНА (SHALL NOT) требовать ручного ввода `workflow_definition_key`, `workflow_revision_id`, `workflow_revision`, `workflow_name` или raw `Decision refs JSON` как primary UX path.

Raw/manual payload editing МОЖЕТ (MAY) существовать только как explicit advanced mode для compatibility/debugging и НЕ ДОЛЖЕН (SHALL NOT) открываться как основной экран редактирования.

#### Scenario: Аналитик создаёт binding profile через workflow revision picker
- **GIVEN** аналитик открыл `/pools/binding-profiles`
- **WHEN** он создаёт новую reusable profile revision
- **THEN** workflow pin выбирается из searchable workflow revision catalog
- **AND** связанные workflow reference fields заполняются из выбранной revision без ручного copy-paste

#### Scenario: Slot-oriented decision editor заменяет raw JSON как primary path
- **GIVEN** аналитик настраивает decision refs для reusable profile revision
- **WHEN** он добавляет publication slots
- **THEN** UI позволяет выбрать decision revision из structured list `/decisions` и отдельно задать `slot_key`
- **AND** raw JSON не является primary способом ввода decision refs

#### Scenario: Advanced mode остаётся явным compatibility path
- **GIVEN** оператору требуется вручную проверить или поправить raw payload для debugging/compatibility
- **WHEN** он явно переключается в advanced mode
- **THEN** UI показывает raw/manual controls
- **AND** default authoring path остаётся structured и скрывает эти controls по умолчанию

### Requirement: Binding profile detail MUST оставаться summary-first и убирать technical lineage в advanced disclosure
Система ДОЛЖНА (SHALL) показывать на default detail path `/pools/binding-profiles` operator-facing summary как primary content:
- code/name/status/latest revision number;
- workflow summary;
- usage summary и next actions (`publish new revision`, `deactivate`, handoff to pool attachments).

Opaque immutable identifiers (`binding_profile_revision_id`) и raw technical payload НЕ ДОЛЖНЫ (SHALL NOT) оставаться primary default content в revision history или detail summary. Они ДОЛЖНЫ (SHALL) быть доступны только через explicit advanced disclosure path.

Это НЕ ДОЛЖНО (SHALL NOT) менять runtime lineage contract: immutable opaque id остаётся authoritative identity, но default operator path не обязан показывать его раньше human-readable summary.

#### Scenario: Default revision history не показывает opaque pin как primary column
- **GIVEN** оператор открыл detail reusable binding profile на `/pools/binding-profiles`
- **WHEN** он просматривает default revision history
- **THEN** экран показывает human-readable revision number и workflow summary как основной контекст
- **AND** immutable opaque pin hidden behind explicit advanced disclosure

#### Scenario: Support visibility остаётся доступной через advanced path
- **GIVEN** оператору или support engineer нужен immutable pin выбранной revision
- **WHEN** он явно открывает advanced disclosure
- **THEN** UI показывает `binding_profile_revision_id` и related technical payload
- **AND** runtime/support path не теряет access к authoritative lineage identifier

### Requirement: Binding profile inspect flow MUST оставаться mobile-safe и touch-safe
Система ДОЛЖНА (SHALL) обеспечивать, что inspect/revise/deactivate flow на `/pools/binding-profiles` остаётся usable на narrow viewport и touch devices.

Primary selection control в catalog ДОЛЖЕН (SHALL) оставаться semantic interactive element с touch-safe hit area для выбора profile.

Primary detail actions и summary fields в mobile detail drawer НЕ ДОЛЖНЫ (SHALL NOT) клиповаться, выходить за viewport или требовать horizontal scroll для завершения primary operator actions.

Secondary tabular diagnostics МОГУТ (MAY) использовать controlled internal overflow, если это не мешает primary inspect/revise/deactivate path.

#### Scenario: Mobile drawer остаётся usable без clipping primary actions
- **GIVEN** оператор открыл `/pools/binding-profiles` на narrow viewport
- **WHEN** он открывает detail выбранного profile
- **THEN** primary actions и summary fields полностью доступны внутри viewport
- **AND** inspect/revise/deactivate flow не требует hidden horizontal scrolling для завершения основных действий

#### Scenario: Catalog selection остаётся touch-safe
- **GIVEN** оператор выбирает reusable profile из catalog на touch device
- **WHEN** он нажимает primary selection control
- **THEN** control остаётся semantic button с достаточно крупной hit area для уверенного выбора
- **AND** выбор profile не зависит только от узкой текстовой зоны внутри строки

### Requirement: `/pools/binding-profiles` MUST быть operator-first workspace с shareable catalog context
Система ДОЛЖНА (SHALL) поддерживать `/pools/binding-profiles` как stateful operator workspace, где catalog context можно адресовать через URL, а detail pane сначала объясняет смысл профиля и доступные действия, а уже потом показывает низкоуровневые pins и raw payload.

Default route path ДОЛЖЕН (SHALL):
- синхронизировать search query, selected profile и detail-open state с URL;
- иметь устойчиво подписанный search control;
- использовать keyboard-first semantic profile selection;
- показывать summary, usage context и next actions раньше opaque revision IDs и raw JSON payload.

#### Scenario: Deep link восстанавливает catalog selection и search
- **GIVEN** оператор открыл `/pools/binding-profiles` с query params поиска и выбранного profile
- **WHEN** страница инициализируется или пользователь использует back/forward
- **THEN** UI восстанавливает тот же catalog context
- **AND** не сбрасывает search и selected profile на состояние по умолчанию

#### Scenario: Detail pane сначала объясняет профиль, а затем раскрывает payload
- **GIVEN** оператор выбрал reusable binding profile
- **WHEN** detail pane открылся на default path
- **THEN** верхняя часть detail показывает summary, status, workflow context и next actions
- **AND** opaque pins и raw JSON остаются доступными только как secondary/advanced layer

#### Scenario: Выбор profile не зависит только от клика по строке
- **GIVEN** оператор работает с catalog через клавиатуру
- **WHEN** он переходит по списку reusable profiles
- **THEN** UI предоставляет semantic selection trigger и явное selected state
- **AND** row click, если остаётся, работает только как дополнительное удобство

### Requirement: Binding profile usage summary MUST использовать dedicated scoped read model
Система ДОЛЖНА (SHALL) предоставлять для `/pools/binding-profiles` dedicated backend read-model, scoped к выбранному `binding_profile_id`, чтобы operator-facing usage summary не зависел от broad tenant-wide pool catalog hydration.

Scoped usage projection ДОЛЖНА (SHALL):
- возвращать только attachment-ы, pinned на выбранный reusable profile;
- возвращать attachment count и summary по revision-ам, которые сейчас используются;
- включать достаточно pool/binding context для явного handoff в `/pools/catalog`;
- не требовать от shipped frontend path загрузки полного списка pools и client-side фильтрации нерелевантных attachment-ов.

UI МОЖЕТ (MAY) lazy-load usage по требованию оператора, но default shipped path НЕ ДОЛЖЕН (SHALL NOT) вычислять usage summary через broad organization pool list scan.

#### Scenario: Profile detail получает scoped usage без tenant-wide pool scan
- **GIVEN** оператор открыл detail reusable profile на `/pools/binding-profiles`
- **WHEN** detail pane загружает usage summary
- **THEN** backend возвращает только attachment-ы, pinned на выбранный profile, вместе с counts и revision summary
- **AND** UI может открыть соответствующий pool attachment workspace без отдельной broad pool catalog hydration

#### Scenario: Нерелевантные pools не участвуют в profile usage response
- **GIVEN** tenant содержит множество pools, не использующих выбранный reusable profile
- **WHEN** оператор открывает usage summary для этого profile
- **THEN** shipped path остаётся scoped к выбранному `binding_profile_id`
- **AND** нерелевантные pools не загружаются только ради client-side aggregation usage summary

### Requirement: Execution pack authoring MUST реализовывать external structural slots, а не определять их
Execution-pack authoring ДОЛЖЕН (SHALL) использовать `slot_key` как ключ executable implementation для external structural slot contract.

Structural slot namespace ДОЛЖЕН (SHALL) считаться внешним по отношению к execution pack catalog и приходить из topology-template layer или materialized concrete topology contract.

Execution pack НЕ ДОЛЖЕН (SHALL NOT) быть доменным owner-ом structural slot namespace.

#### Scenario: Execution pack реализует topology-defined slots
- **GIVEN** topology-template contract определяет structural slots `sale`, `multi`, `receipt`
- **WHEN** аналитик author'ит execution pack
- **THEN** он pin-ит decision revisions для этих `slot_key`
- **AND** resulting execution pack описывает executable implementations, а не topology shape

#### Scenario: Execution pack не вводит новый structural slot молча
- **GIVEN** execution pack содержит implementation для slot `custom_slot`
- **AND** selected topology contract не содержит такого structural slot
- **WHEN** система выполняет compatibility validation
- **THEN** execution pack не считается автоматически совместимым
- **AND** требуется явная remediation или другая topology/template contract

### Requirement: New and revised execution packs MUST use topology-aware participant aliases for template-oriented reusable slots
Система ДОЛЖНА (SHALL) рассматривать topology-aware aliases как canonical reusable authoring contract для всех новых и новых revision reusable execution packs, публикуемых через canonical route `/pools/execution-packs`.

Если decision revision, pinned в execution pack slot, заполняет topology-derived `organization`, `counterparty` или `contract` fields, default authoring path ДОЛЖЕН (SHALL) использовать:
- `master_data.party.edge.parent.organization.ref`
- `master_data.party.edge.parent.counterparty.ref`
- `master_data.party.edge.child.organization.ref`
- `master_data.party.edge.child.counterparty.ref`
- `master_data.contract.<contract_canonical_id>.edge.parent.ref`
- `master_data.contract.<contract_canonical_id>.edge.child.ref`

Default authoring path НЕ ДОЛЖЕН (SHALL NOT) требовать hardcoded concrete `party` или `contract` refs для таких reusable slots.

Если selected decision revision для topology-derived participant fields остаётся concrete-ref-bound, create/revise flow execution pack ДОЛЖЕН (SHALL) завершаться fail-closed с machine-readable diagnostic и handoff в canonical decision authoring surface вместо silent acceptance.

Static canonical tokens для `item` и `tax_profile` ДОЛЖНЫ (SHALL) оставаться допустимыми и не считаться violation этого requirement.

#### Scenario: Аналитик публикует reusable execution pack без hardcoded participant refs
- **GIVEN** аналитик author'ит или revises execution pack для reusable template-oriented top-down topology
- **AND** slot `sale` и slot `receipt_leaf` используют decision revisions с topology-aware aliases для `party` и `contract`
- **WHEN** execution pack revision публикуется
- **THEN** publish succeeds без требования вводить concrete `organization_id`, `counterparty` или `contract owner` refs
- **AND** resulting execution pack остаётся reusable между разными pool с одинаковым template slot contract

#### Scenario: Concrete participant refs блокируют publish revised execution pack
- **GIVEN** аналитик revises existing execution pack
- **AND** selected decision revision для topology-derived slot использует literal static `master_data.party.<canonical_id>.<role>.ref` или `master_data.contract.<contract_id>.<owner_id>.ref`
- **WHEN** analyst пытается опубликовать новую revision execution pack
- **THEN** shipped path возвращает machine-readable blocking diagnostic
- **AND** execution pack revision не публикуется как compatible reusable template-oriented contract
- **AND** UI направляет аналитика в `/decisions` для выпуска topology-aware decision revision

### Requirement: Execution-pack mutation diagnostics MUST expose stable machine-readable incompatibility details
Система ДОЛЖНА (SHALL) возвращать stable machine-readable contract, если create/revise reusable execution pack блокируется из-за concrete participant refs в topology-derived slots.

Минимальный diagnostic payload ДОЛЖЕН (SHALL) содержать:
- `code`;
- `slot_key`;
- `decision_table_id`;
- `decision_revision`;
- `field_or_table_path`;
- `detail`.

Минимальный code для этого change:
- `EXECUTION_PACK_TOPOLOGY_ALIAS_REQUIRED`

#### Scenario: Publish response показывает проблемный slot и field path
- **GIVEN** create/revise reusable execution pack отклонён из-за topology-derived `contract` field с concrete ref
- **WHEN** backend возвращает diagnostic
- **THEN** response содержит `code=EXECUTION_PACK_TOPOLOGY_ALIAS_REQUIRED`
- **AND** response указывает проблемный `slot_key`, decision revision reference и `field_or_table_path`

