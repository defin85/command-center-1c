## ADDED Requirements

### Requirement: KVO17 generated purchase mode MUST require an active compatible workflow binding

Система ДОЛЖНА (SHALL) expose KVO17 generated purchase mode only when the selected pool has an active `pool_workflow_binding` whose pinned execution pack declares support for generated KVO17 purchases and contains the required document-policy slot.

Required slot for the generated-purchase release is:

- `kvo17_generated_purchase_pair`.

If the active binding is missing generated KVO17 capability metadata, the required slot, or target publication compatibility, preview/create-run SHALL fail closed with machine-readable diagnostics.

#### Scenario: Missing generated capability blocks KVO17 generator
- **GIVEN** selected pool has an active binding with the `kvo17_generated_purchase_pair` slot
- **AND** the pinned execution pack does not declare generated KVO17 purchase support
- **WHEN** operator opens KVO17 generated purchase mode
- **THEN** UI marks generated mode unavailable or blocked
- **AND** backend preview/create-run rejects the request with a machine-readable capability diagnostic

#### Scenario: Compatible binding enables KVO17 generator
- **GIVEN** selected pool has an active binding whose execution pack declares generated KVO17 purchase support
- **AND** the binding contains the `kvo17_generated_purchase_pair` slot
- **WHEN** operator opens KVO17 generated purchase mode
- **THEN** UI allows parameter selection and preview
- **AND** run lineage records the selected binding and execution-pack revision
