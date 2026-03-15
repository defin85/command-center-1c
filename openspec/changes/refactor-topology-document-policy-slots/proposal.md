# Change: refactor-topology-document-policy-slots

## Почему

Сейчас workflow-centric path не умеет точно выразить, какой тип документов нужно создавать для конкретной target-организации внутри одного `pool run`: binding preview/materialization выбирает один `compiled_document_policy` на весь binding/run, а не per edge/per target.

Одновременно `Topology Editor` все еще тащит legacy `edge.metadata.document_policy`, из-за чего structural topology и document-policy authoring остаются смешанными в одном surface.

## Что меняется

- `Topology` становится местом выбора publication slot на уровне ребра через lightweight selector `edge.metadata.document_policy_key`.
- `Topology Editor` требует явного UI-рефакторинга: вместо legacy policy panel он становится edge slot assignment workspace с coverage/remediation diagnostics.
- `Bindings` сохраняются как canonical pinning/deployment layer и требуют analyst-friendly UI-рефакторинга: named slots, coverage matrix и remediation вместо low-level списка raw decision refs.
- `/decisions` остается canonical authoring surface для concrete `document_policy` revisions.
- Runtime компилирует `document_plan_artifact` per edge/per target, резолвя `document_policy_key -> binding decision ref -> compiled document_policy`.
- Preview/read-model контракт меняется с single `compiled_document_policy` на slot-based projection с coverage и unresolved diagnostics.
- Runtime lineage и retry переходят на slot-based snapshot вместо single policy blob.
- `Workflows` остаются orchestration-only surface и не получают per-edge matrix "какой документ создавать в какой организации".
- **BREAKING** `Topology Editor` перестает быть shipped surface для legacy `document_policy` authoring/import.
- **BREAKING** runtime cutover убирает legacy fallback на `edge.metadata.document_policy` и `pool.metadata.document_policy` из штатного preview/run path.

## Impact

- Affected specs:
  - `organization-pool-catalog`
  - `pool-document-policy`
  - `pool-workflow-bindings`
  - `pool-workflow-execution-core`
  - `workflow-decision-modeling`
- Affected code:
  - topology editor и pool catalog UI
  - bindings workspace и run/binding preview UI
  - binding preview / run preview
  - execution context / lineage / retry contract
  - public preview/read-model API contract
  - document plan compile и runtime projection
  - legacy migration/remediation flows для `document_policy`
