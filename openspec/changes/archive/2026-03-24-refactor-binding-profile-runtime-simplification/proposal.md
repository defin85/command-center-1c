# Change: refactor-binding-profile-runtime-simplification

## Why

Модель `Binding Profiles` как доменная граница выглядит оправданной: она отделяет reusable execution scheme от pool-local activation layer и сохраняет explicit runtime boundary по `pool_workflow_binding_id`.

Проблема в способе внедрения текущей модели:
- shipped attachment path всё ещё опирается на лишнюю денормализацию reusable payload в `pool_workflow_binding`;
- default read path может материализовать generated one-off profile как побочный эффект чтения legacy row;
- `/pools/binding-profiles` считает usage через загрузку нерелевантных pool catalog payload и client-side aggregation.

Это увеличивает связность, делает read path stateful и размывает source-of-truth между pinned `binding_profile_revision_id` и attachment row.

## What Changes

- Зафиксировать `pool_workflow_binding` как thin pool-local activation layer, где authoritative mutable state ограничен pool-local scope и ссылкой на pinned `binding_profile_revision_id`.
- Разрешить `resolved_profile` или эквивалентный convenience read-model только как derived projection из pinned profile revision, а не как вторую primary mutable payload surface attachment-а.
- Запретить state-changing generated profile materialization в shipped list/detail/preview/runtime path; refactor выполняется без remediation/backfill migration path и с destructive reset затронутых `pool`, attachment и `binding_profile*` данных до включения нового контракта.
- Ввести dedicated scoped usage read-model для `/pools/binding-profiles`, чтобы detail workspace не зависел от broad tenant-wide pool catalog hydration.
- Сохранить текущую доменную capability: reusable profiles, explicit attachment runtime identity, deactivation semantics и idempotency по attachment revision + `binding_profile_revision_id`.

## Impact

- Affected specs:
  - `pool-workflow-bindings`
  - `pool-binding-profiles`
- Affected code:
  - `orchestrator/apps/intercompany_pools/workflow_binding_attachments_store.py`
  - `orchestrator/apps/intercompany_pools/workflow_authoring_contract.py`
  - `orchestrator/apps/intercompany_pools/workflow_binding_resolution.py`
  - `orchestrator/apps/intercompany_pools/binding_preview.py`
  - `orchestrator/apps/api_v2/views/intercompany_pools_binding_profiles.py`
  - `frontend/src/pages/Pools/PoolBindingProfilesPage.tsx`
- Rollout assumption:
  - затронутые `pool`, `pool_workflow_binding` и `binding_profile*` записи допускается удалить заранее вместо in-place migration/backfill.
- Related active work:
  - frontend changes around platform workspaces may touch the same `/pools/*` routes, so the UI part of this refactor should preserve current platform-layer composition and avoid route-level regressions.
