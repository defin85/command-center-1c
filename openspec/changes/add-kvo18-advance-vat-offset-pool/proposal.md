# Change: Add KVO 18 Advance VAT Offset Pool

## Why

User-provided source ТЗ `C:\Users\Egor\Downloads\техзадание на кво 18.docx` describes an advance VAT workflow where operators need to create cash receipt orders, create advance invoices, and make the VAT reflection appear as КВО 01 in the sales book and КВО 18 in the purchase book.

The current business explanation depends on type 1C behavior: КВО 18 appears only after advance offset. Users propose a technical realization document to force the offset, then unpost it later. This needs a bounded, auditable pool scheme rather than manual document choreography.

## What Changes

- Add a dedicated pool scheme for advance VAT offset КВО 01/18.
- Normalize operator-entered or uploaded advance operation rows into canonical batches.
- Generate ПКО and advance issued invoices with КВО 01 in the sales book.
- Generate an explicit, previewable offset chain that produces КВО 18 in the purchase book.
- Model any technical realization/unposting behavior as explicit policy, state transition, and audit evidence.
- Provide operator controls for the three documented actions: create ПКО, create advance invoice, and form offset КВО 18.

## Impact

- Affected specs:
  - `pool-batch-intake`
  - `pool-document-policy`
  - `pool-workflow-bindings`
- Affected code (expected):
  - `orchestrator/apps/intercompany_pools/**`
  - `orchestrator/apps/api_v2/views/intercompany_pools*.py`
  - `orchestrator/apps/operation_catalog/**`
  - `frontend/src/pages/Pools/**`
  - `contracts/orchestrator/src/**`
  - `contracts/orchestrator/openapi.yaml`
  - scheme fixtures/seeds for pool topology, binding profile, decisions and document policies

## Source Notes

- Source ТЗ requires ПКО input fields: counterparty, contract, amount, VAT rate.
- Source ТЗ expects final declaration evidence: КВО 01 in sales book and КВО 18 in purchase book.
- Source ТЗ says type 1C produces КВО 18 only through advance offset; this change makes that offset path explicit and auditable.
