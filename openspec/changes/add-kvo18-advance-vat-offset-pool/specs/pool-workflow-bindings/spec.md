## ADDED Requirements

### Requirement: KVO 18 advance VAT pool MUST be activated through a staged workflow binding

Система ДОЛЖНА (SHALL) configure the КВО 18 advance VAT offset pool through a pool-local `pool_workflow_binding` pinned to a reusable binding/profile revision.

The binding profile ДОЛЖЕН (SHALL) expose staged slots:
- `cash_receipt_order`;
- `advance_invoice_kvo01`;
- `advance_offset_kvo18`;
- `declaration_evidence`.

Preview/create-run path ДОЛЖЕН (SHALL) fail closed if selected binding lacks any mandatory staged slot.

#### Scenario: Operator launches KVO 18 workflow through explicit binding
- **GIVEN** a pool has active binding `kvo18_advance_vat_offset` pinned to a compatible profile revision
- **WHEN** operator creates a staged run from normalized advance rows
- **THEN** run references that binding explicitly
- **AND** lineage records the binding revision, profile revision, staged slots, and policy revision used

#### Scenario: Missing offset slot blocks KVO 18 workflow
- **GIVEN** selected binding profile defines ПКО and КВО 01 invoice slots but lacks `advance_offset_kvo18`
- **WHEN** operator previews or starts the offset stage
- **THEN** system returns missing slot diagnostics
- **AND** no offset publication is enqueued

### Requirement: KVO 18 advance VAT binding MUST expose operator-visible staged controls

Система ДОЛЖНА (SHALL) expose operator-visible staged controls for the КВО 18 pool that correspond to the source business workflow:
- `Создать ПКО`;
- `Создать СФ на аванс`;
- `Сформировать зачет (КВО 18)`.

Each control ДОЛЖЕН (SHALL) resolve to a bounded workflow stage and respect row/stage prerequisites.

#### Scenario: Offset control is disabled until invoice evidence exists
- **GIVEN** normalized advance rows have created ПКО but no КВО 01 advance invoice evidence
- **WHEN** operator opens the КВО 18 pool staged controls
- **THEN** `Сформировать зачет (КВО 18)` is blocked or disabled
- **AND** UI explains that advance invoice КВО 01 evidence is required first
