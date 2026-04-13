## Context

`/pools/factual` уже существует как shipped operator workspace, но по locale/governance contract заметно отстаёт от migrated surfaces:
- route и его shell surface (`frontend/src/uiGovernanceInventory.js`) всё ещё имеют tier `legacy-monitored`;
- `PoolFactualWorkspacePage.tsx` и `PoolFactualWorkspaceDetail.tsx` держат page chrome, alerts, empty/error/status copy и deep-link hints прямо в коде;
- `PoolFactualWorkspaceDetail.tsx` использует route-local helpers вроде `formatTimestamp`, `formatQuarterWindow`, `getRefreshCopy`, `getBacklogCopy`, `buildReviewSummary`;
- `poolFactualReviewQueue.ts` хранит reason/action labels локально;
- в route modules нет canonical translation hooks и shared formatter usage, хотя shell уже умеет `ru/en` locale ownership.

Одновременно active change `update-pool-factual-monitoring-sales-report-parity` расширяет domain semantics factual monitoring. Этот follow-up не должен смешивать domain/runtime parity с locale/governance migration, иначе factual route снова станет "специальным случаем" без чётких acceptance boundaries.

## Goals

- Перевести `/pools/factual` route, detail surface, review modal и route-owned helper modules на canonical frontend i18n runtime.
- Убрать route-local user-facing copy и ad hoc timestamp/quarter/status formatting как primary path.
- Явно вывести factual route из `legacy-monitored` в inventory-backed locale governance coverage.
- Доставить focused browser и unit evidence для locale-consistent factual workflow.

## Non-Goals

- Не менять factual payload semantics, source-profile lineage, worker execution или review queue domain contract.
- Не расширять этот change до остальных `/pools/*` surfaces.
- Не перепроектировать factual workspace layout beyond того, что уже требуется действующим `pool-factual-balance-monitoring` и UI platform governance specs.

## Decisions

### 1. Единица миграции — весь factual route slice, а не только page entry

Считать `/pools/factual` migrated можно только если canonical i18n path используют:
- `PoolFactualWorkspacePage.tsx`;
- `PoolFactualWorkspaceDetail.tsx`;
- `PoolFactualReviewAttributeModal.tsx`;
- route-owned helper modules вроде `poolFactualReviewQueue.ts`;
- route-owned tests/browser evidence.

Нельзя закрыть change переносом только page header или только route title.

### 2. Factual route использует тот же shell-owned i18n runtime, что и pilot wave

Никакой отдельный locale provider для factual workspace не вводится. Route должен использовать существующий shell runtime, dedicated factual namespaces и shared formatter layer для:
- page chrome;
- alerts, empty/error/status copy;
- review reason/action labels;
- user-visible timestamps, quarter windows и numeric summaries;
- code-first API error messaging, где UI уже владеет fallback copy.

Machine-readable payload values и backend vocabulary остаются неизменными; локализуется только operator-facing presentation layer.

### 3. Governance graduation должна быть explicit и inventory-backed

Этот change не считается завершённым, если factual route остаётся `legacy-monitored`. Completion требует:
- перевести `/pools/factual` route entry в inventory-backed locale governance perimeter;
- перевести `PoolFactualReviewAttributeModal.tsx` и другие checked-in factual shell surfaces на тот же coverage path;
- ловить formatter/locale-boundary regressions generic inventory-driven rules, а не one-off factual allowlist.

### 4. Browser proof должен проверять stateful factual UX, а не только статичный перевод

Минимальный acceptance browser set для этого change должен подтвердить:
- shell locale switch + reload на `/pools/factual`;
- locale-consistent route chrome при открытом detail state (`?detail=1`);
- locale-consistent review action flow и modal copy;
- отсутствие mixed-language split между shell navigation, route header и detail/modal surfaces.

### 5. Change остаётся orthogonal к sales-report parity

Если `update-pool-factual-monitoring-sales-report-parity` меняет payload details, factual i18n rollout всё равно должен оставаться валидным, пока route получает machine-readable payload и рендерит его через canonical translation/formatter boundaries.

Следствие: этот change не должен фиксировать узкий payload snapshot как часть i18n contract; он фиксирует presentation/governance contract вокруг него.

## Risks / Trade-offs

- Active changes могут одновременно трогать factual files.
  - Mitigation: держать spec scope узким и отделять locale/governance concerns от domain/source-profile parity.
- Route уже содержит много operator copy, поэтому migration может расползтись в большой string move без acceptance discipline.
  - Mitigation: группировать работу по route slice и привязывать её к concrete browser/unit evidence.
- Factual route может потребовать небольшого governance refactor в inventory и lint/tests.
  - Mitigation: сделать graduation explicit requirement, а не post-factum cleanup.

## Verification Strategy

- Static proof:
  - factual route и shell inventory больше не `legacy-monitored`;
  - route-owned modules не держат raw locale formatting и ad hoc route-local copy registries как primary path;
  - locale-boundary lint rules покрывают factual route через inventory-backed classification.
- Unit/integration proof:
  - route tests подтверждают localized review labels, empty/error states и formatter-backed detail copy;
  - locale coverage tests подтверждают parity route/shell inventory для factual slice.
- Browser proof:
  - locale switch + reload для `/pools/factual`;
  - representative detail/modal scenario без mixed-language split.
