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

