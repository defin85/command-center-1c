## MODIFIED Requirements

### Requirement: Topology-aware participant aliases MUST оставаться additive к static master-data token contract
Система ДОЛЖНА (SHALL) сохранять поддержку existing static canonical token grammar для всех текущих и новых reusable-data entity types:
- `master_data.party.<canonical_id>.<role>.ref`
- `master_data.item.<canonical_id>.ref`
- `master_data.contract.<canonical_id>.<owner_counterparty_canonical_id>.ref`
- `master_data.tax_profile.<canonical_id>.ref`
- `master_data.gl_account.<canonical_id>.ref`

Система НЕ ДОЛЖНА (SHALL NOT) требовать topology-aware alias grammar для `item`, `tax_profile` и `gl_account`.

Система ДОЛЖНА (SHALL) трактовать topology-aware alias dialect как additive extension только для topology-derived participants `party` и `contract`.

#### Scenario: Static item, tax_profile и gl_account tokens проходят compile без topology-derived rewrite
- **GIVEN** `document_policy` содержит `master_data.item.packing-service.ref`, `master_data.tax_profile.vat20.ref` и `master_data.gl_account.sales-revenue.ref`
- **WHEN** runtime компилирует `document_plan_artifact`
- **THEN** resulting artifact сохраняет эти значения в static canonical token grammar
- **AND** compile path не требует `edge.parent|edge.child` semantics для таких token-ов
- **AND** downstream `master_data_gate` обрабатывает их через existing canonical entity resolution

## ADDED Requirements

### Requirement: Document policy MUST поддерживать canonical account tokens в header и tabular account fields
Система ДОЛЖНА (SHALL) разрешать использование `master_data.gl_account.<canonical_id>.ref` в `field_mapping` и `table_parts_mapping` для document fields, которые по metadata contract ожидают ссылку на published chart-of-accounts object.

Система НЕ ДОЛЖНА (SHALL NOT) требовать raw GUID literals для account fields, если policy authoring использует canonical account token.

#### Scenario: Policy задаёт account fields через canonical GLAccount tokens
- **GIVEN** `document_policy` для `Document_РеализацияТоваровУслуг` содержит account fields в header и табличной части
- **WHEN** аналитик задаёт для этих полей `master_data.gl_account.<canonical_id>.ref`
- **THEN** compile path принимает такие token-ы как валидные
- **AND** downstream publication path получает resolved account refs, а не raw token string

### Requirement: Account token validation MUST оставаться metadata-aware и configuration-scoped
Система ДОЛЖНА (SHALL) валидировать `master_data.gl_account.<canonical_id>.ref` против resolved metadata snapshot выбранной target business configuration identity.

Система ДОЛЖНА (SHALL) принимать такой token только для field paths, которые metadata snapshot распознаёт как ссылку на target chart-of-accounts object.

Система НЕ ДОЛЖНА (SHALL NOT) принимать account token только по имени поля или по совпадению account code без metadata-aware compatibility validation.

#### Scenario: Account token в несовместимом field path блокирует compile fail-closed
- **GIVEN** `document_policy` содержит `master_data.gl_account.sales-revenue.ref`
- **AND** выбранный field path в target metadata snapshot не является ссылкой на chart-of-accounts object
- **WHEN** runtime выполняет compile document plan
- **THEN** compile завершается fail-closed с metadata validation error
- **AND** malformed account mapping не уходит дальше в publication payload
