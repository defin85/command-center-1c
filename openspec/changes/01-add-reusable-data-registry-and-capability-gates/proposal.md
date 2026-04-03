# Change: 01. Вынести reusable-data registry и capability gates в отдельный foundation change

## Why
Текущий `Pool Master Data` жёстко прошит в enum-ы, OpenAPI schema, token parser, bootstrap scope и sync/outbox routing. Из-за этого любое новое `entity_type`, добавленное в backend surface, слишком легко становится runtime-исполняемым только по факту присутствия в enum/API.

Это противоречит fail-closed модели для reusable data и делает безопасное добавление `GLAccount` невозможным без предварительного foundation-шага. Поэтому registry и capability gating нужно выделить в отдельный change и поставить перед всеми account-related поставками.

Этот change фиксирует первую исполнимую фазу перехода к универсальному reusable-data hub.

## What Changes
- Ввести backend-owned executable reusable-data registry как единственный source-of-truth для:
  - canonical entity catalog;
  - capability matrix;
  - token exposure;
  - bootstrap eligibility;
  - sync/outbox eligibility;
  - runtime routing seams.
- Публиковать registry в generated contract/schema для `contracts/**` и frontend вместо handwritten duplicated enum lists.
- Перевести token parsing, bootstrap entity catalogs, dependency ordering, sync enqueue и outbox fan-out на registry-driven capability checks.
- Сделать capability resolution fail-closed по умолчанию:
  - отсутствие capability не считается implicit support;
  - наличие `entity_type` в enum/API namespace не даёт автоматического права на execution path.
- Оставить существующие hardcoded enum/switch seams только как временные compatibility wrappers поверх registry до полного cutover.

## Impact
- Affected specs:
  - `pool-master-data-hub`
  - `pool-master-data-sync`
- Affected code:
  - `orchestrator/apps/intercompany_pools/**`
  - `orchestrator/apps/api_v2/views/intercompany_pools_master_data.py`
  - `frontend/src/pages/Pools/**`
  - `contracts/**`
- Related changes:
  - prerequisite for `02-extend-master-data-hub-with-reusable-accounts`
  - prerequisite for `04-expand-pool-master-data-workspace-for-reusable-accounts`

## Non-Goals
- Добавление `GLAccount` / `GLAccountSet` storage, API и UI.
- Миграция factual scope на `GLAccountSet`.
- Route-level UI shell для `/pools/master-data`.
