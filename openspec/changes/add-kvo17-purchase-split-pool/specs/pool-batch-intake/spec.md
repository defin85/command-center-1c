## ADDED Requirements

### Requirement: KVO 17 purchase split pool MUST normalize supplier source documents into split-ready purchase batches

Система ДОЛЖНА (SHALL) поддерживать canonical intake для dedicated КВО 17 purchase split pool, где один supplier source document может produce rows for different VAT operation codes.

Normalized batch rows ДОЛЖНЫ (SHALL) сохранять:
- source supplier identity;
- source document number and date;
- source row identity or deterministic row fingerprint;
- amount, VAT amount/rate and currency;
- optional source КВО hint or operator-approved override;
- provenance of the input schema/integration.

Intake ДОЛЖЕН (SHALL) fail closed before run creation if source document identity, supplier identity, amount, or row identity cannot be resolved deterministically.

#### Scenario: Supplier source document is normalized for KVO split
- **GIVEN** operator uploads a supplier purchase source document with one source number/date and multiple purchase rows
- **WHEN** КВО 17 purchase split intake runs
- **THEN** system creates a canonical purchase batch with row-level source provenance
- **AND** each row has enough identity and amount data to classify into КВО 01 or КВО 17 before publication

#### Scenario: Missing supplier provenance blocks intake
- **GIVEN** uploaded source rows do not identify the original supplier
- **WHEN** operator starts КВО 17 purchase split intake
- **THEN** intake fails before run creation
- **AND** no receipt documents or declaration-affecting artifacts are created

### Requirement: KVO 17 purchase split pool MUST classify rows with explicit audited rules

Система ДОЛЖНА (SHALL) classify normalized purchase rows into КВО 01 and КВО 17 branches using versioned scheme rules.

Default scheme rule ДОЛЖЕН (SHALL) classify:
- amount `<= 100 RUB` as КВО 17;
- amount `> 100 RUB` as КВО 01.

Tenant/scheme-specific overrides МОГУТ (MAY) exist only as versioned binding/decision data and MUST be visible in preview.

Classification ДОЛЖНА (SHALL) be deterministic and included in batch/run lineage.

#### Scenario: Small rows are routed to KVO 17
- **GIVEN** normalized purchase row amount is `57 RUB`
- **WHEN** split classifier uses the default КВО 17 purchase split rule
- **THEN** row is assigned to КВО 17 branch
- **AND** preview includes the classifier rule revision used for that assignment

#### Scenario: Ambiguous classifier blocks publication
- **GIVEN** row amount or currency cannot be normalized for the active threshold rule
- **WHEN** operator attempts preview or create-run
- **THEN** system returns a blocking machine-readable diagnostic
- **AND** no document publication is enqueued for that row
