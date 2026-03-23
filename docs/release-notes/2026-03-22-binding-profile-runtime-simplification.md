# Release Notes — 2026-03-22

## refactor-binding-profile-runtime-simplification

### Что изменилось

- `pool_workflow_binding` shipped contract закреплён как thin attachment: mutable state attachment-а ограничен pool-local scope и pinned `binding_profile_revision_id`.
- `resolved_profile` остаётся derived read-model и больше не должен трактоваться как отдельная mutable payload surface.
- Default shipped path для `/api/v2/pools/workflow-bindings/`, `/api/v2/pools/workflow-bindings/preview/` и `/api/v2/pools/runs/` fail-close на missing или broken `binding_profile` refs с machine-readable diagnostic `POOL_WORKFLOW_BINDING_PROFILE_REFS_MISSING`.
- `/pools/runs` и `/pools/catalog` должны показывать blocking diagnostic вместо silent/generic fallback при unreadable workflow bindings.

### Operator actions

1. Если API или UI возвращает `POOL_WORKFLOW_BINDING_PROFILE_REFS_MISSING`, не запускайте `backfill_pool_workflow_bindings`.
2. Для этого residue canonical remediation — destructive reset затронутых `pool`, `pool_workflow_binding` и `binding_profile*` данных.
3. После reset пересоздайте reusable execution packs в `/pools/execution-packs`, затем заново привяжите attachment-ы в `/pools/catalog`.
4. Перед повторным запуском проверьте preview через `POST /api/v2/pools/workflow-bindings/preview/`.
5. Run стартуйте только после успешного preview через `POST /api/v2/pools/runs/`.

### Notes

- Этот refactor не вводит shipped remediation/backfill flow для historical rows без resolvable profile refs.
- Historical runbook/cutover notes про `backfill_pool_workflow_bindings` относятся к более раннему hardening этапу и не являются актуальным способом remediation для missing `binding_profile` refs.
