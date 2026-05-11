## Context
Текущий observability contour в этом репозитории intentionally replay-free:
- `ui-action-observability` даёт bounded semantic journal;
- `agent-ui-observability-access` даёт dev export path и prod/dev read-only query path;
- `add-ui-incident-telemetry-pipeline` уже создал durable telemetry substrate для recent incidents/timelines;
- `add-gateway-request-budget-isolation` уже добавил machine-readable `429` diagnostics (`request_id`, `ui_action_id`, `rate_limit_class`, `retry_after_seconds`, `budget_scope`).

Проблема не в отсутствии telemetry как таковой, а в потере semantic ownership при route churn. В инциденте `/pools/master-data` contour показал oscillation между `tab=bindings` и `tab=sync`, но не смог доказательно ответить:
- какой operator action был последним route-changing intent;
- какой route writer потом переписал URL;
- когда oscillation стала уже loop, а не просто несколькими переходами.

При этом переход к raw clickstream/DOM replay противоречит уже принятому contract. Значит, решение должно оставаться semantic, bounded и redaction-first.

## Goals / Non-Goals

### Goals
- Сделать route-owned UI loops diagnosable без session replay.
- Отделить explicit operator route intent от вторичных route writes/effects.
- Добавить machine-readable attribution для `setSearchParams(...)` / `navigate(...)` writers.
- Добавить bounded loop signal, чтобы агент не восстанавливал oscillation вручную по длинному timeline.
- Доставить первую подтверждённую surface на `Pool Master Data`, где проблема уже воспроизведена.

### Non-Goals
- Не строить raw click recorder или DOM-level action log.
- Не превращать observability в аналитический clickstream.
- Не расширять pilot сразу на все route-changing surfaces продукта.
- Не делать auto-remediation route loop root cause в рамках этого change.

## Options

### Option A: Логировать все DOM clicks / button texts
Почему не выбираем:
- ломает privacy/noise budget;
- противоречит shipped redaction-first contract;
- не гарантирует устойчивую диагностику, потому что DOM/text labels нестабильны и зависят от UI copy.

### Option B: Semantic route intent + route writer attribution + loop warning
Идея:
- explicit route-changing controls пишут semantic action с устойчивыми identifiers;
- route writers пишут attribution metadata;
- journal выводит derived `route.loop_warning` после bounded threshold.

Плюсы:
- сохраняет replay-free модель;
- даёт answerable question "что нажали" без DOM replay;
- позволяет отличить user intent от self-generated route churn;
- расширяет уже существующий `ui_action_id` lineage, а не вводит второй параллельный contract.

Это рекомендуемый вариант.

### Option C: Оставить только synthetic request boundaries и делать inference offline
Почему не выбираем:
- synthetic request boundary отвечает на вопрос "какой запрос стал slow/failure", но не на вопрос "какой control изменил route";
- ambiguity между operator action и route effect остаётся.

### Option D: Добавить только route transition counters без writer attribution
Почему не выбираем:
- loop будет виден, но root ownership останется неясной;
- придётся заново делать code archaeology по нескольким route writers.

## Decisions

### Decision: Route-changing operator intent должен логироваться как explicit semantic action
Для instrumented route-changing controls система пишет explicit semantic action с устойчивыми полями:
- `surface_id`;
- `control_id`;
- `intent_kind=route.change`;
- bounded route context до/после (`from_*`, `to_*` или equivalent compact form).

Source-of-truth здесь остаётся semantic intent, а не DOM details. Пользовательский label control может меняться, а `surface_id` / `control_id` должны оставаться grep-friendly и стабильными.

### Decision: Route writers получают отдельный attribution layer
Когда route-owned shell или child surface делает `setSearchParams(...)` / `navigate(...)`, observability layer фиксирует:
- `route_writer_owner`;
- `write_reason`;
- `navigation_mode` (`push|replace`);
- bounded `param_diff`;
- `caused_by_ui_action_id`, если write произошёл в causal chain от operator intent.

Это даёт причинную связку:
`operator intent -> route write -> route transition -> request/error`.

### Decision: Loop сигнал должен быть derived и bounded
Loop не должен эмититься на каждый transition. Вместо этого observability layer держит short rolling window и выпускает `route.loop_warning`, когда:
- route states oscillate above threshold;
- oscillation касается bounded key set (`tab`, `detail`, `launchId` и т.п.);
- signal можно объяснить как отдельный инцидентный факт, а не как шумной stream.

`route.loop_warning` должен содержать как минимум:
- `surface_id` / `route_path`;
- oscillating keys / states;
- observed writer owners;
- transition count/window;
- last or causing `ui_action_id`, если он есть.

### Decision: First mandatory surface — `Pool Master Data`
Этот change intentionally bounded:
- route-owned shell: `PoolMasterDataPage`;
- child writers: `SyncStatusTab`, `DedupeReviewTab`;
- explicit operator path: zone switch `Bindings` / `Sync`.

Другие route-owning surfaces можно подключать позже отдельными задачами/changes после доказанной полезности pilot.

### Decision: Durable telemetry/query substrate переиспользуется, а не дублируется
Если новые поля/events нужны в prod/dev read-only query path, change расширяет уже shipped telemetry/query substrate:
- existing ingest/query models;
- existing timeline/incidents endpoints;
- existing debug wrappers.

Этот change не создаёт новый observability backend и не дублирует `add-ui-incident-telemetry-pipeline`.

### Decision: Route intent must stay redaction-first
Новый contract не должен утянуть в telemetry:
- innerText кнопок;
- raw query fragments, не входящие в allowlist;
- произвольные form values;
- нестабильные DOM selectors.

Допустимы только whitelisted semantic fields: stable IDs, bounded route diffs и machine-readable reason codes.

## Data Shape Sketch

### Explicit route intent action
- `event_type = ui.action`
- `action_kind = route.change`
- `surface_id`
- `control_id`
- `action_source = explicit`
- `context.from`
- `context.to`

### Attributed route transition
- `event_type = route.transition`
- `route_writer_owner`
- `write_reason`
- `navigation_mode`
- `param_diff`
- `caused_by_ui_action_id`

### Loop warning
- `event_type = route.loop_warning`
- `surface_id`
- `route_path`
- `oscillating_keys`
- `observed_states`
- `writer_owners`
- `transition_count`
- `window_ms`
- `ui_action_id` (optional)

## Migration Plan
1. Обновить OpenSpec contracts для `ui-action-observability` и `agent-ui-observability-access`.
2. Расширить frontend journal core и route attribution helper в `uiActionJournal`.
3. Инструментировать `PoolMasterDataPage` explicit route intent и attribution.
4. Подключить child route writers `SyncStatusTab` и `DedupeReviewTab`.
5. Добавить bounded loop warning logic.
6. При необходимости расширить durable telemetry/query serializers и contracts.
7. Добавить focused tests и только потом думать о rollout на другие route-owned shells.

## Risks / Trade-offs
- Дополнительные observability events могут увеличить volume.
  - Mitigation: bounded route intent taxonomy, derived loop warnings instead of per-transition spam.
- Route writers легко могут начать писать слишком сырые diffs.
  - Mitigation: explicit allowlist of query params and normalized param diff format.
- Child writers могут неправильно связываться с `caused_by_ui_action_id`.
  - Mitigation: contract должен допускать `null` там, где write system-driven, и не подменять uncertainty ложной causal certainty.
- Pilot only on `Pool Master Data` может оставить аналогичные gaps в других routes.
  - Mitigation: это осознанный bounded first step; после подтверждённой полезности можно расширять дальше отдельными tasks/changes.
