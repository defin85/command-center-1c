# Change: topology-aware authoring для reusable templates и execution packs

## Why
Runtime уже поддерживает topology-aware master-data aliases для `document_policy.v1`, но operator-facing producer path пока не фиксирует их как обязательный contract для новых/revised reusable topology templates и execution packs.

Из-за этого простая правка topology template не гарантирует reusable path без hardcoded `organization/counterparty/contract` refs: concrete participant refs всё ещё могут оставаться в decision revisions, pinned в execution pack.

## What Changes
- закрепить compatibility contract между `topology_template_revision` и `execution-pack revision`, который различает:
  - structural slot coverage;
  - topology-aware master-data readiness для topology-derived participants;
- закрепить authoring contract для canonical `/pools/execution-packs`: все новые и новые ревизии reusable execution packs НЕ ДОЛЖНЫ использовать hardcoded concrete refs для topology-derived `party/contract` полей и ДОЛЖНЫ публиковаться только через topology-aware aliases;
- закрепить stable machine-readable diagnostics для producer и consumer path, если reusable execution pack остаётся concrete-ref-bound;
- закрепить pool assembly contract в `/pools/catalog`: template-based path использует `slot_key -> organization_id` и alias-aware reusable execution packs, а incompatible execution pack блокирует attach/preview/save/run с handoff в canonical authoring surfaces.

## Impact
- Affected specs:
  - `pool-topology-templates`
  - `pool-binding-profiles`
  - `organization-pool-catalog`
- Runtime dependencies reused as-is:
  - `pool-document-policy`
  - `pool-master-data-hub`
- Affected code later:
  - topology/execution-pack compatibility read models
  - execution-pack create/revise validation and diagnostics
  - `/pools/execution-packs` authoring/inspect diagnostics
  - `/pools/catalog` template-based attach/preview/save diagnostics and handoffs

## Вне scope
- automatic conversion или remediation historical `pool`, `top-down-pool`, `execution-pack` и attachment rows;
- новый DSL для `document_policy` сверх уже shipped topology-aware alias contract;
- inline редактирование reusable decision payload в `/pools/catalog`.
