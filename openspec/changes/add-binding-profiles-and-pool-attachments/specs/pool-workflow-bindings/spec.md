## MODIFIED Requirements

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

## ADDED Requirements

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
