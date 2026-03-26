## ADDED Requirements
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
