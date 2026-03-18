## ADDED Requirements

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
