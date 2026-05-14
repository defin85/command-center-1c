## ADDED Requirements

### Requirement: KVO17 generated purchase policy MUST create two distinct receipt documents per counterparty with shared invoice identity

For generated KVO17 purchase runs, the system SHALL materialize exactly two receipt document targets per selected counterparty: one for each configured amount range/KVO assignment.

For the two generated documents of one counterparty, supplier invoice number and supplier invoice date SHALL be identical. Runtime document identity, external idempotency key, row lineage, and KVO/range policy lineage MUST remain distinct.

When both generated documents target the same `Organization.database`, the document plan SHALL NOT require two topology branch slots or two physical graph edges. It SHALL represent the pair as one publication edge/chain containing two distinct receipt documents, while preserving KVO/range lineage for each document.

For each generated receipt document, the publication chain SHALL also include one linked received invoice document (`Document_СчетФактураПолученный`). The invoice document SHALL preserve the same supplier invoice number/date as the generated receipt pair, SHALL carry the receipt row's KVO value, and SHALL reference its exact receipt document through `ДокументыОснования`/`ДокументОснование`.

The document plan MUST preserve:

- selected counterparty provenance;
- generated supplier invoice number/date;
- generated amount and VAT fields;
- assigned KVO;
- range key or equivalent branch identity;
- generation seed/manifest lineage.

#### Scenario: One counterparty receives two generated purchase document targets
- **GIVEN** generated manifest contains counterparty `supplier-001`
- **AND** range `small` is assigned to KVO `17`
- **AND** range `large` is assigned to KVO `01`
- **WHEN** document plan is compiled
- **THEN** document plan contains two receipt targets for `supplier-001`
- **AND** both targets use the same supplier invoice number/date
- **AND** one target uses KVO `17` and the other target uses KVO `01`
- **AND** the two targets have distinct document identity/idempotency lineage

#### Scenario: One target database receives both generated receipt documents on one edge
- **GIVEN** generated manifest contains counterparty `supplier-001`
- **AND** both generated receipt documents target the same `Organization.database`
- **WHEN** document plan is compiled
- **THEN** document plan contains one publication edge/chain for that counterparty
- **AND** that chain contains two receipt documents
- **AND** the publication chain contains a received invoice document linked to each receipt
- **AND** graph topology does not need separate `purchase_kvo01` and `purchase_kvo17` child nodes for the same physical database

#### Scenario: Generated receipts publish linked received invoices
- **GIVEN** generated manifest contains counterparty `supplier-001`
- **AND** its two generated receipt documents share supplier invoice number `KVO17-0001` and invoice date `2026-01-15`
- **WHEN** publication artifact is compiled
- **THEN** the chain contains two `Document_ПоступлениеТоваровУслуг` documents
- **AND** the chain contains two `Document_СчетФактураПолученный` documents
- **AND** each received invoice has `invoice_mode` `required`
- **AND** each received invoice links to exactly one generated receipt through `ДокументыОснования`
- **AND** the received invoices preserve supplier invoice number/date and the row-specific KVO value

### Requirement: KVO17 generated purchase policy MUST not hide technical workarounds for 1C document collapse

If the target 1C configuration requires a technical workaround to keep generated KVO17 purchase documents distinct while preserving the same supplier invoice number/date, the workaround SHALL be explicit in preview, document plan, publication payload, and audit lineage.

The system SHALL NOT silently change supplier invoice number/date, counterparty, amount, or KVO only to avoid 1C collapse.

#### Scenario: Technical split workaround is visible before publication
- **GIVEN** target publication strategy requires a technical identity field to keep two generated receipts distinct
- **WHEN** operator previews generated KVO17 publication
- **THEN** preview shows the technical workaround and its affected fields
- **AND** supplier invoice number/date remain unchanged in the declaration/source lineage
- **AND** operator can distinguish technical publication identity from business invoice identity
