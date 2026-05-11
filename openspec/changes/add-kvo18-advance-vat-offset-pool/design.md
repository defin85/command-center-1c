## Context

The КВО 18 source document describes a workflow:

1. Create `Приходный кассовый ордер` from manual input or upload.
2. Create `Счет-фактура выданный (на аванс)` from the ПКО with КВО 01.
3. Form an advance offset so КВО 18 appears in the purchase book.
4. Ensure the result reaches the VAT declaration.

The source also states that type 1C produces КВО 18 only on advance offset and suggests creating a large enough `Реализация товаров и услуг`, then unposting it after use. That behavior is high-risk if hidden, so it must be expressed as a policy-controlled workflow with preview and audit.

## Goals

- Configure a reusable pool scheme for advance VAT КВО 01/18.
- Support both manual input and upload of advance operation rows.
- Produce auditable document chain: ПКО -> advance issued invoice КВО 01 -> offset КВО 18.
- Make technical realization/unposting behavior explicit and stateful.
- Verify sales book and purchase book outcomes before declaring the scheme successful.

## Non-Goals

- Do not implement arbitrary VAT declaration editing outside 1C.
- Do not hide a temporary realization document behind an untracked side effect.
- Do not support partial silent offset when some ПКО rows fail validation.
- Do not make КВО 18 generation available without explicit operator preview/confirmation.

## Decisions

### Decision: Model the workflow as a staged pool scheme

The scheme exposes staged actions:

- `create_cash_receipt_order`;
- `create_advance_invoice_kvo01`;
- `form_advance_offset_kvo18`.

Each stage must be idempotent and linked through run lineage.

### Decision: Technical realization is explicit policy, not a hidden implementation detail

If realization is required to trigger advance offset, the policy must define:

- how realization amount is chosen;
- which counterparty/contract is used;
- whether it remains posted, is unposted, or is reversed;
- what audit evidence proves the final book/declaration state.

### Decision: Final acceptance is book/declaration evidence

The run is not complete only because documents were created. Acceptance requires evidence that:

- advance invoice contributes КВО 01 to the sales book;
- offset contributes КВО 18 to the purchase book;
- final declaration-facing projection contains both outcomes.

## Risks / Trade-offs

- Technical realization/unposting can be tax-sensitive. Mitigation: require explicit policy, preview, and audit trail.
- A single large realization covering many ПКО rows can create complex partial failure behavior. Mitigation: staged status per operation row and fail-closed before offset publication when coverage is incomplete.
- Target configuration may require different document fields for ПКО/invoice/offset. Mitigation: metadata-aware completeness profiles and blocked preview on missing fields.

## Open Questions

- Should the technical realization amount equal total ПКО amount or exceed it by a configured margin?
- Should the workflow automatically unpost the technical realization after КВО 18 appears, or stop for operator confirmation?
- Which 1C register/book readback is canonical proof for КВО 01/18 in this configuration?
