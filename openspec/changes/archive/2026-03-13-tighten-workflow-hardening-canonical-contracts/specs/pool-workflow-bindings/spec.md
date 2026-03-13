## ADDED Requirements
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

## MODIFIED Requirements
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
