## ADDED Requirements

### Requirement: Document policy MUST поддерживать topology-aware master-data participant aliases
Система ДОЛЖНА (SHALL) разрешать в `document_policy.v1` внутри `field_mapping` и `table_parts_mapping`
topology-aware master-data aliases для участников конкретного topology edge.

Поддерживаемый минимальный grammar:
- `master_data.party.edge.parent.organization.ref`
- `master_data.party.edge.parent.counterparty.ref`
- `master_data.party.edge.child.organization.ref`
- `master_data.party.edge.child.counterparty.ref`
- `master_data.contract.<contract_canonical_id>.edge.parent.ref`
- `master_data.contract.<contract_canonical_id>.edge.child.ref`

Система ДОЛЖНА (SHALL) резолвить эти aliases во время compile `document_plan_artifact.v1` для каждого edge по
active topology version и selected binding slot.

Система ДОЛЖНА (SHALL) сохранять в resulting `document_plan_artifact.v1` уже переписанные static canonical токены:
- party alias -> `master_data.party.<canonical_id>.<role>.ref`
- contract alias -> `master_data.contract.<contract_canonical_id>.<owner_counterparty_canonical_id>.ref`

Система НЕ ДОЛЖНА (SHALL NOT) передавать unresolved syntax `master_data.party.edge.*` или
`master_data.contract.<id>.edge.*` downstream в `master_data_gate` или publication payload.

#### Scenario: Один reusable receipt policy даёт разные counterparties на разных child edges
- **GIVEN** binding slot `receipt_leaf` pin-ит один `document_policy`, который использует
  `master_data.party.edge.child.organization.ref` и `master_data.party.edge.parent.counterparty.ref`
- **AND** topology содержит ребра `organization_2 -> organization_3` и `organization_2 -> organization_4`
  c одинаковым `document_policy_key=receipt_leaf`
- **WHEN** runtime компилирует `document_plan_artifact`
- **THEN** оба edge используют один и тот же slot policy без повторной decision evaluation
- **AND** для каждого edge resulting documents содержат собственные rewritten canonical tokens parent/child participants
- **AND** downstream artifact/payload не содержит unresolved `master_data.party.edge.*` syntax

### Requirement: Topology-aware participant aliases MUST оставаться additive к static master-data token contract
Система ДОЛЖНА (SHALL) сохранять поддержку existing static canonical token grammar для всех текущих
master-data entity types:
- `master_data.party.<canonical_id>.<role>.ref`
- `master_data.item.<canonical_id>.ref`
- `master_data.contract.<canonical_id>.<owner_counterparty_canonical_id>.ref`
- `master_data.tax_profile.<canonical_id>.ref`

Система НЕ ДОЛЖНА (SHALL NOT) требовать topology-aware alias grammar для `item` и `tax_profile`.

Система ДОЛЖНА (SHALL) трактовать topology-aware alias dialect как additive extension только для topology-derived
participants `party` и `contract`.

#### Scenario: Static item и tax_profile tokens проходят compile без topology-derived rewrite
- **GIVEN** `document_policy` содержит `master_data.item.packing-service.ref` и `master_data.tax_profile.vat20.ref`
- **WHEN** runtime компилирует `document_plan_artifact`
- **THEN** resulting artifact сохраняет эти значения в static canonical token grammar
- **AND** compile path не требует `edge.parent|edge.child` semantics для таких token-ов
- **AND** downstream `master_data_gate` обрабатывает их через existing canonical entity resolution

### Requirement: Topology-aware alias compile MUST быть fail-closed и machine-readable
Система ДОЛЖНА (SHALL) возвращать стабильный machine-readable код `POOL_DOCUMENT_POLICY_TOPOLOGY_ALIAS_INVALID`,
если значение в `field_mapping` или `table_parts_mapping` syntactically похоже на topology-aware alias, но не
соответствует допустимому grammar.

Система НЕ ДОЛЖНА (SHALL NOT) silently игнорировать, partially резолвить или передавать malformed alias дальше по
runtime path.

#### Scenario: Некорректный alias блокирует compile document plan
- **GIVEN** `document_policy` содержит значение `master_data.party.edge.middle.counterparty.ref`
- **WHEN** runtime выполняет compile `document_plan_artifact`
- **THEN** compile завершается fail-closed до OData side effects
- **AND** diagnostics содержит `POOL_DOCUMENT_POLICY_TOPOLOGY_ALIAS_INVALID`
