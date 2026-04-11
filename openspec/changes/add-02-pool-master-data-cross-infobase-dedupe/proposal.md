# Change: Добавить cross-infobase semantic dedupe как source-of-truth слой pool master-data

## Why
Текущий canonical hub уже умеет хранить reusable master-data, per-infobase bindings, staged bootstrap import и sync/runtime gate. Но после перехода к сбору reference layer по нескольким ИБ система всё ещё не фиксирует отдельный контракт, который говорит, как именно одинаковые бизнес-сущности из разных баз превращаются в один canonical source-of-truth.

Сейчас этот слой фактически остаётся недоопределённым:
- `Ref_Key` и binding rows намеренно target-local и не являются cross-infobase identity;
- existing bootstrap/import/sync контракты специально не обещают "умный глобальный merge";
- оператору негде увидеть, почему две записи из разных ИБ были автоматически сведены в одну canonical сущность или почему merge был заблокирован.

Для сценария "собрать reference по всем ИБ -> получить один канонический слой -> раскатать его обратно по этим ИБ" этого недостаточно. Нужен отдельный, явный source-of-truth contract для automatic semantic dedupe:
- с детерминированными entity-specific rules;
- с provenance по каждому источнику;
- с fail-closed review queue для неоднозначных случаев;
- с блокировкой rollout/publication, пока canonical слой не разрешён.

## What Changes
- Ввести отдельную capability `cross-infobase semantic dedupe` для pool master-data как слой между collection/inbound ingress и canonical source-of-truth.
- Добавить persisted source provenance для записей, пришедших из разных ИБ:
  - `source_database_id`;
  - source object key (`ib_ref_key` или эквивалентный source ref);
  - `origin_kind` и link на batch/job/launch;
  - normalized match signals;
  - resolution status/reason.
- Зафиксировать registry-driven dedupe policy per entity type:
  - auto-dedupe eligibility;
  - identity signals и normalization rules;
  - deterministic survivor precedence;
  - review-required conditions;
  - rollout eligibility.
- Автоматически резолвить только safe matches; ambiguous cases переводить в operator review queue с machine-readable diagnostics.
- Переиспользовать существующий canonical entity при попадании новых source records в уже resolved cluster; не создавать duplicate canonical rows из-за порядка поступления данных.
- Блокировать outbound rollout/manual sync launch/publication для unresolved dedupe clusters.
- Добавить в `/pools/master-data` отдельную operator surface `Dedupe Review` с history, provenance detail и explicit resolution actions.

## Impact
- Affected specs:
  - `pool-master-data-hub`
  - `pool-master-data-hub-ui`
  - `pool-master-data-sync`
- Affected code:
  - `orchestrator/apps/intercompany_pools/models.py`
  - `orchestrator/apps/intercompany_pools/master_data_*`
  - `orchestrator/apps/api_v2/views/intercompany_pools_master_data*.py`
  - `frontend/src/pages/Pools/masterData/**`
  - `frontend/src/api/intercompanyPools.ts`
  - `contracts/**`
- Related changes:
  - complements `add-01-pool-master-data-bootstrap-collection-launches`, which brings multi-database collection orchestration;
  - complements `add-03-pool-master-data-manual-sync-launches`, which brings cluster/database-scoped rollout orchestration.

## Non-Goals
- ML/fuzzy matching без explicit policy и audit-friendly explanation.
- Silent field blending между конфликтующими источниками.
- Подмена per-infobase binding contract или трактовка `Ref_Key` как cross-infobase identity.
- Auto-dedupe для entity types без explicit registry capability; `GLAccountSet` остаётся вне automatic dedupe `V1`.
- Универсальный tenant-global merge engine за пределами pool master-data domain.

## Assumptions
- Dedupe scope остаётся tenant-local.
- Collection/inbound ingress уже умеет принести достаточное source provenance для сохранения candidate evidence.
- Canonical source-of-truth остаётся operator-governed; automatic merge разрешён только там, где entity-specific rules считают его безопасным.
- Outbound rollout/publication используют только dedupe-resolved canonical state.
