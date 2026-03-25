## ADDED Requirements
### Requirement: New and revised execution packs MUST use topology-aware participant aliases for template-oriented reusable slots
Система ДОЛЖНА (SHALL) рассматривать topology-aware aliases как canonical reusable authoring contract для всех новых и новых revision reusable execution packs, публикуемых через canonical route `/pools/execution-packs`.

Если decision revision, pinned в execution pack slot, заполняет topology-derived `organization`, `counterparty` или `contract` fields, default authoring path ДОЛЖЕН (SHALL) использовать:
- `master_data.party.edge.parent.organization.ref`
- `master_data.party.edge.parent.counterparty.ref`
- `master_data.party.edge.child.organization.ref`
- `master_data.party.edge.child.counterparty.ref`
- `master_data.contract.<contract_canonical_id>.edge.parent.ref`
- `master_data.contract.<contract_canonical_id>.edge.child.ref`

Default authoring path НЕ ДОЛЖЕН (SHALL NOT) требовать hardcoded concrete `party` или `contract` refs для таких reusable slots.

Если selected decision revision для topology-derived participant fields остаётся concrete-ref-bound, create/revise flow execution pack ДОЛЖЕН (SHALL) завершаться fail-closed с machine-readable diagnostic и handoff в canonical decision authoring surface вместо silent acceptance.

Static canonical tokens для `item` и `tax_profile` ДОЛЖНЫ (SHALL) оставаться допустимыми и не считаться violation этого requirement.

#### Scenario: Аналитик публикует reusable execution pack без hardcoded participant refs
- **GIVEN** аналитик author'ит или revises execution pack для reusable template-oriented top-down topology
- **AND** slot `sale` и slot `receipt_leaf` используют decision revisions с topology-aware aliases для `party` и `contract`
- **WHEN** execution pack revision публикуется
- **THEN** publish succeeds без требования вводить concrete `organization_id`, `counterparty` или `contract owner` refs
- **AND** resulting execution pack остаётся reusable между разными pool с одинаковым template slot contract

#### Scenario: Concrete participant refs блокируют publish revised execution pack
- **GIVEN** аналитик revises existing execution pack
- **AND** selected decision revision для topology-derived slot использует literal static `master_data.party.<canonical_id>.<role>.ref` или `master_data.contract.<contract_id>.<owner_id>.ref`
- **WHEN** analyst пытается опубликовать новую revision execution pack
- **THEN** shipped path возвращает machine-readable blocking diagnostic
- **AND** execution pack revision не публикуется как compatible reusable template-oriented contract
- **AND** UI направляет аналитика в `/decisions` для выпуска topology-aware decision revision

### Requirement: Execution-pack mutation diagnostics MUST expose stable machine-readable incompatibility details
Система ДОЛЖНА (SHALL) возвращать stable machine-readable contract, если create/revise reusable execution pack блокируется из-за concrete participant refs в topology-derived slots.

Минимальный diagnostic payload ДОЛЖЕН (SHALL) содержать:
- `code`;
- `slot_key`;
- `decision_table_id`;
- `decision_revision`;
- `field_or_table_path`;
- `detail`.

Минимальный code для этого change:
- `EXECUTION_PACK_TOPOLOGY_ALIAS_REQUIRED`

#### Scenario: Publish response показывает проблемный slot и field path
- **GIVEN** create/revise reusable execution pack отклонён из-за topology-derived `contract` field с concrete ref
- **WHEN** backend возвращает diagnostic
- **THEN** response содержит `code=EXECUTION_PACK_TOPOLOGY_ALIAS_REQUIRED`
- **AND** response указывает проблемный `slot_key`, decision revision reference и `field_or_table_path`
