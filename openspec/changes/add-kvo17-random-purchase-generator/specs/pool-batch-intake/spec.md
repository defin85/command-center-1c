## ADDED Requirements

### Requirement: KVO17 generated purchase intake MUST create a deterministic manifest from operator parameters

Система ДОЛЖНА (SHALL) support a KVO17 generated purchase intake mode where the operator selects:

- `period_start` and `period_end`;
- one or more counterparties;
- two positive amount ranges;
- a KVO assignment for each amount range;
- a generation seed or explicit regenerate action.

The two amount ranges MUST map to different KVO values from the supported KVO set. The first release MUST support `01` and `17`.

The generated intake MUST produce a canonical manifest before run creation. The manifest MUST include the selected parameters, seed, generated dates, generated amounts, generated supplier invoice number/date, generated row identity, and KVO assignment for every generated row.

#### Scenario: Operator previews generated KVO17 purchases
- **GIVEN** operator selected a valid period, three counterparties, two amount ranges, and different KVO values for the ranges
- **WHEN** operator requests KVO17 generated purchase preview
- **THEN** system creates a deterministic generation manifest with six generated rows
- **AND** every selected counterparty has exactly two generated rows
- **AND** every generated row contains amount, VAT fields, source invoice identity, row identity, KVO assignment, and generation seed lineage

#### Scenario: Invalid generation parameters block preview
- **GIVEN** operator selected no counterparties or assigned the same KVO to both ranges
- **WHEN** operator requests generated KVO17 preview
- **THEN** preview fails before run creation
- **AND** no generated batch, run, receipt document, or publication task is created

### Requirement: KVO17 generated purchase intake MUST choose dates and amounts inside selected ranges without re-rolling on submit

For each selected counterparty, the system SHALL choose a random supplier invoice date inside the selected period and one random amount inside each configured amount range.

The generated date for the two rows of one counterparty MUST be the same. The generated amounts for those two rows MUST remain within their respective amount ranges.

Preview, create-run, retry, and readback MUST use the same persisted manifest values. The system MUST NOT re-roll dates or amounts implicitly after preview has been accepted.

#### Scenario: Generated values stay stable from preview to create-run
- **GIVEN** operator previewed generated KVO17 purchases with seed `seed-1`
- **AND** preview shows counterparty `supplier-001` with invoice date `2026-01-15`, small amount `57.25`, and large amount `250.40`
- **WHEN** operator creates the run from that preview
- **THEN** run input stores the same generated date and amounts
- **AND** publication/retry uses those stored values rather than generating new random values

#### Scenario: Generated values respect selected bounds
- **GIVEN** operator selected period `2026-01-01..2026-01-31`, small amount range `50..100`, and large amount range `200..300`
- **WHEN** generated preview is built
- **THEN** every generated supplier invoice date is between `2026-01-01` and `2026-01-31`
- **AND** every small-row amount is between `50` and `100`
- **AND** every large-row amount is between `200` and `300`
