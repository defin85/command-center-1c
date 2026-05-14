## ADDED Requirements

### Requirement: KVO17 generated purchase mode MUST require an active compatible workflow binding

Система ДОЛЖНА (SHALL) expose KVO17 generated purchase mode only when the selected pool has an active `pool_workflow_binding` whose pinned execution pack declares support for generated KVO17 purchases and contains the required document-policy slots.

Required slots for the first release are:

- `purchase_kvo01`;
- `purchase_kvo17`.

If the active binding is missing generated KVO17 capability metadata, required slots, or target publication compatibility, preview/create-run SHALL fail closed with machine-readable diagnostics.

#### Scenario: Missing generated capability blocks KVO17 generator
- **GIVEN** selected pool has an active binding with `purchase_kvo01` and `purchase_kvo17` slots
- **AND** the pinned execution pack does not declare generated KVO17 purchase support
- **WHEN** operator opens KVO17 generated purchase mode
- **THEN** UI marks generated mode unavailable or blocked
- **AND** backend preview/create-run rejects the request with a machine-readable capability diagnostic

#### Scenario: Compatible binding enables KVO17 generator
- **GIVEN** selected pool has an active binding whose execution pack declares generated KVO17 purchase support
- **AND** the binding contains `purchase_kvo01` and `purchase_kvo17` slots
- **WHEN** operator opens KVO17 generated purchase mode
- **THEN** UI allows parameter selection and preview
- **AND** run lineage records the selected binding and execution-pack revision
