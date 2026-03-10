# pool-workflow-bindings Specification

## Purpose
TBD - created by archiving change refactor-12-workflow-centric-analyst-modeling. Update Purpose after archive.
## Requirements
### Requirement: Pools MUST поддерживать несколько workflow bindings в одном организационном контуре
Система ДОЛЖНА (SHALL) поддерживать `pool_workflow_binding` как versioned связь между конкретным `pool` и pinned revision workflow definition.

Binding ДОЛЖЕН (SHALL) хранить как минимум:
- `pool_id`;
- `status`;
- `effective_from`;
- `effective_to`;
- `direction`;
- `mode`;
- `workflow_definition_id`;
- `workflow_revision`;
- `decisions`;
- `parameters`;
- `role_mapping` или эквивалентную контекстную привязку;
- `revision`;
- `created_by`;
- `updated_by`.

Один `pool` МОЖЕТ (MAY) иметь несколько одновременно активных bindings, если они различимы по selector/effective period и не создают ambiguity.

Система ДОЛЖНА (SHALL) хранить canonical `pool_workflow_binding` в dedicated persistent resource/store/table, который является единым source-of-truth для:
- list/detail/upsert/delete API;
- runtime binding resolution;
- operator-facing read models и lineage.

Canonical store ДОЛЖЕН (SHALL) использовать indexed scalar columns `pool_id`, `status`, `effective_from`, `effective_to`, `direction`, `mode`, JSON fields `decisions`, `parameters`, `role_mapping` и service fields `revision`, `created_by`, `updated_by`, `created_at`, `updated_at`.

`pool.metadata` НЕ ДОЛЖЕН (SHALL NOT) оставаться canonical или единственным runtime source-of-truth для workflow bindings после hardening cutover.

Snapshot binding provenance для конкретного запуска НЕ ДОЛЖЕН (SHALL NOT) читаться retroactively из mutable binding row после старта run; он ДОЛЖЕН (SHALL) фиксироваться в `PoolRun`/execution lineage на момент preview/create-run.

#### Scenario: Один pool использует две разные схемы одновременно
- **GIVEN** один `pool` имеет binding `top_down_services_v3` и binding `bottom_up_import_v2`
- **WHEN** оператор открывает список доступных схем для этого pool
- **THEN** интерфейс показывает оба binding
- **AND** каждый binding указывает на собственную pinned workflow revision

#### Scenario: Обновление metadata пула не переписывает canonical binding store
- **GIVEN** для `pool` уже созданы canonical workflow bindings
- **WHEN** оператор меняет `name`, `description` или другую pool metadata через pool upsert path
- **THEN** bindings остаются доступными через dedicated binding API и runtime resolution
- **AND** pool upsert path не переписывает canonical binding payload как побочный эффект

### Requirement: Pool workflow binding resolution MUST быть детерминированной и fail-closed
Система ДОЛЖНА (SHALL) резолвить binding для запуска run либо явно по выбранному `pool_workflow_binding_id`, либо по детерминированным selector-правилам.

Если запрос запуска подходит более чем к одному активному binding без явного disambiguation, система НЕ ДОЛЖНА (SHALL NOT) молча выбирать один из них.

#### Scenario: Ambiguous binding блокирует запуск run
- **GIVEN** для одного `pool` активны два binding с пересекающимся effective scope
- **WHEN** оператор пытается запустить run без явного выбора binding
- **THEN** система отклоняет запуск fail-closed
- **AND** возвращает machine-readable диагностику ambiguity

### Requirement: Pool workflow binding MUST предоставлять preview effective runtime projection
Система ДОЛЖНА (SHALL) предоставлять preview binding-а до запуска, достаточный для понимания:
- какой workflow revision будет выполнен;
- какие decisions/parameters будут применены;
- какая concrete runtime projection будет собрана;
- какой lineage получит run.

#### Scenario: Binding preview показывает workflow lineage и compiled projection summary
- **GIVEN** аналитик или оператор открывает binding перед запуском
- **WHEN** система строит preview
- **THEN** preview показывает pinned workflow revision, linked decisions и compiled projection summary
- **AND** пользователь видит, какой именно binding будет исполнен до старта run

### Requirement: Pool workflow binding mutating MUST быть conflict-safe и audit-friendly
Система ДОЛЖНА (SHALL) предоставлять conflict-safe mutating semantics для `pool_workflow_binding`, достаточные для конкурентного редактирования и audit trail.

Concurrent update одного и того же binding НЕ ДОЛЖЕН (SHALL NOT) приводить к silent last-write-wins без явного conflict outcome.

Binding read contract ДОЛЖЕН (SHALL) возвращать server-managed `revision`, а mutating contract ДОЛЖЕН (SHALL) требовать этот `revision` для update/delete.

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

