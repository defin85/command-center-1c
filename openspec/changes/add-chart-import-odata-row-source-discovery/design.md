## Context
Текущий `Discover Chart` решает только половину onboarding-задачи: он может вывести `chart_identity` из `ChartOfAccounts_*`, source mapping metadata, metadata rows или metadata catalog field types.

Metadata catalog snapshot не содержит строки плана счетов. Он полезен как evidence для identity, но не может быть runtime row source для полного initial load. Сейчас полный список счетов появляется только если для database уже есть `bootstrap_import_source.entities.gl_account` mapping или `metadata.bootstrap_import_rows.gl_account`.

## Goals / Non-Goals

### Goals
- Сделать readiness initial load явной частью discovery candidate.
- Автоматически создавать chart-scoped row source mapping для standard OData entity `ChartOfAccounts_*`.
- Сохранять row source evidence рядом с authoritative chart source, чтобы stale checks учитывали не только `chart_identity`, но и mapping/probe.
- Не смешивать Chart Import runtime с generic `Sync` или legacy `Bootstrap Import` jobs.

### Non-Goals
- Не строить универсальный mapping wizard для всех master-data entities.
- Не гарантировать поддержку кастомных 1C публикаций без явного operator mapping.
- Не выполнять full chart row scan до `dry-run`.

## Decisions

### Decision: candidate has identity readiness and row-source readiness
Discovery response должен различать:
- identity candidate: система знает `chart_identity`;
- load-ready candidate: система знает, как прочитать строки выбранного chart через OData/source adapter.

Candidate с `chart_identity`, найденным только из metadata field type, может быть валидным для выбора identity, но НЕ ДОЛЖЕН считаться готовым для primary initial load, пока row source не подтверждён.

### Decision: discovery is read-only and row source is chart-scoped provenance
Discovery может возвращать row-source proposal и выполнять bounded read-only probe, но не создаёт authoritative chart source и не меняет `Database.metadata`.

Выбранный row source сохраняется в metadata authoritative chart source только на source upsert / prepare initial load, а не silently перезаписывает global `Database.metadata.bootstrap_import_source` для всех bootstrap workflows.

Допустимо переиспользовать существующий bootstrap source adapter для нормализации OData rows, но execution остаётся внутри Chart Import materialization:
- `preflight`;
- `dry-run`;
- operator review;
- `materialize`.

Если уже существует global `Database.metadata.bootstrap_import_source.entities.gl_account`, Chart Import может переиспользовать его только после explicit compatibility check with selected candidate и должен snapshot-нуть фактически выбранный mapping в chart source metadata. Runtime не должен silently fallback-ить на изменившийся global mapping после dry-run.

### Decision: standard ChartOfAccounts mapping is deterministic
Для OData entity `ChartOfAccounts_<identity>` система может сформировать deterministic default mapping:
- `source_ref` и/или `canonical_id` из `Ref_Key`;
- `code` из `Code`;
- `name` из `Description`;
- `chart_identity` из entity name, а не из отдельной row column.

Если published OData surface использует другие поля, candidate должен быть marked `row_source_status=needs_mapping` и требовать explicit operator mapping/review.

### Decision: probe is bounded, materialization fetch is staged
Discovery/preflight могут выполнять bounded OData probe (`top=1`, required field select, health/auth check), но не читают полный chart. Полная постраничная загрузка остаётся только на `dry-run/materialize`, где уже есть audit trail и review gate.

Probe, discovery response, diagnostics и persisted provenance не должны содержать OData passwords, authorization headers, raw Basic auth material или raw chart row payload. Допустимы только non-secret identifiers, selected mapping, credential strategy label, counts/status и fingerprints.

Full row fetch должен использовать bounded page size и deterministic output fingerprint. Если pagination опирается на `$skip/$top`, implementation should prefer stable ordering by `Ref_Key`/`Code` when the source supports it; otherwise diagnostics must make the snapshot consistency assumption visible to the operator.

### Decision: row source evidence participates in stale checks
Source revision token должен включать row source mapping/probe evidence. Если после `dry-run` меняется entity name, field mapping, selected database, credentials strategy, metadata hash/catalog version или probe fingerprint, `materialize` должен требовать новый `preflight/dry-run`.

## Risks / Trade-offs
- В части ИБ `Description` может быть неполным display field.
  - Mitigation: default mapping можно заменить explicit operator mapping before initial load.
- OData metadata snapshot может не содержать published `ChartOfAccounts_*` entity, хотя live OData его отдаёт.
  - Mitigation: allow bounded live probe when credentials are configured; otherwise show remediation.
- Persisting chart-scoped mapping creates a second source config surface.
  - Mitigation: keep it under chart source metadata and show it in Chart Import UI; do not mutate global Bootstrap Import mapping implicitly.

## Migration Plan
1. Extend discovery contract with row-source readiness and row-source evidence.
2. Add OData row-source resolver/probe for `ChartOfAccounts_*`.
3. Persist selected row source in chart source metadata and source revision.
4. Make chart preflight/dry-run use chart-scoped row source before falling back to existing database metadata mapping.
5. Update UI to show identity-only vs load-ready candidates and block initial load until row source is ready.
6. Add backend/frontend/contract tests for load-ready, identity-only, custom mapping required, and stale row-source evidence.

## Open Questions
- Нужен ли отдельный API action для operator-reviewed custom field mapping, или достаточно расширить source upsert payload?
- Должен ли UI предлагать explicit "publish/use global Bootstrap Import mapping" action, если operator хочет переиспользовать row source outside Chart Import?
- Требуем ли для больших charts server-driven continuation/nextLink support, или для MVP достаточно bounded `$top/$skip` с stable ordering и итоговым fingerprint?
