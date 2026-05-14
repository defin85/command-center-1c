## ADDED Requirements

### Requirement: KVO17 generated purchase publication MUST prove that 1C kept split documents distinct

For generated KVO17 purchase runs, publication SHALL read back the created receipt documents after write operations and verify that each selected counterparty has exactly two generated receipt documents from the accepted manifest.

Publication SHALL also create and read back one linked received invoice document (`Document_СчетФактураПолученный`) for each generated receipt. Readback evidence MUST prove that every received invoice has a distinct 1C ref, preserves the expected supplier invoice number/date and KVO, and links back to the exact generated receipt through `ДокументыОснования`.

Readback evidence MUST prove, for every selected counterparty:

- both generated documents exist as distinct 1C refs or stable document identities;
- both documents share the expected supplier invoice number/date;
- the documents have different KVO values according to the accepted range mapping;
- amounts and VAT values match the accepted generated manifest;
- both linked received invoice documents exist as distinct 1C refs and point to the corresponding receipt refs;
- no unexpected merge/collapse occurred.

If readback returns one collapsed document, more than two ambiguous generated documents, missing KVO separation, or missing amount evidence, publication SHALL finish in a blocking state and MUST NOT mark the KVO17 generated stage complete.

#### Scenario: Programmatic publication creates two distinct generated receipts
- **GIVEN** accepted generated manifest contains counterparty `supplier-001` with two rows sharing invoice number `KVO17-0001` and invoice date `2026-01-15`
- **WHEN** publication writes the two generated receipts to 1C and performs readback
- **THEN** readback evidence contains two distinct 1C document refs
- **AND** both refs have invoice number `KVO17-0001` and invoice date `2026-01-15`
- **AND** one ref has KVO `17` and the other has KVO `01`
- **AND** readback evidence contains two linked received invoice refs for the same generated rows
- **AND** publication may mark that counterparty complete

#### Scenario: Programmatic publication creates linked received invoices
- **GIVEN** accepted generated manifest contains counterparty `supplier-001` with two generated receipts
- **WHEN** publication writes the receipts and received invoices to 1C and performs readback
- **THEN** readback evidence contains two distinct `Document_СчетФактураПолученный` refs
- **AND** each received invoice has the expected supplier invoice number/date
- **AND** each received invoice has the row-specific KVO
- **AND** each received invoice has `ДокументыОснования[0].ДокументОснование` equal to its generated receipt ref

#### Scenario: 1C collapses generated receipts into one document
- **GIVEN** accepted generated manifest contains two generated rows for counterparty `supplier-001`
- **WHEN** publication/readback observes only one resulting 1C receipt document for the shared invoice identity
- **THEN** publication returns a blocking diagnostic for KVO17 document collapse
- **AND** run/stage status does not claim successful document creation
- **AND** audit lineage preserves the attempted manifest and readback evidence
