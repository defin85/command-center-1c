## MODIFIED Requirements
### Requirement: Pools MUST поддерживать несколько workflow bindings в одном организационном контуре
Система ДОЛЖНА (SHALL) поддерживать `pool_workflow_binding` как versioned связь между конкретным `pool` и pinned revision workflow definition.

Binding ДОЛЖЕН (SHALL) хранить как минимум:
- `pool_id`;
- `workflow_definition_id`;
- `workflow_revision`;
- effective period;
- binding parameters;
- role mapping или эквивалентную контекстную привязку;
- binding status.

Один `pool` МОЖЕТ (MAY) иметь несколько одновременно активных bindings, если они различимы по selector/effective period и не создают ambiguity.

Система ДОЛЖНА (SHALL) хранить canonical `pool_workflow_binding` в dedicated persistent resource/store, который является единым source-of-truth для:
- list/detail/upsert/delete API;
- runtime binding resolution;
- operator-facing read models и lineage.

`pool.metadata` НЕ ДОЛЖЕН (SHALL NOT) оставаться canonical или единственным runtime source-of-truth для workflow bindings после hardening cutover.

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

## ADDED Requirements
### Requirement: Pool workflow binding mutating MUST быть conflict-safe и audit-friendly
Система ДОЛЖНА (SHALL) предоставлять conflict-safe mutating semantics для `pool_workflow_binding`, достаточные для конкурентного редактирования и audit trail.

Concurrent update одного и того же binding НЕ ДОЛЖЕН (SHALL NOT) приводить к silent last-write-wins без явного conflict outcome.

#### Scenario: Конкурентное редактирование binding возвращает явный conflict
- **GIVEN** два оператора редактируют один и тот же `pool_workflow_binding`
- **AND** первый оператор уже зафиксировал новую ревизию binding
- **WHEN** второй оператор пытается сохранить устаревшее состояние
- **THEN** система возвращает machine-readable conflict
- **AND** canonical binding store сохраняет только выигравшее изменение
