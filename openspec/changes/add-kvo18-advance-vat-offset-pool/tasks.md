## 1. Contract And Scheme Assets

- [x] 1.1 Define the КВО 18 advance VAT pool scheme fixture/seed with topology, binding profile revision, document policy slots, and explicit staged workflow metadata.
- [x] 1.2 Define canonical intake schema for advance operation rows: counterparty, contract, date, amount, VAT rate, VAT amount, currency, row identity, and optional source reference.
- [x] 1.3 Define technical realization/offset policy fields: amount rule, document state after offset, confirmation gates, and audit evidence requirements.

## 2. Backend Runtime

- [x] 2.1 Implement batch normalization for manual/uploaded advance rows.
- [x] 2.2 Implement staged runtime actions for creating ПКО, creating advance invoices with КВО 01, and forming advance offset with КВО 18.
- [x] 2.3 Compile document policy into deterministic document plan artifacts for ПКО, advance invoice, technical realization/offset, and post-offset state.
- [x] 2.4 Preserve row-level lineage from input row through ПКО, invoice, offset, book entries, and declaration-facing evidence.
- [x] 2.5 Enforce idempotency and partial failure handling per operation row and per stage.

## 3. Operator UI

- [x] 3.1 Add scheme selection/read model so operators can choose the КВО 18 advance VAT offset pool.
- [x] 3.2 Provide staged controls: `Создать ПКО`, `Создать СФ на аванс`, `Сформировать зачет (КВО 18)`.
- [x] 3.3 Show preview and execution evidence for sales book КВО 01, purchase book КВО 18, technical realization state, and declaration readiness.
- [x] 3.4 Block downstream stages until required prior-stage documents and evidence exist.

## 4. Verification

- [x] 4.1 Add backend tests for intake normalization, staged idempotency, required fields, and partial failure handling.
- [x] 4.2 Add document policy compile tests for ПКО, advance invoice КВО 01, offset КВО 18, and technical realization state.
- [x] 4.3 Add frontend/operator tests for staged controls, blocked states, and evidence display.
- [x] 4.4 Run relevant pool backend tests, frontend focused tests, contract validation, and `openspec validate add-kvo18-advance-vat-offset-pool --strict --no-interactive`.

## 5. Review Blocker Closure

- [x] 5.1 Wire KVO 18 schema-template intake into the public `POST /pool-batches` path with lineage metadata and duplicate row identity fail-closed behavior.
- [x] 5.2 Publish KVO 18 staged workflow aliases through the pool runtime template registry and route them through pool-domain runtime execution.
- [x] 5.3 Bind ready KVO 18 UI staged controls to bounded stage submit metadata and block submit/stage actions on blocking diagnostics.
- [x] 5.4 Re-run focused backend/frontend gates plus strict OpenSpec validation for the blocker closure.
