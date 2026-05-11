## 1. Contract And Scheme Assets

- [ ] 1.1 Define the КВО 17 pool scheme fixture/seed with topology, binding profile revision, document policy slots `purchase_kvo01` and `purchase_kvo17`, and explicit scheme metadata.
- [ ] 1.2 Define canonical intake schema for supplier purchase rows: source document number/date, supplier identity, amount, VAT amount/rate, currency, row identifier, and optional override КВО.
- [ ] 1.3 Define split classifier config with default `<= 100 RUB -> КВО 17`, `> 100 RUB -> КВО 01`, plus explicit validation for ambiguous rows.

## 2. Backend Runtime

- [ ] 2.1 Implement batch normalization for the КВО 17 purchase source shape with row-level provenance.
- [ ] 2.2 Implement split preview with counts, sums, КВО branches, duplicate-source diagnostics, and source supplier provenance.
- [ ] 2.3 Compile document policy slots into deterministic document plan artifacts for КВО 01 and КВО 17.
- [ ] 2.4 Preserve original supplier provenance in run lineage and declaration/export-facing artifacts.
- [ ] 2.5 Enforce idempotency for repeated intake/publication of the same source document and split rule revision.

## 3. Operator UI

- [ ] 3.1 Add scheme selection/read model so operators can choose the КВО 17 purchase split pool.
- [ ] 3.2 Show split preview, threshold/rule revision, source document identity, and КВО branch totals before publication.
- [ ] 3.3 Block publication when source supplier, source document identity, row identity, or split classification is incomplete.

## 4. Verification

- [ ] 4.1 Add backend tests for intake normalization, split classification, duplicate detection, and idempotency.
- [ ] 4.2 Add document policy compile tests for КВО 01/17 slot coverage and required document fields.
- [ ] 4.3 Add frontend/operator tests for preview diagnostics and blocked states.
- [ ] 4.4 Run relevant pool backend tests, frontend focused tests, contract validation, and `openspec validate add-kvo17-purchase-split-pool --strict --no-interactive`.
