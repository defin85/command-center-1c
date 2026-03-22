# Change: refactor-binding-profiles-into-execution-packs

## Why

После выделения reusable topology layer structural slot-ы перестают быть ответственностью `Binding Profiles`. Они переезжают в `Topology Templates`, а reusable behavior layer фактически остаётся владельцем другого набора данных:
- pinned workflow revision;
- decision refs, реализующих slot-ы;
- default parameters;
- role mapping;
- immutable lineage/provenance.

Текущий термин `Binding Profiles` начинает смешивать две разные идеи:
- structural binding к topology;
- reusable executable pack.

Это ухудшает доменную ясность: operator-facing catalog `/pools/binding-profiles` выглядит как владелец slot namespace, хотя после `add-pool-topology-templates` он должен владеть именно reusable execution logic.

Нужен отдельный change, который:
- упрощает и переосмысляет роль `Binding Profiles`;
- вводит operator/domain термин `Execution Pack`;
- фиксирует разделение ответственности между structural slot graph и executable slot implementations;
- не требует немедленного big-bang удаления existing storage/runtime identifiers `binding_profile*`.

## What Changes

- Зафиксировать новый operator-facing/domain термин `Execution Pack` как основную модель reusable execution logic для pools.
- Переопределить текущую capability `Binding Profiles` как execution-pack catalog:
  - reusable execution-pack revision хранит workflow revision, decision refs, parameters, role mapping и provenance;
  - execution pack НЕ владеет topology shape и НЕ является источником structural slot namespace.
- Зафиксировать, что structural slot namespace принадлежит `Topology Templates`, а execution pack лишь реализует template-defined slot keys.
- Зафиксировать staged migration:
  - operator-facing route и UI терминология переходят на `Execution Packs`;
  - existing internal/storage/runtime identifiers `binding_profile`, `binding_profile_revision`, `binding_profile_revision_id` могут временно оставаться compatibility aliases;
  - attachment/runtime pin остаётся immutable opaque revision identity.
- Обновить binding attachment contract так, чтобы operator-facing semantics описывали attached execution pack, а не “binding profile” как будто он владеет structural topology.

## Impact

- Affected specs:
  - `pool-binding-profiles`
  - `pool-workflow-bindings`
  - `pool-topology-templates`
- Affected code:
  - `orchestrator/apps/intercompany_pools/models.py`
  - `orchestrator/apps/intercompany_pools/workflow_binding_attachments_store.py`
  - `orchestrator/apps/intercompany_pools/binding_preview.py`
  - `frontend/src/pages/Pools/PoolBindingProfilesPage.tsx`
  - `frontend/src/pages/Pools/PoolWorkflowBindingsEditor.tsx`
  - `frontend/src/pages/Pools/PoolRunsRouteCanvas.tsx`
  - `frontend/src/pages/Pools/routes.ts`
  - `frontend/src/App.tsx`
- Related active work:
  - `add-pool-topology-templates` задаёт structural slot ownership и должен быть реализован до или вместе с этим change.
  - `refactor-binding-profile-runtime-simplification` желательно выполнить до этого change, чтобы не тащить в execution-pack reframe лишнюю денормализацию и side-effectful read paths.
- Explicitly out of scope:
  - полное физическое удаление storage-модели `binding_profile*` в этом change;
  - merge reusable execution logic обратно в topology templates;
  - runtime inference slot behavior только по graph shape.
