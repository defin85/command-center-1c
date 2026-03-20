# pool-binding-profiles Specification

## Purpose
TBD - created by archiving change add-binding-profiles-and-pool-attachments. Update Purpose after archive.
## Requirements
### Requirement: Binding profiles MUST быть tenant-scoped reusable versioned resources
Система ДОЛЖНА (SHALL) поддерживать tenant-scoped reusable сущности `binding_profile` и immutable `binding_profile_revision`, не привязанные к конкретному `pool`.

`binding_profile_revision` ДОЛЖЕН (SHALL) хранить reusable схему:
- pinned workflow revision;
- publication slot decision refs;
- default parameters;
- role mapping;
- revision metadata/provenance.

Каждая immutable revision ДОЛЖНА (SHALL) иметь opaque `binding_profile_revision_id`, который используется как единственный runtime pin и lineage reference.

`revision_number` или эквивалентный human-readable номер revision МОЖЕТ (MAY) существовать для operator-facing read-model, но НЕ ДОЛЖЕН (SHALL NOT) подменять `binding_profile_revision_id` как authoritative immutable identity.

Одна и та же `binding_profile_revision` МОЖЕТ (MAY) использоваться несколькими pool attachment-ами в разных пулах.

Публикация новой revision НЕ ДОЛЖНА (SHALL NOT) retroactively менять уже существующие attachment-ы, pinned на предыдущую revision.

#### Scenario: Одна profile revision используется двумя пулами
- **GIVEN** аналитик создал `binding_profile` с revision `r3`
- **WHEN** оператор attach'ит `r3` к `pool-A` и `pool-B`
- **THEN** оба пула используют одну и ту же reusable revision
- **AND** pool-local activation rules остаются независимыми

#### Scenario: Новая revision не переписывает существующие attachment-ы
- **GIVEN** `pool-A` и `pool-B` pinned на `binding_profile_revision r3`
- **WHEN** аналитик публикует `binding_profile_revision r4`
- **THEN** existing attachment-ы продолжают ссылаться на `r3`
- **AND** rollout `r4` требует явного обновления attachment-а

#### Scenario: Runtime pin использует opaque revision id, а не display number
- **GIVEN** reusable profile имеет operator-facing `revision_number=4`
- **WHEN** attachment сохраняет ссылку на immutable revision
- **THEN** runtime и lineage используют `binding_profile_revision_id`
- **AND** display number остаётся только человекочитаемым summary

### Requirement: Binding profile authoring MUST использовать dedicated catalog surface
Система ДОЛЖНА (SHALL) предоставлять dedicated catalog surface для list/detail/create/revise/deactivate reusable binding profiles.

Default operator-facing UI route для этого catalog ДОЛЖЕН (SHALL) быть отдельной страницей `/pools/binding-profiles`, а НЕ встроенным inline authoring surface внутри `/pools/catalog`.

Pool-local binding workspace МОЖЕТ (MAY) attach'ить существующую profile revision, но НЕ ДОЛЖЕН (SHALL NOT) оставаться primary full authoring surface для reusable workflow/slot logic.

#### Scenario: Аналитик создаёт reusable profile один раз и затем attach'ит её к пулу
- **GIVEN** аналитик открыл binding profile catalog
- **WHEN** он создаёт profile revision с workflow revision и slot map
- **THEN** resulting profile revision становится доступной для выбора в pool attachment workspace
- **AND** оператор может attach'ить её к конкретному пулу без повторного ручного ввода всей схемы

#### Scenario: Pool workspace направляет в profile catalog для правки reusable схемы
- **GIVEN** оператор открыл attachment в `/pools/catalog`
- **AND** attachment pinned на profile revision
- **WHEN** оператору нужна правка workflow/slot logic
- **THEN** UI направляет его в dedicated profile catalog
- **AND** pool workspace не редактирует reusable logic inline как primary path

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

