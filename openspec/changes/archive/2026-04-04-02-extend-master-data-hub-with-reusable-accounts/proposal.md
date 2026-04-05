# Change: 02. Расширить master-data hub первой reusable account family

## Why
После вынесения registry/gating foundation reusable-data hub можно безопасно расширять новой entity family. Следующий шаг нужен для первой reusable account family: сегодня бухгалтерские счета частично присутствуют в published documents и factual path, но не имеют устойчивого canonical storage, compatibility contract и binding scope в CC.

Этот change расширяет универсальный reusable-data hub первой reusable account family и сознательно не включает factual cutover.

## What Changes
- Добавить `GLAccount` как tenant-scoped canonical reusable entity для бухгалтерских счетов.
- Добавить `GLAccountSet` как reusable profile с profile/draft/published revision surfaces и immutable revision contract.
- Сделать `chart_identity` и account compatibility markers first-class persisted surfaces.
- Явно отделить canonical identity `GLAccount` от per-infobase `ib_ref_key` / `Ref_Key`.
- Добавить API/contracts для `/api/v2/pools/master-data/gl-accounts/` и `/api/v2/pools/master-data/gl-account-sets/`.
- Поддержать bootstrap import для `GLAccount` через existing master-data lifecycle.
- Добавить token `master_data.gl_account.<canonical_id>.ref` с metadata-aware validation.
- Разрешить publication compile/runtime использовать resolved account refs из binding artifact после typed metadata validation.
- Зафиксировать, что `GLAccount` и `GLAccountSet` не получают automatic outbound/bidirectional mutation semantics в этом change.

## Impact
- Affected specs:
  - `pool-master-data-hub`
  - `pool-master-data-sync`
  - `pool-document-policy`
  - `pool-odata-publication`
- Affected code:
  - `orchestrator/apps/intercompany_pools/**`
  - `orchestrator/apps/api_v2/views/intercompany_pools_master_data.py`
  - `contracts/**`
  - `frontend/src/pages/Pools/**`
- Related changes:
  - depends on `01-add-reusable-data-registry-and-capability-gates`
  - prerequisite for `03-bridge-pool-factual-scope-to-gl-account-set`
  - prerequisite for `05-expand-pool-master-data-workspace-for-reusable-accounts`

## Non-Goals
- Cutover factual scope на `GLAccountSet`.
- Изменение top-level factual worker envelopes.
- Route-level UI shell migration для `/pools/master-data`.
- Automatic outbound sync или bidirectional mutation для plan-of-accounts objects.
