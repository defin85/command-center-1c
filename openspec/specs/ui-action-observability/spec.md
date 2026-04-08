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
- `window.onerror` и `unhandledrejection`.
- WebSocket lifecycle events для instrumented realtime surfaces (`connect`, `reuse`, `close`, `reconnect`, `churn_warning`).

Журнал НЕ ДОЛЖЕН (SHALL NOT) превращаться в raw DOM/session replay stream.

#### Scenario: Route change и последующая UI ошибка попадают в один journal bundle
- **GIVEN** оператор открывает product route и выполняет semantic action
- **WHEN** после этого возникает render/runtime ошибка
- **THEN** bounded journal содержит запись о route context, semantic action и error event
- **AND** engineer может восстановить последовательность событий без чтения browser console history

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
