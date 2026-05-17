## Context

`add-kvo17-purchase-split-pool` delivered the first KVO17 split layer: normalize source rows, classify by amount, compile two document-policy slots, and preserve supplier provenance. The new requirement is not an upload/normalization problem. It is an operator-controlled generator that produces the source rows itself.

The key runtime uncertainty is 1C behavior. When a user creates two receipt documents with the same supplier invoice number/date and different KVO interactively, 1C may collapse them into one. Programmatic OData/1C publication may or may not bypass that behavior. This change treats that as a verification target, not an assumption.

## Locked Decisions

- The uploaded KVO17 split classifier can remain as a legacy intake helper, but generated KVO17 publication uses one dedicated document-policy slot: `kvo17_generated_purchase_pair`.
- Generated purchase publication MUST NOT require two topology branch slots when both generated receipts target the same `Organization.database`; it materializes one publication edge/chain with receipt and invoice documents.
- The generated mode is a new source mode for KVO17, not a silent replacement for uploaded source-registry intake.
- One selected counterparty produces exactly two generated purchase documents: one per configured amount range.
- The two documents for a counterparty share supplier invoice number and supplier invoice date.
- The two documents for a counterparty must have different KVO values.
- Random dates and amounts must be previewed and persisted before publication; create-run/retry must not re-roll values.

## Decisions

### Deterministic Randomization

Random generation is backed by a stored generation seed and a generated manifest. Preview and create-run use the same canonical manifest:

- `period_start`, `period_end`;
- selected counterparty refs/names;
- two amount ranges;
- KVO assignment per range;
- seed;
- generated supplier invoice number/date per counterparty;
- generated row amount/VAT amount/KVO per range;
- row identity and idempotency keys.

If the operator reopens preview for the same draft, the generated values remain stable unless they explicitly regenerate the seed.

### Generated Source Identity

The generated supplier invoice number/date is source identity for declaration and invoice fields, not necessarily the internal 1C receipt document number. Runtime document identity must stay distinct through external keys/idempotency metadata so that two documents can be read back and audited independently.

### One-Edge Document Materialization

The generated mode compiles a standard `document_plan_artifact.v1` directly from the accepted manifest. For each selected counterparty, the artifact uses one target database edge and one chain containing two purchase receipt documents and two linked received invoice documents. The generated policy lineage points at `kvo17_generated_purchase_pair`; the topology graph does not model `purchase_kvo01` and `purchase_kvo17` as two separate child nodes when the target database is physically the same.

This reuses the already-supported document-policy shape where one decision/chain can emit multiple documents for one edge, and avoids inventing parallel graph edges solely to separate KVO values.

### 1C Collapse Handling

The implementation must include a live 1C verification step or an equivalent integration test against the target publication path. Success requires readback evidence that two distinct receipt documents exist for one counterparty with:

- the same supplier invoice number/date;
- different KVO values;
- expected generated amounts;
- distinct document refs/external keys.

If readback returns one collapsed document, ambiguous documents, or missing KVO separation, the run must end in a blocking publication diagnostic rather than marking the stage complete.

### Scheme-Specific Operator Surface

The KVO17 generator must use a scheme-specific operator UI module rather than extending the generic JSON/schema-template drawer with more conditional controls.

The shared layer should own:

- selected pool, period, and workflow binding context;
- active binding compatibility and blocking diagnostics;
- preview/create-run lifecycle;
- generated OpenAPI client calls;
- shared validation/error presentation primitives;
- canonical `DrawerFormShell` / platform composition and i18n boundaries.

The KVO17 generator module should own:

- counterparty multi-select;
- two amount range editors;
- KVO assignment controls for the ranges;
- seed/regenerate controls;
- generated manifest preview;
- collapse/readback risk presentation;
- scheme-specific blocked submit rules.

This establishes the preferred pattern for future high-ceremony "schematos": each scheme can provide an original operator surface while reusing the same platform shell, API lifecycle, binding compatibility checks, diagnostics model, and run lineage mechanics.

## Alternatives Considered

- Treat the generated rows as if they were uploaded rows only: rejected, because the UI needs first-class parameter selection, deterministic randomization, and no manual source file.
- Put all scheme-specific controls into `PoolBatchIntakeDrawer`: rejected, because the existing drawer already contains KVO17/KVO18 conditional preview logic and would become a brittle cross-scheme component if it also owned generated-parameter authoring.
- Assume OData publication bypasses interactive collapse: rejected, because this is exactly the risky runtime behavior that must be proven.
- Change supplier invoice number/date to avoid collapse: rejected for the default path, because the user requirement explicitly requires the same invoice number/date pair.

## Risks / Trade-offs

- 1C may enforce collapse even for programmatic creation. Mitigation: readback gate and explicit blocker; introduce only an approved workaround if live proof fails.
- Random generation can become non-reproducible. Mitigation: stored seed and manifest, no hidden re-roll on submit/retry.
- Counterparty selection can reference stale/unbound master data. Mitigation: generated preview must resolve target counterparty/contract refs before create-run.
- Duplicate supplier invoice identity may collide with existing target documents. Mitigation: preflight/readback diagnostics must distinguish expected two generated documents from pre-existing documents.
- Scheme-specific UI can drift from common pool workflow semantics. Mitigation: use a small shared intake shell/registry contract for pool, period, binding, preview, create-run, diagnostics, and lineage, while keeping only scheme input composition custom.

## Open Questions

- Should amount ranges be required to be non-overlapping, or is explicit KVO assignment enough?
- Should the generated supplier invoice number format be configurable per tenant, or fixed for the first KVO17 generator release?
- Which exact 1C fields/registers carry KVO for the target configuration in the generated purchase document path?
- Should future schemes use drawer-contained surfaces by default, or should multi-step/high-risk schemes graduate to a dedicated route/workspace when preview/readback evidence becomes too large for a drawer?
