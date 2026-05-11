## ADDED Requirements

### Requirement: KVO 17 purchase split policy MUST materialize separate KVO 01 and KVO 17 receipt document slots

Система ДОЛЖНА (SHALL) compile КВО 17 purchase split scheme into deterministic document policy slots for:
- `purchase_kvo01`;
- `purchase_kvo17`.

Each slot ДОЛЖЕН (SHALL) produce receipt document chain data with the correct КВО value, source document lineage, VAT fields, and supplier provenance required for declaration output.

The policy НЕ ДОЛЖНА (SHALL NOT) silently collapse КВО 01 and КВО 17 rows into one receipt document when the target 1C configuration permits only one КВО per receipt document.

#### Scenario: One source document produces two KVO document branches
- **GIVEN** one supplier source document contains rows classified as КВО 01 and КВО 17
- **WHEN** document policy compile runs for the КВО 17 purchase split pool
- **THEN** compiled document plan contains separate КВО 01 and КВО 17 document branches
- **AND** each branch preserves source document number/date and original supplier provenance in lineage

### Requirement: KVO 17 purchase split policy MUST make technical supplier substitution explicit when required

If target 1C behavior requires technical document identity separation to avoid merge/collapse, system ДОЛЖНА (SHALL) represent that as explicit policy metadata and lineage, not as silent supplier mutation.

Original supplier identity ДОЛЖНА (SHALL) remain the declaration/export provenance source.

Any technical counterparty or document identity workaround ДОЛЖЕН (SHALL) be visible in preview and audit artifacts before publication.

#### Scenario: Technical identity workaround is visible before publication
- **GIVEN** active target configuration requires a technical counterparty or document identity split to publish КВО 17 rows
- **WHEN** operator previews the КВО 17 purchase split run
- **THEN** preview shows the technical workaround and original supplier mapping
- **AND** operator can verify that declaration/export provenance still points to the original supplier
