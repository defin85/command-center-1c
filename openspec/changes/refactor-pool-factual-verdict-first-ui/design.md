## Context

`/pools/factual` уже является canonical operator-facing workspace для factual balances, settlement handoff и manual review, но текущая композиция больше похожа на diagnostics dashboard, чем на status workspace:
- пользователь сначала видит explanatory copy и набор равноправных cards;
- aggregate денежные показатели присутствуют, но визуально не доминируют;
- причина плохого состояния выясняется только после чтения нескольких блоков;
- master pane не даёт быстрого ответа, какой pool проблемный.

Для operator-facing factual route это создаёт неправильный cognitive order: сначала пользователь должен понять общий verdict и движение денег по пулу, а уже потом читать scope lineage, checkpoint ids и runtime-specific diagnostics.

## Goals

- Дать пользователю ответ "всё хорошо / нужно внимание / критическая проблема" за первый взгляд на selected pool.
- Сделать aggregate `вошло / вышло / остаток` главным business signal above the fold.
- Сохранить всю текущую diagnostic depth, но опустить её ниже primary summary.
- Улучшить scanability master pane для выбора проблемного pool.

## Non-Goals

- Не менять factual domain semantics.
- Не делать broad redesign existing `PoolFactualWorkspace` payload или generic `/api/v2/pools/` contract.
- Не заменять текущий `MasterDetailShell` другим page pattern.
- Не объединять этот change с factual i18n rollout или sales-report parity rollout.

## Decisions

### 1. Workspace становится verdict-first, а не diagnostics-first

Selected pool detail ДОЛЖЕН начинаться с двух primary blocks:
- `Overall state`
- `Pool movement summary`

Только после них идут smaller operational cards, tables и diagnostics.

Следствие: explanatory copy про relation к `/pools/runs`, `scope lineage` и per-checkpoint diagnostics больше не должны быть первыми блоками detail pane.

### 2. Selected-pool movement summary использует existing workspace summary fields

Selected detail не вводит новый workspace contract. Primary movement summary строится из уже существующих:
- `incoming_amount`
- `outgoing_amount`
- `open_balance`

Если `incoming_amount > 0`, UI дополнительно показывает derived completion ratio (`outgoing / incoming`).
Если `incoming_amount = 0`, UI явно сообщает, что за выбранный период нет заведённого объёма, а не строит бессмысленный процент.

### 3. Master pane использует dedicated factual overview contract, а не generic pool catalog contract

Compact per-pool health summary не должен собираться через sequential `getPoolFactualWorkspace` calls после открытия route и не должен расширять generic `OrganizationPool` / `/api/v2/pools/`, потому что этот contract уже используется за пределами factual workspace.

Вместо этого change вводит отдельный lightweight factual overview read model для selection pane со следующими свойствами:
- row-level overview использует те же verdict inputs, что и selected detail, чтобы не появилось второй несовместимой health model;
- explicit `quarter_start` route context, если он задан, ДОЛЖЕН использоваться одинаково для overview и selected detail;
- если explicit `quarter_start` не задан, overview ДОЛЖЕН либо возвращать resolved quarter label per pool, либо иным способом явно не скрывать quarter context, в котором рассчитан summary;
- overview contract остаётся bounded для `/pools/factual` и не меняет семантику общих pool catalog surfaces.

Практическое следствие: backend change здесь допустим, но он должен быть узким read-model addition, а не broad payload redesign.

### 4. Overall verdict вычисляется через приоритетную health model

Workspace verdict использует один deterministic priority order:
- `critical`
  - `workspaceError`
  - `source_availability != available`
  - `sync_status == failed`
  - `checkpoints_failed > 0`
- `warning`
  - `freshness_state == stale`
  - `backlog_total > 0`
  - `attention_required_total > 0`
  - `pending_review_total > 0`
- `healthy`
  - нет условий выше и есть валидный sync context
- `unknown`
  - pool не выбран или данные ещё не загружены

Verdict не должен пытаться выразить все детали сразу. Он обязан дать:
- один status label;
- одну главную причину;
- одно рекомендуемое следующее действие.

### 5. Master pane получает compact per-pool health summary

Список пулов должен помогать выбрать проблемный pool без открытия каждого detail. Для этого каждая строка показывает compact summary:
- статус (`critical` / `warning` / `healthy` / `unknown`);
- короткую причину или counter (`3 sync failures`, `2 review items`, `healthy`).

Это остаётся compact selection surface и не превращается в table/grid.

### 6. Diagnostics остаются доступными, но становятся secondary disclosure

`Pinned scope lineage`, `Sync diagnostics`, raw codes и workflow/operation handoff links остаются в route, потому что они нужны для расследования.

Но они:
- не должны precede primary verdict;
- не должны visually compete с movement summary;
- должны читаться как `почему так получилось`, а не как `первый ответ`.

## Risks / Trade-offs

- Один агрегированный verdict неизбежно скрывает часть нюансов.
  - Mitigation: всегда показывать primary cause и сохранять detailed diagnostics ниже.
- При нулевых суммах пользователь может принять `0 / 0 / 0` за healthy state, хотя sync может быть broken.
  - Mitigation: verdict живёт отдельно от financial rollup и имеет больший приоритет.
- Master pane summary теперь требует отдельного bounded data source.
  - Mitigation: не переиспользовать generic `/api/v2/pools/`; держать dedicated overview contract маленьким и построенным на тех же verdict inputs, что и detail.
- Без explicit quarter alignment selection pane может сравнивать pools в разных quarter contexts.
  - Mitigation: при наличии `quarter_start` route param overview и detail используют одинаковый quarter context; при отсутствии explicit quarter row summary показывает resolved quarter label.
- Параллельный i18n rollout может менять wording.
  - Mitigation: этот change фиксирует hierarchy и disclosure model, а не конкретную final phrasing.

## Verification Strategy

- Contract proof:
  - factual overview contract возвращает row-level selection summary без изменения generic `/api/v2/pools/` semantics;
  - explicit `quarter_start` route context одинаково отражается в selection summary и selected detail verdict.
- Static/UI proof:
  - detail pane рендерит `Overall state` и `Pool movement summary` above the fold;
  - aggregate incoming/outgoing/open balance больше не скрыты только внутри prose copy;
  - diagnostics sections смещены ниже primary summary.
- Unit proof:
  - tests подтверждают conflicting-state resolution через deterministic verdict priority;
  - tests подтверждают prominent aggregate movement summary и zero-incoming behavior.
- Browser proof:
  - оператор открывает `/pools/factual`, выбирает pool и видит общий verdict и aggregate movement до чтения technical diagnostics;
  - scanability списка пулов позволяет быстро выбрать route item, требующий внимания.
