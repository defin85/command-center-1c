## 1. Contract And Scheme Assets

- [ ] 1.1 Define the КВО 18 advance VAT pool scheme fixture/seed with topology, binding profile revision, document policy slots, and explicit staged workflow metadata.
- [ ] 1.2 Define canonical intake schema for advance operation rows: counterparty, contract, date, amount, VAT rate, VAT amount, currency, row identity, and optional source reference.
- [ ] 1.3 Define technical realization/offset policy fields: amount rule, document state after offset, confirmation gates, and audit evidence requirements.

## 2. Backend Runtime

- [ ] 2.1 Implement batch normalization for manual/uploaded advance rows.
- [ ] 2.2 Implement staged runtime actions for creating ПКО, creating advance invoices with КВО 01, and forming advance offset with КВО 18.
- [ ] 2.3 Compile document policy into deterministic document plan artifacts for ПКО, advance invoice, technical realization/offset, and post-offset state.
- [ ] 2.4 Preserve row-level lineage from input row through ПКО, invoice, offset, book entries, and declaration-facing evidence.
- [ ] 2.5 Enforce idempotency and partial failure handling per operation row and per stage.

## 3. Operator UI

- [ ] 3.1 Add scheme selection/read model so operators can choose the КВО 18 advance VAT offset pool.
- [ ] 3.2 Provide staged controls: `Создать ПКО`, `Создать СФ на аванс`, `Сформировать зачет (КВО 18)`.
- [ ] 3.3 Show preview and execution evidence for sales book КВО 01, purchase book КВО 18, technical realization state, and declaration readiness.
- [ ] 3.4 Block downstream stages until required prior-stage documents and evidence exist.

## 4. Verification

- [ ] 4.1 Add backend tests for intake normalization, staged idempotency, required fields, and partial failure handling.
- [ ] 4.2 Add document policy compile tests for ПКО, advance invoice КВО 01, offset КВО 18, and technical realization state.
- [ ] 4.3 Add frontend/operator tests for staged controls, blocked states, and evidence display.
- [ ] 4.4 Run relevant pool backend tests, frontend focused tests, contract validation, and `openspec validate add-kvo18-advance-vat-offset-pool --strict --no-interactive`.
