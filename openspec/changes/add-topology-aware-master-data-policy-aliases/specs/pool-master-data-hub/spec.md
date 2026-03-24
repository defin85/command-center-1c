## ADDED Requirements

### Requirement: Master-data hub MUST резолвить topology participants через Organization->Party binding
Система ДОЛЖНА (SHALL) использовать `Organization.master_party` как canonical binding topology participant-а для
`document_policy` aliases вида `master_data.party.edge.parent.*`, `master_data.party.edge.child.*` и
`master_data.contract.<id>.edge.parent|child.ref`.

При resolution:
- `edge.parent` ДОЛЖЕН (SHALL) адресовать parent organization активного topology edge;
- `edge.child` ДОЛЖЕН (SHALL) адресовать child organization активного topology edge;
- qualifier `organization` ДОЛЖЕН (SHALL) требовать `master_party.is_our_organization=true`;
- qualifier `counterparty` ДОЛЖЕН (SHALL) требовать `master_party.is_counterparty=true`;
- contract alias ДОЛЖЕН (SHALL) использовать canonical id соответствующего participant-а как
  `owner_counterparty_canonical_id` при rewrite в static token grammar.

#### Scenario: Contract owner canonical id выводится из child participant
- **GIVEN** `document_policy` содержит `master_data.contract.osnovnoy.edge.child.ref`
- **AND** child organization текущего edge имеет `master_party.canonical_id=dom-lesa`
- **WHEN** runtime резолвит topology-aware alias
- **THEN** resulting static token равен `master_data.contract.osnovnoy.dom-lesa.ref`
- **AND** downstream master-data resolve использует обычный contract binding scope

### Requirement: Non-participant master-data objects MUST продолжать резолвиться через canonical static bindings
Система ДОЛЖНА (SHALL) продолжать резолвить `item` и `tax_profile` через существующий static canonical token
contract без topology participant indirection.

Система НЕ ДОЛЖНА (SHALL NOT) пытаться выводить `item` или `tax_profile` из `edge.parent` / `edge.child`
только на основании topology structure.

#### Scenario: Static item token bypasses topology participant resolution
- **GIVEN** `document_policy` содержит `master_data.item.packing-service.ref`
- **WHEN** runtime выполняет readiness/compile path
- **THEN** система не требует `participant_side` или `required_role` для этого token-а
- **AND** resulting readiness/gate path использует existing canonical binding semantics для `item`

### Requirement: Topology participant readiness MUST блокировать publication при missing binding или role
Система ДОЛЖНА (SHALL) блокировать preview/create-run fail-closed, если topology-aware alias требует participant,
для которого:
- отсутствует `Organization->Party` binding;
- bound `master_party` не содержит требуемую роль.

Система ДОЛЖНА (SHALL) возвращать machine-readable blockers минимум с полями:
- `code`;
- `detail`;
- `organization_id`;
- `database_id`;
- `edge_ref`;
- `participant_side`;
- `required_role`.

Минимальные коды ошибок:
- `MASTER_DATA_ORGANIZATION_PARTY_BINDING_MISSING`
- `MASTER_DATA_PARTY_ROLE_MISSING`

#### Scenario: Missing child counterparty role блокирует receipt policy compile
- **GIVEN** `document_policy` использует `master_data.party.edge.child.counterparty.ref`
- **AND** child organization текущего edge имеет `master_party`, но у него `is_counterparty=false`
- **WHEN** runtime выполняет readiness/compile path
- **THEN** preview/create-run завершается fail-closed
- **AND** diagnostics содержит `MASTER_DATA_PARTY_ROLE_MISSING`
- **AND** blocker указывает `participant_side=child` и `required_role=counterparty`

#### Scenario: Missing parent organization binding блокирует realization policy compile
- **GIVEN** `document_policy` использует `master_data.party.edge.parent.organization.ref`
- **AND** parent organization текущего edge не имеет `master_party`
- **WHEN** runtime выполняет readiness/compile path
- **THEN** preview/create-run завершается fail-closed
- **AND** diagnostics содержит `MASTER_DATA_ORGANIZATION_PARTY_BINDING_MISSING`
- **AND** blocker указывает `participant_side=parent` и `required_role=organization`
