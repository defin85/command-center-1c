## Context

The КВО 17 source document describes a supplier purchase scenario:

- one supplier shipment has a shared source number and date;
- large purchase operations should be reflected with КВО 01;
- small operations up to 100 RUB should be reflected with КВО 17;
- current users manually copy receipt documents and temporarily change supplier identity to avoid document merge, then repair declaration output externally.

The repository already has pool concepts for batch intake, workflow bindings, topology slots, document policies, and document plan artifacts. The new scheme should be expressed through those existing layers instead of introducing a separate one-off processing surface.

## Goals

- Configure a reusable pool scheme for supplier purchase split КВО 01/17.
- Preserve original supplier, source document number/date, and row provenance throughout preview, publication, and declaration export.
- Avoid silent supplier substitution in shipped runtime paths.
- Make split rules explicit, versioned, previewable, and auditable.
- Keep document publication idempotent for repeated intake of the same source document.

## Non-Goals

- Do not implement SBIS-specific post-export editing as the canonical solution.
- Do not create a generic arbitrary tax-code override engine.
- Do not support manual silent fallback from КВО 17 to КВО 01 when source data is incomplete.
- Do not require this change to solve every existing КВО 46 workaround beyond the documented transition into КВО 01/17 split policy.

## Decisions

### Decision: Model the scheme as a pool workflow binding

Create a pool-local attachment pinned to a reusable binding/profile revision for the КВО 17 scheme. The binding exposes named document policy slots:

- `purchase_kvo01`;
- `purchase_kvo17`.

Rationale: this matches the existing workflow-centric authoring and document policy slot model, keeps the scheme reusable, and avoids putting tax logic into mutable pool metadata.

### Decision: Treat original supplier provenance as mandatory

The scheme may create technical documents if the downstream 1C platform requires document separation, but original supplier identity must remain in machine-readable provenance and declaration/export mapping.

Rationale: the source workaround changes supplier manually only to avoid merge behavior. The automated scheme must make that technical behavior explicit and reversible/auditable.

### Decision: Split classification is explicit and versioned

Default classifier:

- amount `<= 100 RUB` -> КВО 17;
- amount `> 100 RUB` -> КВО 01.

The threshold and override rules must live in the versioned scheme/binding/decision layer, not in operator-local ad hoc settings.

## Risks / Trade-offs

- Real 1C document merge behavior may still require technical document identity separation. Mitigation: preview must expose generated document identity strategy and provenance.
- If input files contain only aggregate lines, the system may not be able to split deterministically. Mitigation: fail closed with missing row-level evidence.
- Tax/declaration behavior depends on exact configuration metadata. Mitigation: validate required document fields and KVO register effects before publication.

## Open Questions

- Should the threshold be hard-coded to `100 RUB` or tenant-configurable per scheme revision?
- Is the "large purchase through КВО 46 then group edit to КВО 01" path a migration input, or only historical context?
- Which exact 1C fields/registers hold the КВО value in the target configuration for these receipt documents?
