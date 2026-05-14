# Change: Add KVO17 Random Purchase Generator

## Why

The current KVO17 purchase split flow normalizes already prepared source rows. The operator-facing need is different: generate purchase receipts from parameters, without preparing a source registry manually.

Operators need to choose a period, counterparties, two amount ranges, and the KVO assigned to each range. For every selected counterparty the system must create two purchase receipts: one for the large amount and one for the small amount, with different KVO values while preserving the same supplier invoice number/date pair.

1C may collapse such documents when they are created interactively. The system must not assume programmatic publication avoids that behavior; it must prove and audit the publication strategy or fail closed.

## What Changes

- Add a KVO17 purchase generation mode that produces a canonical generated batch from operator parameters.
- Let the operator select:
  - accounting period;
  - a set of counterparties;
  - two amount ranges;
  - the target KVO for each range.
- Generate, preview, and persist a deterministic generation manifest with random dates and random amounts chosen inside the selected ranges.
- Create exactly two generated purchase rows/documents per counterparty, one per amount range/KVO branch.
- Preserve the same supplier invoice number/date for the two documents of one counterparty while keeping distinct runtime document identity and idempotency keys.
- Add publication/readback evidence that proves two distinct receipt documents were created, or blocks completion if 1C collapsed them into one document.

## Impact

- Affected specs:
  - `pool-batch-intake`
  - `pool-document-policy`
  - `pool-workflow-bindings`
  - `pool-odata-publication`
  - `ui-frontend-governance`
- Affected code (expected):
  - `orchestrator/apps/intercompany_pools/**`
  - `orchestrator/apps/api_v2/views/intercompany_pools*.py`
  - `contracts/orchestrator/src/**`
  - `contracts/orchestrator/openapi.yaml`
  - `frontend/src/pages/Pools/**`
  - `frontend/src/pages/Pools/*kvo17*`
  - KVO17 bootstrap/binding profile fixtures
