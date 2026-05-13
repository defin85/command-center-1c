## ADDED Requirements

### Requirement: KVO 18 advance VAT pool MUST normalize advance operation rows into staged batches

Система ДОЛЖНА (SHALL) support canonical intake for the КВО 18 advance VAT offset pool from manual operator input or uploaded rows.

Each normalized operation row ДОЛЖЕН (SHALL) contain:
- counterparty;
- contract;
- date;
- amount;
- VAT rate and VAT amount;
- currency;
- deterministic row identity;
- optional source reference.

Intake ДОЛЖЕН (SHALL) work through the public `schema_template_upload` batch path and fail closed before ПКО or invoice creation if required fields are missing, cannot be mapped, or row identity is duplicated.

#### Scenario: Operator enters advance rows for KVO 18 workflow
- **GIVEN** operator enters counterparty, contract, amount and VAT rate for one or more advance operations
- **WHEN** КВО 18 advance VAT intake runs
- **THEN** system creates a canonical staged batch
- **AND** each row is eligible for ПКО creation with row-level lineage

#### Scenario: Missing contract blocks advance intake
- **GIVEN** an advance operation row has counterparty and amount but no contract
- **WHEN** operator starts intake for the КВО 18 pool
- **THEN** intake fails before document creation
- **AND** diagnostic output identifies the missing contract mapping

#### Scenario: Uploaded KVO 18 schema template starts a staged receipt batch
- **GIVEN** operator selected the public КВО 18 advance VAT schema template and a compatible top-down workflow binding
- **WHEN** the operator submits advance rows through the canonical batch intake endpoint
- **THEN** system creates a receipt `PoolBatch` with КВО 18 policy metadata, staged slots, row lineage, and total amount/VAT summary
- **AND** the linked run input records the selected stage intent, policy revision, content hash, and document policy slots

#### Scenario: Duplicate row identity blocks KVO 18 intake
- **GIVEN** two uploaded advance rows contain the same deterministic row identity
- **WHEN** operator submits the КВО 18 intake
- **THEN** intake fails before document creation
- **AND** diagnostics identify the duplicate row identity

### Requirement: KVO 18 advance VAT pool MUST track per-stage row state

Система ДОЛЖНА (SHALL) track each normalized advance operation row through staged states:
- ready for ПКО;
- ПКО created;
- advance invoice КВО 01 created;
- offset КВО 18 formed;
- declaration evidence verified.

Downstream stages НЕ ДОЛЖНЫ (SHALL NOT) run for a row until required prior-stage state and evidence are present.

#### Scenario: Invoice stage waits for PКO state
- **GIVEN** an advance row is normalized but no linked ПКО exists
- **WHEN** operator tries to create an advance invoice for that row
- **THEN** system blocks the invoice stage
- **AND** reports that ПКО creation is required first
