## ADDED Requirements

### Requirement: Master-data sync and bootstrap routing MUST читаться из executable reusable-data registry
Система ДОЛЖНА (SHALL) определять bootstrap eligibility, dependency ordering, sync enqueue и outbox fan-out через executable reusable-data registry/type handlers.

Система НЕ ДОЛЖНА (SHALL NOT) выводить routing eligibility только из enum membership, OpenAPI namespace или наличия binding row.

#### Scenario: Bootstrap routing не зависит от handwritten scope lists
- **GIVEN** reusable-data registry уже определяет bootstrap capability для shipped entity types
- **WHEN** оператор запускает bootstrap import
- **THEN** backend и frontend используют registry-driven entity catalog
- **AND** список доступных сущностей не поддерживается вручную в нескольких местах

### Requirement: Unsupported reusable-data directions MUST блокироваться fail-closed
Система ДОЛЖНА (SHALL) блокировать mutating sync/outbox actions для reusable entity types, если registry не объявляет соответствующую direction capability.

Operator-facing sync affordances ДОЛЖНЫ (SHALL) читать то же capability решение, что и backend runtime.

#### Scenario: Runtime и UI одинаково скрывают неподдержанную direction capability
- **GIVEN** reusable entity type не имеет declared outbound capability в registry
- **WHEN** система строит sync read-model и оценивает enqueue eligibility
- **THEN** backend не создаёт mutating sync intent
- **AND** UI не показывает generic action для этой direction
