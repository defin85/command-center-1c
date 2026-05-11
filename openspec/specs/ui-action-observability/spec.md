# ui-action-observability Specification

## Purpose
Capability defines the bounded, redaction-first UI journal for the operator-facing SPA, plus end-to-end action/request correlation, WebSocket reuse diagnostics, and canonical debug export for incident analysis.
## Requirements
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

### Requirement: Instrumented WebSocket surfaces MUST публиковать owner и reuse diagnostics

Система ДОЛЖНА (SHALL) для каждого instrumented WebSocket connection фиксировать:
- `owner`;
- `reuse_key`;
- `channel_kind` (`shared|dedicated`);
- `socket_instance_id`;
- lifecycle outcome (`connect|reuse|close|reconnect`);
- `active_connections_for_reuse_key`.

Shared long-lived channels ДОЛЖНЫ (SHALL) иметь стабильный `reuse_key`, позволяющий определить, было ли соединение reused или открыто заново без необходимости.

#### Scenario: Shared WebSocket churn становится diagnosable
- **GIVEN** shared realtime surface ошибочно создаёт несколько WebSocket instances вместо reuse
- **WHEN** оператор воспроизводит проблему в браузере
- **THEN** journal bundle показывает одинаковый `owner` и `reuse_key` для этих instances
- **AND** bundle содержит machine-readable churn signal или active connection count, достаточный для определения источника утечки соединений

### Requirement: Instrumented UI requests MUST быть коррелированы end-to-end

Система ДОЛЖНА (SHALL) присваивать instrumented UI actions значение `ui_action_id`, а каждому instrumented HTTP request — значение `request_id`.

Shared frontend API client ДОЛЖЕН (SHALL) передавать эти значения в API Gateway и downstream runtime через canonical headers или эквивалентный transport contract. API Gateway и Orchestrator ДОЛЖНЫ (SHALL) сохранять эти поля в diagnostic logs и problem/error payloads, когда запрос завершился fail-closed ошибкой.

#### Scenario: Problem details можно связать с конкретным UI действием
- **GIVEN** оператор запускает instrumented action из product UI
- **WHEN** backend отвечает `application/problem+json`
- **THEN** response payload содержит `request_id`
- **AND** при наличии содержит `ui_action_id`
- **AND** frontend journal и server-side logs можно сопоставить по тем же значениям

### Requirement: Debug toolkit MUST уметь экспортировать текущий UI journal bundle

Система ДОЛЖНА (SHALL) предоставлять canonical debug export path для active browser session через existing local debug toolkit, чтобы инженер мог снять текущий bounded journal bundle без ручного копирования console output.

Export path ДОЛЖЕН (SHALL) возвращать machine-readable JSON bundle с release/session metadata, redacted events и текущей summary по active WebSocket owners / reuse keys.

#### Scenario: Инженер снимает bundle после ручного воспроизведения бага
- **GIVEN** пользователь или инженер воспроизвёл UI-инцидент в локальном runtime
- **WHEN** инженер использует repository-defined debug toolkit для frontend eval/dump
- **THEN** он получает JSON bundle текущего UI journal
- **AND** bundle содержит route/action/error chronology и WebSocket ownership/reuse summary, пригодные для дальнейшего анализа

### Requirement: UI journal и correlation plumbing MUST быть redaction-first

Система ДОЛЖНА (SHALL) гарантировать, что UI journal, debug export bundle, correlated logs и problem/error payloads не содержат raw чувствительные данные, включая:
- auth headers;
- cookies;
- raw request/response bodies;
- password/token/secret-like fields;
- не-whitelisted fragments form input.

Если значение не прошло policy redaction, система НЕ ДОЛЖНА (SHALL NOT) включать его в journal или export bundle.

#### Scenario: Чувствительное поле не попадает в journal bundle
- **GIVEN** операторский action использует sensitive form field или auth context
- **WHEN** action завершаетcя ошибкой и journal bundle экспортируется
- **THEN** bundle содержит только whitelisted metadata и correlation fields
- **AND** raw sensitive value отсутствует в journal, error payload и correlated logs

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
