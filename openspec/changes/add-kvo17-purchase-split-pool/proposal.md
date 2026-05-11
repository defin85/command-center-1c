# Change: Add KVO 17 Purchase Split Pool

## Why

User-provided source TЗ `C:\Users\Egor\Downloads\ТЕХЗАДАНИЕ НА КВО 17.docx` describes a manual workaround for supplier purchase documents that contain one source number/date but must be reflected with different VAT operation codes: large purchase amounts as КВО 01 and small amounts as КВО 17.

Current manual handling copies receipt documents, changes amounts, changes КВО, temporarily substitutes supplier identity, and then fixes declaration output in SBIS. This is not auditable or repeatable enough for a pool-backed process.

## What Changes

- Add a dedicated pool scheme for КВО 17 purchase splitting.
- Normalize a supplier purchase registry/source document into canonical batch rows with source document provenance.
- Classify rows into КВО 01 and КВО 17 branches using explicit scheme rules, including a configurable small-amount threshold with default `100 RUB`.
- Compile separate document-policy slots for КВО 01 and КВО 17 while preserving the original supplier provenance for declaration/export.
- Provide preview diagnostics for split counts, sums, source document identity, and declaration impact before publication.
- Fail closed on ambiguous split rules, missing source document identity, missing supplier provenance, or duplicate source rows.

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

- Source ТЗ states that one supplier shipment has common source number/date, but rows must be reflected as КВО 01 and КВО 17.
- Source ТЗ describes current manual supplier substitution only as a workaround. This change treats original supplier preservation as a first-class provenance requirement, not as an invisible side effect.
