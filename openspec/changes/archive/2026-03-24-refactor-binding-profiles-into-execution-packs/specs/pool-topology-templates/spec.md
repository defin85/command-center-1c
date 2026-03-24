## ADDED Requirements

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
