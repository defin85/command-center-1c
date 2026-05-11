## ADDED Requirements

### Requirement: KVO 18 advance VAT policy MUST materialize PКO and advance invoice KVO 01 chain

Система ДОЛЖНА (SHALL) compile the КВО 18 advance VAT pool policy into a deterministic document chain that creates:
- `Приходный кассовый ордер`;
- `Счет-фактура выданный (на аванс)` with КВО 01.

Advance invoice fields ДОЛЖНЫ (SHALL) be derived from linked ПКО:
- date equals ПКО date;
- amount equals ПКО amount;
- operation kind is advance received;
- VAT fields are filled according to row VAT rate and amount.

#### Scenario: Advance invoice inherits PКO date and amount
- **GIVEN** a normalized row has a linked posted ПКО
- **WHEN** document policy compiles the advance invoice stage
- **THEN** generated advance invoice date and amount match the ПКО
- **AND** generated invoice is marked for КВО 01 sales book reflection

### Requirement: KVO 18 advance VAT policy MUST make offset and technical realization behavior explicit

Система ДОЛЖНА (SHALL) compile an explicit offset policy that can produce КВО 18 in the purchase book through the target 1C advance offset mechanism.

If a technical `Реализация товаров и услуг` document is required, policy ДОЛЖНА (SHALL) define:
- amount rule;
- counterparty/contract source;
- posting/unposting/reversal state after offset;
- linkage to affected ПКО/invoice rows;
- evidence required before marking the stage complete.

System НЕ ДОЛЖНА (SHALL NOT) silently create, post, unpost, or hide technical realization documents outside documented policy and run lineage.

#### Scenario: Technical realization is visible in offset preview
- **GIVEN** active КВО 18 policy requires technical realization to form advance offset
- **WHEN** operator previews the offset stage
- **THEN** preview shows the planned realization amount, linked rows, final document state, and expected КВО 18 purchase book effect
- **AND** publication cannot proceed without explicit operator confirmation when policy marks the step as confirmation-gated

### Requirement: KVO 18 advance VAT policy MUST verify sales and purchase book outcomes

Система ДОЛЖНА (SHALL) treat the КВО 18 workflow as complete only after declaration-facing evidence confirms:
- КВО 01 sales book reflection for advance invoices;
- КВО 18 purchase book reflection after offset.

Document creation without book/declaration evidence НЕ ДОЛЖНО (SHALL NOT) be reported as completed workflow success.

#### Scenario: Workflow remains incomplete until book evidence exists
- **GIVEN** ПКО and advance invoice documents were created
- **AND** offset document chain has not produced КВО 18 purchase book evidence
- **WHEN** operator opens run result
- **THEN** workflow is not marked complete
- **AND** diagnostics explain missing КВО 18 purchase book evidence
