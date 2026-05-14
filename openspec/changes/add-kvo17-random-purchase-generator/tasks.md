## 1. Contract and Generator Core

- [x] 1.1 Define generated KVO17 purchase request/manifest schemas, including period, counterparties, amount ranges, KVO assignment, seed, generated invoice identity, and row ids.
- [x] 1.2 Implement deterministic generator service with stable preview/create-run manifest reuse.
- [x] 1.3 Add backend validation for invalid periods, empty counterparty selection, invalid amount ranges, duplicate KVO assignment, stale counterparty refs, and non-reproducible manifests.
- [x] 1.4 Add backend tests for random date/amount bounds, two rows per counterparty, shared invoice identity per pair, distinct KVO values, and idempotency.

## 2. Runtime and Publication

- [x] 2.1 Wire generated manifests into the existing KVO17 `purchase_kvo01` / `purchase_kvo17` document-policy slots.
- [x] 2.2 Preserve shared supplier invoice number/date while generating distinct runtime document identities and idempotency keys.
- [x] 2.3 Add preflight/readback diagnostics for existing duplicate invoice identity and target master-data resolution.
- [x] 2.4 Prove live 1C/OData publication behavior for two generated receipts with the same invoice number/date and different KVO.
- [x] 2.5 Fail closed with machine-readable diagnostics if 1C collapses the generated documents or readback cannot prove two distinct receipts.
- [x] 2.6 Represent generated KVO17 publication as one target database edge with two purchase documents per counterparty, without requiring parallel topology branch slots for the same database.
- [x] 2.7 Create a linked received invoice document (`Document_СчетФактураПолученный`) for each generated receipt, preserving the same supplier invoice number/date and binding the invoice to its receipt through `ДокументыОснования`.

## 3. API, Contracts, and Frontend

- [x] 3.1 Add public API contract for KVO17 generated preview/create-run payloads and regenerate clients.
- [x] 3.2 Extract or introduce a shared scheme-intake shell/registry boundary so `PoolBatchIntakeDrawer` does not accumulate another hardcoded high-ceremony scheme.
- [x] 3.3 Add a scheme-specific KVO17 generated purchase UI module with period, counterparty multiselect, two amount ranges, KVO per range, seed/regenerate, preview, and create-run controls.
- [x] 3.4 Add frontend tests for generated preview, validation errors, manifest stability, blocked submit states, and shell/registry routing.
- [x] 3.5 Ensure generated mode is available only when an active compatible KVO17 workflow binding is selected.

## 4. Verification

- [x] 4.1 Run focused Django tests for KVO17 generation, manifest persistence, document plan, and publication readback diagnostics.
- [x] 4.2 Run focused frontend Vitest tests for the KVO17 generator UI.
- [x] 4.3 Run contract validation and generated-client drift checks.
- [x] 4.4 Run `openspec validate add-kvo17-random-purchase-generator --strict --no-interactive`.
- [x] 4.5 Capture live/manual 1C evidence for the collapse-or-two-documents behavior before marking implementation complete.

Live evidence: run `acbb0d17-570f-4230-a9c5-39acedae99e9` on target DB `e05e258a-c5c8-4350-98a2-ceee13febe38` published two `Document_ПоступлениеТоваровУслуг` refs (`5a3282d8-4fad-11f1-9b47-000c29b79fe4`, `59845654-4fad-11f1-9b47-000c29b79fe4`) with shared supplier invoice `KVO17-0001-B8EDEACD` / `2026-05-05`, KVO `17` and `01`, plus two linked `Document_СчетФактураПолученный` refs (`5a793a98-4fad-11f1-9b47-000c29b79fe4`, `59f7d99e-4fad-11f1-9b47-000c29b79fe4`) whose `ДокументыОснования[0].ДокументОснование` values equal the corresponding receipt refs.
