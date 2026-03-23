## Context

В текущем репозитории уже существуют отдельные observability building blocks:
- server-side correlation и trace metadata для execution/runtime flows;
- `AdminActionAuditLog` для части privileged API actions;
- local debug toolkit (`debug/eval-frontend.sh`, `scripts/dev/chrome-debug.py`) для ad-hoc browser inspection.

При этом operator-facing SPA не хранит canonical bounded trail пользовательских действий и frontend ошибок:
- `ErrorBoundary` пишет только в browser console;
- browser runtime errors не собираются в machine-readable session bundle;
- ручной анализ требует склеивать console, network и service logs без единого `ui_action_id`.
- realtime surfaces не публикуют canonical ownership/reuse diagnostics по WebSocket connections, поэтому при churn в browser console видно только факт множества connect/close событий, но не источник логического владельца и не нарушение reuse policy.

## Goals / Non-Goals

- Goals:
  - Ввести минимальный built-in frontend journal для ручной диагностики UI-инцидентов.
  - Связать semantic UI action, HTTP request, server-side log и problem details через explicit correlation fields.
  - Сделать видимым frontend WebSocket churn: какой hook/store/surface создаёт соединения, reused оно или dedicated, и где начинается массовое пересоздание.
  - Дать инженерный способ снять session bundle после ручного воспроизведения без правок кода на лету.
  - Зафиксировать redaction-first contract, чтобы observability слой не превратился в канал утечки чувствительных данных.
- Non-Goals:
  - Внедрять внешний monitoring/replay vendor.
  - Записывать все DOM clicks/keystrokes или строить pixel-perfect session replay.
  - Добавлять новый end-user экран с просмотром journal bundle.
  - Дублировать существующие backend audit logs для всех доменных write-путей.

## Decisions

### 1. Журнал остаётся bounded и in-memory

Phase 1 использует bounded ring buffer в памяти frontend runtime. Это достаточно для локального воспроизведения и предотвращает бесконтрольный рост данных. Persistence в localStorage / IndexedDB / server storage в этот change не входит.

Базовый bundle включает:
- `session_id`;
- `captured_at`;
- `release/build` fingerprint;
- список `events[]`.

Каждое событие содержит минимум:
- `event_id`;
- `event_type`;
- `occurred_at`;
- `route`;
- `context` (только whitelisted entity ids и view state);
- `ui_action_id` при наличии;
- `request_id` / `trace_id` при наличии;
- `outcome` и machine-readable error fields для failure paths.

Для WebSocket lifecycle events дополнительно нужны:
- `socket_instance_id`;
- `owner`;
- `reuse_key`;
- `channel_kind` (`shared|dedicated`);
- `active_connections_for_reuse_key`;
- `close_code` / `close_reason`, если соединение закрыто.

### 2. Захватываются только semantic events

Система не пишет raw DOM event stream. Вместо этого она инструментирует только product-significant переходы:
- route open / route change;
- explicit operator actions вроде submit / retry / inspect / trigger;
- failed or slow API request;
- render/runtime errors.

Для realtime surfaces semantic events также включают:
- WebSocket connect;
- reconnect scheduled / reconnect succeeded;
- close/error;
- reuse hit / reuse miss;
- churn warning, если один `owner` или `reuse_key` создаёт избыточное число параллельных или последовательных соединений за bounded interval.

Такой слой даёт достаточно сигнала для диагностики, но не создаёт noise wall и не собирает лишние пользовательские данные.

### 3. Корреляция разделяется на `ui_action_id` и `request_id`

`ui_action_id` объединяет набор связанных journal events внутри одного operator intent. `request_id` относится к конкретному HTTP request.

Принятый flow:
- frontend создаёт `ui_action_id` на semantic action;
- каждый instrumented HTTP request получает свой `request_id` и наследует текущий `ui_action_id`;
- gateway/orchestrator сохраняют оба значения в runtime logs, если они присутствуют;
- error responses (`problem+json` и эквивалентные fail-closed payloads) возвращают `request_id`, а при наличии и `ui_action_id`.

Это позволяет разбирать как single-request инциденты, так и составные сценарии, где одна UI-команда вызывает несколько запросов.

### 4. WebSocket observability фиксирует владельца и reuse semantics

Для каждого instrumented WebSocket surface вводятся:
- `owner` — стабильный идентификатор логического владельца (`serviceMeshManager`, `useWorkflowExecution`, `databaseStreamProvider` и т.п.);
- `reuse_key` — logical channel key, по которому expected reuse можно проверить автоматически;
- `channel_kind` — `shared` для singleton/manager-style connections и `dedicated` для resource-scoped connections.

Journal обязан фиксировать:
- создание нового socket instance;
- reuse существующего instance;
- reconnect/close code;
- текущий active connection count по `reuse_key`.

Если surface, объявленный как `shared`, создаёт больше одного active instance на одинаковый `reuse_key`, либо churn по тому же `owner`/`reuse_key` превышает agreed threshold за bounded interval, journal должен публиковать machine-readable churn event. Это не блокирует runtime само по себе, но делает утечку или неверный lifecycle immediately diagnosable в export bundle.

### 5. Debug export path строится поверх существующего toolkit

Вместо нового product surface change использует уже существующий local debug toolkit. Frontend exposes canonical dump function / object, который можно снять через `debug/eval-frontend.sh` или Chrome CDP helper.

Это даёт минимальную стоимость внедрения и сразу решает инженерный use case: пользователь воспроизводит баг в локальном окружении, инженер снимает bounded journal bundle и сопоставляет его с server logs.

Export bundle должен включать сводку:
- `active_http_requests`;
- `active_websockets_by_owner`;
- `active_websockets_by_reuse_key`;
- recent churn anomalies.

### 6. Redaction обязателен по умолчанию

В observability bundle разрешены только whitelisted поля. Нельзя логировать:
- `Authorization` и другие auth headers;
- cookies;
- raw request/response bodies;
- password/token/secret-like form fields;
- чувствительные payload fragments из problem details, если они не прошли явную нормализацию.

При сомнении система должна fail-close и опускать поле из journal/export, а не включать его "на всякий случай".

## Risks / Trade-offs

- Слишком узкая таксономия semantic events может пропустить редкие UX-path инциденты.
  - Mitigation: начать с route/actions/errors/network failures и расширять только по реальным инцидентам.
- Слишком широкая таксономия быстро превратит journal в noisy console mirror.
  - Mitigation: не писать raw DOM events и не писать успешные low-value requests без явной причины.
- Корреляция через headers затрагивает несколько слоёв (`frontend -> gateway -> orchestrator`).
  - Mitigation: зафиксировать один canonical contract в spec до начала реализации и покрыть boundary tests.
- Churn thresholds для WebSocket surfaces могут оказаться слишком жёсткими или слишком мягкими.
  - Mitigation: phase 1 фиксирует machine-readable counters/events и conservative defaults; blocking behavior в runtime не вводится.

## Migration Plan

1. Зафиксировать capability `ui-action-observability` и event/correlation schema.
2. Инструментировать shared frontend boundaries (`router`, API client, `ErrorBoundary`, global error hooks).
3. Пробросить `request_id` / `ui_action_id` через gateway/orchestrator error/logging path.
4. Добавить debug export workflow и automated validation.

## Open Questions

- Нужен ли phase-2 persisted server-side ingestion journal bundle, или локального debug export path достаточно на обозримый период.
- Нужно ли включать sampled successful requests в journal, или phase-1 должен фиксировать только failures и explicitly annotated operator actions.
