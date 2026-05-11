## ADDED Requirements

### Requirement: KVO 17 purchase split pool MUST be activated through a pinned workflow binding

Система ДОЛЖНА (SHALL) configure the КВО 17 purchase split pool through a pool-local `pool_workflow_binding` pinned to a reusable binding/profile revision.

The binding profile ДОЛЖЕН (SHALL) expose named publication slots for КВО 01 and КВО 17 purchase branches and include the active classifier rule revision.

Preview/create-run path ДОЛЖЕН (SHALL) fail closed if the selected pool has no active КВО 17 purchase split binding or if required slots are missing.

#### Scenario: Operator launches KVO 17 split through explicit binding
- **GIVEN** a pool has active binding `kvo17_purchase_split` pinned to a compatible profile revision
- **WHEN** operator creates a run from a normalized purchase batch
- **THEN** create-run request references that binding explicitly
- **AND** run lineage records the binding revision, profile revision, classifier rule revision, and document policy slots used

#### Scenario: Missing KVO 17 slot blocks run
- **GIVEN** selected binding profile lacks slot `purchase_kvo17`
- **WHEN** operator previews or creates a КВО 17 purchase split run
- **THEN** system returns missing slot diagnostics
- **AND** no publication workflow starts
