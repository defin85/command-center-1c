## Context
`Chart Import` сейчас ожидает `chart_identity` в двух местах:
- оператор вводит identity при создании chart source;
- bootstrap source rows уже содержат тот же `chart_identity`.

Это работает для тестового или заранее подготовленного metadata-mode сценария, но плохо подходит для onboarding: оператору нужно не угадывать `ChartOfAccounts_Хозрасчетный`, а выбрать эталонную ИБ и увидеть, какие планы счетов доступны.

## Goals / Non-Goals

### Goals
- Сделать `chart_identity` discoverable из выбранной ИБ.
- Дать оператору guided first-load path из эталонной ИБ.
- Оставить authoritative source и snapshot-first materialization единственным source-of-truth path.
- Сделать provenance discovery явным, чтобы было понятно, откуда взялся identity.

### Non-Goals
- Не заменять текущий chart materialization lifecycle.
- Не запускать generic `pool-master-data-sync` для планов счетов.
- Не считать free-text `chart_identity` штатным основным UX.

## Decisions

### Decision: discovery возвращает typed chart candidates
Backend вводит read-only discovery API для выбранной database.

Candidate должен содержать как минимум:
- `chart_identity`;
- operator-facing `name`;
- `config_name`;
- `config_version`;
- `source_database_id`;
- `source_kind`;
- `derivation_method`;
- `confidence`;
- `metadata_hash`/`catalog_version` или equivalent source evidence fingerprint;
- diagnostic/warning fields.

`chart_identity` может быть получен из:
- configured OData entity name вида `ChartOfAccounts_*`;
- metadata catalog field/type information;
- explicit bootstrap source mapping metadata;
- metadata rows, если они уже содержат `chart_identity`.

Если discovery не может доказательно получить stable identity, candidate должен быть marked incomplete, а штатная первичная загрузка должна блокироваться до ручного advanced override.

Discovery должен использовать существующий `metadata_catalog`/bootstrap source configuration как primary evidence. Full chart row fetch не должен быть обязательным discovery mechanism; row inspection допустим только как bounded/sample или metadata-rows path, а полный snapshot остаётся стадией dry-run/materialize.

### Decision: initial load composes existing lifecycle
Initial load не является новым runtime mode. Это orchestration поверх существующих стадий:
1. select reference database;
2. discover chart candidates;
3. choose chart candidate;
4. create/update authoritative chart source;
5. run preflight;
6. run dry-run;
7. require operator review;
8. run materialize.

Для API это может быть реализовано как отдельный guided endpoint или как UI orchestration над существующими source/job endpoint-ами. В обоих вариантах backend должен сохранять отдельные job records и audit trail для стадий lifecycle.

Materialize в guided initial load должен ссылаться на current source revision/evidence и successful dry-run review. Если authoritative source или discovery evidence изменились после dry-run, materialize должен требовать новый preflight/dry-run вместо переиспользования stale result.

### Decision: reference database selection is explicit
Эталонная ИБ выбирается оператором явно. Система не должна silently выбирать первую совместимую database.

Одна compatibility class остаётся привязанной к одной authoritative source database. Если оператор меняет эталонную ИБ для того же `(tenant, chart_identity, config_name, config_version)`, система должна показать impact: предыдущий source, latest snapshot, affected follower verification state и необходимость нового dry-run/materialize.

Discovery и source setup должны использовать тот же tenant access boundary, что и existing Chart Import mutation/read APIs. Endpoint не должен раскрывать metadata или chart candidates из database вне текущего tenant context.

### Decision: manual override remains advanced and auditable
Ручной ввод `chart_identity` допустим только как advanced fallback:
- с явной причиной override;
- с сохранением provenance в source metadata;
- с fail-closed validation against source rows during preflight/dry-run.

Штатный UI не должен подталкивать оператора к free-text вводу там, где discovery работает.

## Risks / Trade-offs
- OData metadata может не содержать удобного display name.
  - Mitigation: candidate показывает raw identity и derivation method, display name может быть best-effort.
- В некоторых ИБ source mapping может быть неполным.
  - Mitigation: discovery returns incomplete candidate diagnostics instead of silently fabricating identity.
- Guided initial load может стать долгим для больших charts.
  - Mitigation: initial load remains staged; materialize starts only after dry-run review.

## Migration Plan
1. Add chart discovery service and API contract.
2. Extend bootstrap source mapping/read path so `chart_identity` can be derived from chart entity configuration when appropriate, including row stamping from source config when the source entity itself is `ChartOfAccounts_*`.
3. Add initial-load orchestration/guidance in backend or UI while preserving existing job records.
4. Add source-revision/evidence checks so stale discovery or stale dry-run cannot authorize materialize.
5. Replace primary free-text source setup UI with reference DB + discovered chart selection.
6. Keep advanced manual override behind explicit affordance and audit metadata.
