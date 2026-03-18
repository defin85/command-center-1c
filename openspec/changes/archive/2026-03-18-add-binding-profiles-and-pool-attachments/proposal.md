# Change: add-binding-profiles-and-pool-attachments

## Why

Сейчас `pool_workflow_binding` живет только внутри одного `pool`. Это делает повторное использование типовой схемы распределения между несколькими пулами невозможным без копирования binding payload.

Copy-paste bindings между пулами быстро приводит к drift:
- одинаковая схема начинает расходиться по `workflow_revision`, slot map и parameters;
- массовое обновление типовой схемы требует ручного обхода множества пулов;
- аналитик не видит, где заканчивается reusable схема и где начинаются pool-specific activation rules.

При этом runtime уже опирается на explicit `pool_workflow_binding_id` и pool-specific effective scope, поэтому shared live binding на несколько пулов будет смешивать reusable логику и pool-local lifecycle в одной записи.

## What Changes

- Вводится tenant-scoped reusable сущность `binding_profile` с immutable `binding_profile_revision`, адресуемой через opaque `binding_profile_revision_id`.
- `binding_profile_revision` становится reusable source-of-truth для:
  - pinned workflow revision;
  - publication slot map / decision refs;
  - default parameters;
  - role mapping.
- Reuse на уровне `workflow` сохраняется как reusable orchestration layer, но НЕ заменяет `binding_profile_revision` как reusable execution scheme для pool runtime.
- `pool_workflow_binding` сохраняется как pool-scoped runtime record, но трактуется как attachment к конкретной `binding_profile_revision_id`, а не как primary место хранения reusable логики.
- Public run/preview path продолжает использовать explicit `pool_workflow_binding_id`; profile revision не подменяет attachment на runtime boundary.
- В MVP attachment НЕ получает локальные overrides для workflow/slots/parameters/role mapping. Для pool-specific вариации создаётся новая profile revision или отдельный profile.
- Аналитик получает dedicated binding profile catalog на отдельном route/page `/pools/binding-profiles` как primary authoring surface для reusable схем; `/pools/catalog` binding workspace управляет attachment-ами и выбором profile revision для конкретного pool.
- `deactivate` для profile блокирует новые attach/re-attach и выпуск новых revisions, но НЕ ломает уже существующие attachment-ы, pinned на существующие revisions; для аварийного жёсткого запрета нужен отдельный future `revoke` semantics.
- Run idempotency fingerprint расширяется: кроме `pool_workflow_binding_id` в него входят и `attachment revision`, и `binding_profile_revision_id`, чтобы reattach или repin на новую reusable логику не reuse'или старый run.
- Migration/backfill переводит существующие pool bindings в generated one-off profiles + pool attachments без попытки auto-deduplicate похожие binding-ы между пулами.

## Impact

- Affected specs:
  - `pool-binding-profiles` (new)
  - `pool-workflow-bindings`
  - `pool-distribution-runs`
  - `organization-pool-catalog`
- Related active changes:
  - proposal зависит от slot-oriented binding model из `refactor-topology-document-policy-slots`; reuse profile revisions предполагает, что `slot_key` уже отделён от reusable `decision_key`.
- Affected code:
  - canonical binding store / runtime resolution
  - create-run / binding preview / lineage contracts
  - `/pools/catalog` binding workspace
  - new profile catalog API/UI (`/pools/binding-profiles`, `/api/v2/pools/binding-profiles/*`)
  - migration/backfill tooling для existing pool bindings
