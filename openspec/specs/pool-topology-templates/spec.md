# pool-topology-templates Specification

## Purpose
TBD - created by archiving change add-pool-topology-templates. Update Purpose after archive.
## Requirements
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

Capability НЕ ДОЛЖНА (SHALL NOT) требовать automatic conversion existing concrete pool graphs; в MVP template instantiation применяется к новым или явно пересозданным `pool`.

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

#### Scenario: Existing manual pool не конвертируется в template автоматически
- **GIVEN** в системе уже существует `pool` с concrete manual topology
- **WHEN** capability `pool-topology-templates` включается для tenant
- **THEN** existing `pool` не получает template instantiation автоматически
- **AND** template-based path применяется только к новым или явно пересозданным `pool`

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

### Requirement: Topology templates MUST own structural slot namespace independent from execution packs
Topology-template revision ДОЛЖНА (SHALL) быть authoritative owner-ом structural slot namespace, используемого для compatibility и runtime slot selection.

Execution-pack layer МОЖЕТ (MAY) реализовывать этот namespace, но НЕ ДОЛЖЕН (SHALL NOT) быть его primary source-of-truth.

#### Scenario: Structural slot namespace принадлежит topology template, а не execution-pack catalog
- **GIVEN** topology-template revision определяет structural slots `sale`, `multi`, `receipt`
- **WHEN** аналитик выбирает или author'ит reusable execution pack
- **THEN** execution pack использует эти keys как implementation contract
- **AND** topology-template revision остаётся owner-ом structural slot namespace

### Requirement: Topology-template compatibility MUST использовать explicit execution-pack slot coverage summary
Система ДОЛЖНА (SHALL) уметь строить compatibility summary между topology-template revision и execution-pack revision по пересечению required structural slot keys и implemented execution slot keys.

Такая summary НЕ ДОЛЖНА (SHALL NOT) менять ownership границ:
- topology template owns structural slots;
- execution pack owns executable implementations.

#### Scenario: Compatibility summary показывает matching и missing slots
- **GIVEN** topology-template revision требует `sale`, `receipt`, `return`
- **AND** execution-pack revision реализует `sale` и `receipt`
- **WHEN** оператор открывает attach/inspect flow
- **THEN** система может показать compatibility summary `2 matched / 1 missing`
- **AND** missing slot остаётся структурной проблемой совместимости, а не implicit auto-generated behavior

### Requirement: Topology-template compatibility MUST distinguish topology-aware reusable execution packs from concrete-ref-bound implementations
Система ДОЛЖНА (SHALL) оценивать compatibility между `topology_template_revision` и `execution-pack revision` не только по пересечению `slot_key`, но и по reusable master-data contract для topology-derived participants.

Для новых или явно revised template-oriented execution packs compatibility summary ДОЛЖЕН (SHALL) различать как минимум:
- structural slot coverage;
- topology-aware readiness для topology-derived `party` / `contract` refs;
- blocking incompatible state, если slot формально покрыт, но decision revisions используют concrete participant refs вместо topology-aware aliases.

Compatibility summary ДОЛЖЕН (SHALL) возвращать эти измерения отдельно, а не схлопывать их в один нечитаемый status.

Compatibility summary НЕ ДОЛЖЕН (SHALL NOT) считать static canonical tokens для `item` и `tax_profile` incompatibility marker'ом.

#### Scenario: Slot формально покрыт, но execution pack остаётся concrete-ref-bound
- **GIVEN** `topology_template_revision` требует structural slots `sale` и `receipt_leaf`
- **AND** выбранная `execution-pack revision` pin-ит решения для этих slots
- **AND** решение для `sale` использует literal `master_data.party.<canonical_id>.<role>.ref` или `master_data.contract.<contract_id>.<owner_id>.ref` в topology-derived participant field
- **WHEN** система строит compatibility summary
- **THEN** slot coverage может считаться structurally matched
- **AND** итоговый status помечается blocking incompatible для template-oriented reusable path
- **AND** summary явно объясняет, что execution pack должен использовать topology-aware aliases вместо concrete participant refs

#### Scenario: Topology-aware execution pack проходит compatibility без concrete participant refs
- **GIVEN** `topology_template_revision` требует structural slots `sale` и `receipt_leaf`
- **AND** выбранная `execution-pack revision` реализует эти slots через decision revisions c `master_data.party.edge.*` и `master_data.contract.<id>.edge.*`
- **WHEN** система строит compatibility summary
- **THEN** summary показывает compatible status для reusable template path
- **AND** concrete `slot_key -> organization_id` остаётся единственным pool-specific participant binding слоем

#### Scenario: Summary показывает отдельные structural и semantic результаты
- **GIVEN** execution-pack revision покрывает все required `slot_key`
- **AND** один slot semantic incompatible из-за concrete participant refs
- **WHEN** система строит compatibility summary
- **THEN** structural coverage отмечается как complete
- **AND** topology-aware master-data readiness отмечается как blocking incompatible
- **AND** оператор видит, что проблема не в missing slot, а в reusable master-data contract

