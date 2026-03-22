## ADDED Requirements

### Requirement: Pool topology templates MUST задавать reusable abstract graph revisions
Система ДОЛЖНА (SHALL) поддерживать tenant-scoped catalog `topology_template` / `topology_template_revision` для повторного использования topology схем между разными `pool`.

`topology_template_revision` ДОЛЖНА (SHALL) описывать:
- abstract nodes со стабильными `slot_key`;
- abstract edges между этими slot-ами;
- optional default `document_policy_key` на template edge;
- shape graph без concrete `organization_id`.

Template revision НЕ ДОЛЖНА (SHALL NOT) хранить concrete организации как часть reusable graph definition.

#### Scenario: Аналитик публикует reusable branching template без concrete организаций
- **GIVEN** аналитик описывает типовую схему распределения с root, двумя intermediate slot-ами и leaf slot-ами
- **WHEN** он сохраняет новую `topology_template_revision`
- **THEN** revision содержит только abstract `slot_key` и edges между ними
- **AND** не требует выбора concrete организаций на этапе публикации шаблона

### Requirement: Pool topology instantiation MUST pin specific template revision and bind concrete organizations to slots
Система ДОЛЖНА (SHALL) позволять `pool` создавать topology не только вручную, но и через instantiation pinned `topology_template_revision_id`.

Pool instantiation ДОЛЖНА (SHALL) сохранять mapping `slot_key -> organization_id` для всех обязательных slot-ов выбранной revision.

Созданный pool НЕ ДОЛЖЕН (SHALL NOT) retroactively менять свою topology только потому, что в catalog появилась новая template revision.

#### Scenario: Оператор создаёт pool из template revision и назначает организации в slot-ы
- **GIVEN** в tenant catalog опубликована `topology_template_revision`
- **WHEN** оператор выбирает эту revision для нового `pool` и задаёт mapping `slot_key -> organization_id`
- **THEN** система создаёт pool-local instantiation на pinned revision
- **AND** resulting pool получает concrete topology, materialized из template shape и slot assignments

#### Scenario: Новая template revision не меняет уже созданный pool молча
- **GIVEN** `pool` уже pinned на `topology_template_revision_id=v3`
- **AND** аналитик публикует новую revision `v4` того же template
- **WHEN** оператор открывает существующий `pool`
- **THEN** concrete topology pool остаётся связанной с `v3`
- **AND** migration на `v4` требует отдельного явного действия

### Requirement: Template edge defaults MUST быть explicit presets, а не graph-only inference
Если template edge задаёт default `document_policy_key`, система ДОЛЖНА (SHALL) materialize'ить его в concrete `edge.metadata.document_policy_key` при instantiation, если pool-local path явно не задал другой selector.

Система НЕ ДОЛЖНА (SHALL NOT) вычислять canonical `document_policy_key` только по degree/position узла в graph shape, если explicit template preset или explicit pool-local override отсутствуют.

#### Scenario: Template edge preset materialize'ится в concrete edge selector
- **GIVEN** template edge `root -> branch_a` содержит default `document_policy_key=realization`
- **WHEN** оператор создаёт `pool` из этой revision без override для этого edge
- **THEN** resulting concrete edge содержит `edge.metadata.document_policy_key=realization`
- **AND** downstream runtime использует этот explicit selector как canonical slot reference

#### Scenario: Отсутствие explicit selector не заменяется эвристикой по graph shape
- **GIVEN** template edge не содержит default `document_policy_key`
- **AND** pool-local instantiation не задала explicit override
- **WHEN** runtime или preview path резолвит policy slot для этого edge
- **THEN** система не выбирает `multi`, `receipt` или другой selector только по положению edge в graph
- **AND** дальнейшая shipped path использует existing fail-closed diagnostics для missing selector
