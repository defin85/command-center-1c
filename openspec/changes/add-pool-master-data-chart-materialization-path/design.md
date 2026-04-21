## Context
`GLAccount` и `GLAccountSet` уже существуют как canonical reusable-account surfaces в master-data hub, но текущая shipped модель оставляет два зазора:

1. для полного плана счетов нет отдельного operator-facing import/materialization path;
2. пользователь легко путает этот сценарий с generic `Sync`, хотя `GLAccount` и `GLAccountSet` intentionally не входят в sync-capable entity family.

Внешние integration constraints усиливают это решение:
- проект использует standard 1C published OData surface как read path;
- standard 1C OData в практическом контракте проекта опирается на OData v3-style interface и не даёт надёжную MVP-опору на standard delta/change-tracking semantics;
- follower databases всё равно требуют target-local binding materialization, потому что `Ref_Key` остаётся per-infobase object reference.

Из этого следует, что продукту нужен отдельный authoritative import/materialization path, а не расширение generic `Sync`.

## Goals / Non-Goals

### Goals
- Дать продукту отдельный source-of-truth path для полного canonical chart-of-accounts.
- Отделить read-only chart materialization от generic mutating sync semantics.
- Переиспользовать текущий bootstrap/import foundation вместо параллельного ad hoc runtime.
- Добавить deterministic follower binding verify/backfill path для `GLAccount`.
- Сохранить fail-closed diagnostics при ambiguity/drift.

### Non-Goals
- Не включать `GLAccount` / `GLAccountSet` в generic `Sync` launcher.
- Не строить новый top-level service или новый primary runtime.
- Не делать silent merge нескольких incompatible chart sources.
- Не делать native incremental delta-tracking обязательным условием MVP.

## Options

### Option A: Расширить generic `Sync` на `GLAccount`
Идея: добавить `GLAccount` в sync-capable entity family и использовать существующий sync launcher/runtime.

Почему не выбираем:
- смешивает canonical chart materialization и mutating per-infobase sync semantics;
- противоречит уже shipped registry model для reusable accounts;
- создаёт ложное ожидание bidirectional sync там, где нужен authoritative read-only source.

### Option B: Snapshot-first materialization из одной authoritative source DB на compatibility class
Идея: для `(tenant, chart_identity, config_name, config_version)` выбирать одну authoritative source DB, читать её published chart snapshot, materialize canonical `GLAccount`, затем verify/backfill follower bindings.

Плюсы:
- совместимо с current registry and bootstrap foundation;
- source-of-truth остаётся явным;
- downstream factual/publication получают стабильную canonical chart surface;
- нет зависимости от vendor-specific delta support.

Минусы:
- полный snapshot может быть заметно тяжелее incremental feed;
- нужен отдельный operator surface и provenance model.

Это рекомендуемый вариант.

### Option C: Federated merge нескольких source DB
Идея: брать несколько ИБ одного chart и собирать canonical chart через merge.

Почему не выбираем:
- скрывает drift вместо явного verdict;
- делает canonical lineage спорным;
- повышает риск silent overwrite для account names/compatibility markers.

### Option D: Сразу строить custom delta service поверх 1C
Идея: требовать отдельный published HTTP service/Data History-like incremental feed для chart changes.

Почему не выбираем как MVP:
- operational complexity выше;
- потребует отдельного delivery surface на стороне 1C;
- без snapshot-first фазы слишком рано усложняет rollout.

## Decisions

### Decision: authoritative source задаётся на compatibility class
Система вводит first-class source contract на `(tenant, chart_identity, config_name, config_version)`.

Для каждой compatibility class продукт выбирает одну authoritative source DB, из которой materialize-ится canonical chart snapshot. Остальные databases считаются follower targets для verify/backfill, а не равноправными source-ами.

### Decision: materialization остаётся read-only и staged
Canonical chart path использует staged lifecycle:
1. `preflight`
2. `dry-run`
3. `materialize`
4. `verify followers/backfill bindings`

`Chart Import` и `Sync` остаются разными operator surfaces и разными контрактами.

### Decision: canonical identity выводится детерминированно из normalized chart scope
Canonical `GLAccount` identity не опирается на source `Ref_Key`.

Стабильный canonical key должен определяться детерминированно как минимум из:
- normalized `chart_identity`;
- normalized account `code`.

Source `Ref_Key` и source database provenance сохраняются только как provenance/debug surface.

### Decision: snapshot-first before incremental
MVP строится на full snapshot materialization через existing bootstrap/import foundation.

Если later profile покажет, что snapshot path слишком тяжелый, продукт сможет добавить optional incremental mode через separate published custom surface. Но canonical contract не должен зависеть от этой future optimization.

### Decision: follower binding verify/backfill идёт после canonical materialization
После materialization canonical chart система отдельно:
- проверяет follower databases на code/chart coverage;
- materialize-ит или обновляет target-local `GLAccount` bindings по `code + chart_identity`;
- оставляет ambiguity/stale state как fail-closed diagnostics с ручной remediation.

Это сохраняет separation между общей canonical chart model и target-local `Ref_Key` layer.

### Decision: retirement должен быть soft и provenance-preserving
Если очередной authoritative snapshot больше не содержит ранее materialized account, система не делает hard delete по умолчанию.

Вместо этого account получает soft-retired/provenance state, чтобы:
- не ломать historical `GLAccountSet` revisions;
- не уничтожать factual/publication lineage;
- позволять operator review перед purge.

### Decision: operator surface называется `Chart Import`
В `/pools/master-data` появляется отдельная зона `Chart Import`.

Она отвечает за:
- source selection / inspect;
- preflight и dry-run;
- materialize;
- follower verify/backfill;
- drift and ambiguity diagnostics.

Это имя прямо подчёркивает, что речь идёт о canonical chart materialization, а не о generic sync launcher.

## Data Model Sketch
- `PoolMasterDataChartSource`
  - compatibility class
  - authoritative `database_id`
  - status / last_success_at / last_error_code
- `PoolMasterDataChartSnapshot`
  - source reference
  - snapshot hash
  - row counts / timing
  - created_at
- `PoolMasterDataChartMaterializationJob`
  - mode: `dry_run | materialize | verify_followers | backfill_bindings`
  - status / counters / last_error_code
- `PoolMasterDataChartFollowerStatus`
  - follower database
  - coverage verdict
  - ambiguity/stale diagnostics
  - last_verified_at

## Migration Plan
1. Add authoritative source + job models and API contracts.
2. Reuse bootstrap import adapter for `GLAccount` full-snapshot source reads.
3. Implement deterministic canonical materialization and soft-retire semantics.
4. Add follower verify/backfill path for `GLAccount` bindings.
5. Ship `Chart Import` workspace zone and deep-linkable diagnostics.
6. Keep `Sync` unchanged for reusable accounts.

## Risks / Trade-offs
- Full snapshot import может быть дорогим на больших charts.
  - Mitigation: staged dry-run, bounded paging, future optional incremental mode.
- Единственная authoritative source DB создаёт governance burden.
  - Mitigation: explicit source selection, drift verification against followers.
- Auto-backfill bindings по `code + chart_identity` может давать ambiguity на нестандартных ИБ.
  - Mitigation: fail-closed ambiguity diagnostics and manual remediation path.
- Soft-retire усложняет lifecycle canonical chart.
  - Mitigation: это лучше, чем ломать historical revisions и downstream lineage hard delete-ом.
