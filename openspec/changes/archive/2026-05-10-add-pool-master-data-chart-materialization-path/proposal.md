# Change: Отдельный import/materialization path для canonical chart-of-accounts

## Why
Сейчас `GLAccount` и `GLAccountSet` уже существуют как canonical reusable-account surfaces внутри master-data hub, но у продукта нет отдельного shipped пути, который наполняет полный canonical chart-of-accounts без подмены этого сценария generic `Sync`.

Такой пробел приводит к двум проблемам:
- оператор не получает очевидный source-of-truth path для полного канонического плана счетов;
- factual/publication контуры вынуждены опираться на ручные bootstrap/binding шаги там, где для типового бухучёта нужен отдельный read-only materialization contract.

Отдельный path нужен и потому, что standard 1C OData surface в проекте рассматривается как published read path, а не как generic bidirectional sync contract для reusable accounts. Для полного chart-of-accounts системе нужен authoritative source, snapshot-first import/materialization lifecycle и follower binding backfill/verify, а не mutating sync launcher.

## What Changes
- Добавить отдельный capability `pool-master-data-chart-materialization` для authoritative import/materialization полного canonical chart-of-accounts.
- Ввести authoritative source contract на compatibility class `(tenant, chart_identity, config_name, config_version)` вместо попытки тащить `GLAccount` через generic `Sync`.
- Зафиксировать snapshot-first staged lifecycle: `preflight -> dry-run -> materialize -> verify followers/backfill bindings`.
- Сделать deterministic canonical materialization для `GLAccount`, где source `Ref_Key` остаётся provenance-only и не становится canonical identity.
- Добавить operator-facing `Chart Import` zone в `/pools/master-data`, отдельную от `Sync` и `Bootstrap Import`.
- Зафиксировать, что follower databases получают target-local `GLAccount` bindings через verify/backfill path по `code + chart_identity`, а ambiguity/drift остаются fail-closed diagnostic surface.

## Impact
- Affected specs:
  - `pool-master-data-chart-materialization` (new)
  - `pool-master-data-hub-ui`
- Affected code:
  - `orchestrator/apps/intercompany_pools/master_data_bootstrap_import_*`
  - `orchestrator/apps/intercompany_pools/master_data_canonical_upsert.py`
  - `orchestrator/apps/intercompany_pools/master_data_registry.py`
  - `orchestrator/apps/api_v2/views/intercompany_pools_master_data.py`
  - `frontend/src/pages/Pools/masterData/**`
  - `contracts/**`

## Non-Goals
- Не переводить `GLAccount` или `GLAccountSet` в generic mutating sync entity types.
- Не делать multi-source merge нескольких ИБ в один silent canonical chart.
- Не требовать native OData delta/change-tracking от standard 1C surface как обязательный MVP-механизм.
- Не менять current factual runtime contract напрямую в этом change; он только получает более надёжный upstream canonical chart materialization path.
