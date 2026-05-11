## MODIFIED Requirements
### Requirement: Operator-facing SPA MUST вести bounded redacted action journal

Система ДОЛЖНА (SHALL) вести bounded in-memory journal для authenticated operator-facing SPA. Журнал ДОЛЖЕН (SHALL) включать только semantic events, достаточные для диагностики UI инцидентов:
- route transitions;
- explicit operator actions;
- failed или подозрительные HTTP requests;
- `ErrorBoundary` catches;
- `window.onerror` и `unhandledrejection`;
- WebSocket lifecycle events для instrumented realtime surfaces (`connect`, `reuse`, `close`, `reconnect`, `churn_warning`).

Для instrumented route-changing controls explicit operator action ДОЛЖЕН (SHALL) содержать устойчивую semantic metadata, достаточную для ответа на вопрос "какой control изменил route" без raw DOM/session replay:
- `surface_id`;
- `control_id`;
- bounded route context `from -> to` или его эквивалентную normalized форму.

Для instrumented route-owning surfaces route transition ДОЛЖЕН (SHALL) при наличии сохранять bounded causal/write attribution:
- `route_writer_owner`;
- `write_reason`;
- `navigation_mode` (`push|replace`);
- bounded `param_diff`;
- `caused_by_ui_action_id`, если route write принадлежит causal chain operator intent.

Журнал НЕ ДОЛЖЕН (SHALL NOT) превращаться в raw DOM/session replay stream.

#### Scenario: Route-changing control и последующий failure остаются causally diagnosable
- **GIVEN** оператор открывает `/pools/master-data` и переключает рабочую зону через route-changing control
- **WHEN** после route change один из backend requests завершаетcя fail-closed ошибкой
- **THEN** bounded journal содержит explicit semantic action для этого route intent
- **AND** связанный route transition содержит causal/write attribution, достаточный чтобы отделить user intent от последующего route writer
- **AND** engineer может восстановить последовательность `intent -> route write -> route transition -> request failure` без чтения browser console history

## ADDED Requirements
### Requirement: Instrumented route-owning surfaces MUST attribute route writes and emit bounded loop diagnostics

Система ДОЛЖНА (SHALL) для instrumented route-owning surfaces и их child route writers фиксировать route-write attribution всякий раз, когда они меняют canonical route/query state через `setSearchParams(...)`, `navigate(...)` или эквивалентный route mutation path.

Attribution ДОЛЖЕН (SHALL) использовать устойчивые semantic identifiers и machine-readable reason codes, а не raw UI copy или DOM selectors.

Если route state начинает bounded oscillation между конкурирующими значениями, observability layer ДОЛЖЕН (SHALL) эмитить derived machine-readable signal `route.loop_warning`, содержащий как минимум:
- `route_path`;
- `surface_id` или эквивалентный route owner;
- oscillating route keys / states;
- observed writer owners;
- transition count и bounded time window;
- последний или causal `ui_action_id`, если он есть.

#### Scenario: Pool Master Data bindings/sync loop становится diagnosable без replay
- **GIVEN** `Pool Master Data` route-owned shell и child tab writers начинают попеременно переписывать `tab=bindings` и `tab=sync`
- **WHEN** oscillation превышает configured threshold в bounded window
- **THEN** journal содержит attributed route transitions и отдельный `route.loop_warning`
- **AND** warning позволяет увидеть, был ли у цикла предшествующий explicit operator route intent
- **AND** engineer не обязан вручную реконструировать loop только по длинной последовательности `route.transition`
