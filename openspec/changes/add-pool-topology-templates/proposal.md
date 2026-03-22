# Change: add-pool-topology-templates

## Why

Текущая модель topology целиком concrete и pool-scoped: `PoolNodeVersion` ссылается на конкретную `Organization`, а `PoolEdgeVersion` хранит конкретные связи внутри одного `pool`. Это хорошо работает как runtime/state model, но плохо подходит для тиражирования повторяющихся схем между разными пулами.

По факту у будущих пулов повторяется не состав организаций, а shape/roles graph и типовые edge behaviors (`realization`, `multi`, `receipt` и т.п.). Ручное пересоздание topology для каждого нового пула создаёт лишнюю стоимость авторинга и drift, а pure clone path делает reuse неявным и плохо управляемым.

Нужен минимальный reusable слой:
- abstract topology template/revision без concrete организаций;
- pool-local instantiation через `slot_key -> organization_id`;
- template-defined edge defaults для `document_policy_key`, но без магического runtime inference только по положению узла в графе.

## What Changes

- Добавить capability `pool-topology-templates` как tenant-scoped reusable catalog topology template/revision.
- Зафиксировать, что template revision описывает abstract slot graph:
  - template nodes идентифицируются стабильными slot/role keys;
  - template edges описывают shape graph и могут задавать default `document_policy_key`;
  - template revision не хранит concrete `organization_id`.
- Добавить pool-local instantiation path, где `pool` pin-ит конкретную `topology_template_revision_id` и задаёт mapping `slot_key -> organization_id`.
- Зафиксировать, что instantiation materialize'ит concrete topology в текущий pool graph/runtime layer и не меняется retroactively при появлении новой template revision.
- Зафиксировать, что `edge.metadata.document_policy_key` остаётся canonical runtime selector, а template edge defaults лишь materialize'ятся в explicit edge metadata.
- Сохранить manual topology authoring как fallback path для нестандартных или разовых схем.

## Impact

- Affected specs:
  - `pool-topology-templates`
  - `organization-pool-catalog`
  - `pool-document-policy`
- Affected code:
  - `orchestrator/apps/intercompany_pools/models.py`
  - `orchestrator/apps/api_v2/views/intercompany_pools.py`
  - `orchestrator/apps/intercompany_pools/document_plan_artifact_contract.py`
  - `orchestrator/apps/intercompany_pools/binding_preview.py`
  - `frontend/src/pages/Pools/PoolCatalogRouteCanvas.tsx`
- Explicitly out of scope:
  - pool clone как canonical reuse path;
  - cross-tenant/global template library;
  - автоматическое вычисление `document_policy_key` только по degree/position узла без explicit template preset или operator override;
  - полная замена текущих concrete runtime tables `PoolNodeVersion` / `PoolEdgeVersion`.
