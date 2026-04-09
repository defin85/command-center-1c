## ADDED Requirements

### Requirement: Operator-facing SPA MUST asynchronously upload redacted semantic telemetry while user works

Система ДОЛЖНА (SHALL) отправлять redacted semantic UI telemetry в фоне, пока оператор работает в SPA, без ручного export шага. Persistent upload ДОЛЖЕН (SHALL) reuse-ить semantic taxonomy из `ui-action-observability` и НЕ ДОЛЖЕН (SHALL NOT) расширяться до raw DOM/session replay stream.

Foreground user actions НЕ ДОЛЖНЫ (SHALL NOT) ждать подтверждения telemetry upload как обязательного условия завершения.

#### Scenario: Оператор выполняет action, а telemetry уходит в фоне
- **GIVEN** оператор открывает product route и выполняет semantic action
- **WHEN** событие попадает в client-side telemetry batch и наступает flush threshold или unload-safe flush
- **THEN** браузер отправляет redacted batch в фоне
- **AND** операторский flow не блокируется ожиданием telemetry ACK

### Requirement: Ingested telemetry MUST preserve correlation and incident chronology in durable storage

Система ДОЛЖНА (SHALL) сохранять accepted telemetry в durable append-only storage с нормализованными полями как минимум:
- `tenant_id`;
- `user_id` или эквивалентный actor identifier;
- `session_id`;
- `occurred_at`;
- `event_type`;
- route metadata;
- `request_id`, `ui_action_id`, `trace_id` при наличии.

Durable store ДОЛЖЕН (SHALL) позволять восстановить ordered incident timeline по `session_id`, correlation identifiers и time window.

#### Scenario: Timeline восстанавливается по session и correlation ids
- **GIVEN** один operator intent приводит к HTTP failure и последующей UI ошибке
- **WHEN** telemetry batch принят и сохранён
- **THEN** query path позволяет восстановить ordered sequence `action -> request -> failure -> UI error`
- **AND** события остаются связуемыми через `session_id`, `request_id` или `ui_action_id`

### Requirement: System MUST provide a read-only query surface for recent UI incident analysis

Система ДОЛЖНА (SHALL) предоставлять authenticated read-only query surface для recent UI incident summaries и ordered timelines.

Минимально поддерживаемые фильтры:
- tenant;
- user/actor;
- `session_id`;
- `request_id`;
- `ui_action_id`;
- route/path;
- time window.

Ответ ДОЛЖЕН (SHALL) быть machine-readable и достаточным для последующего LLM анализа без прямого подключения к живому пользовательскому браузеру.

#### Scenario: Support tooling читает recent incidents пользователя
- **GIVEN** support engineer или authorized automation знает tenant, user и time window инцидента
- **WHEN** она вызывает canonical query surface
- **THEN** система возвращает recent incident summaries и ordered timelines в machine-readable виде
- **AND** этих данных достаточно, чтобы связать UI symptom с route/action/error chronology без browser attach

### Requirement: Persistent UI telemetry MUST remain redaction-first and bounded

Система ДОЛЖНА (SHALL) применять redaction policy и на client producer, и на server ingest path.

Persistent telemetry НЕ ДОЛЖНА (SHALL NOT) хранить:
- raw request/response bodies;
- auth headers;
- cookies;
- password/token/secret-like fields;
- не-whitelisted form input fragments.

Retention ДОЛЖНА (SHALL) быть bounded; indefinite storage для UI telemetry запрещено.

#### Scenario: Sensitive field не попадает в durable telemetry store
- **GIVEN** route, action context или error payload содержит sensitive value
- **WHEN** telemetry batch проходит client upload, server ingest и subsequent query
- **THEN** durable store и query result содержат только redacted/whitelisted metadata
- **AND** raw sensitive value отсутствует на всех persistent/query surfaces

### Requirement: Telemetry pipeline MUST be resilient to sink failures and duplicate delivery

Система ДОЛЖНА (SHALL) использовать bounded client buffering и duplicate-safe ingest semantics.

При временной недоступности ingest path pipeline ДОЛЖЕН (SHALL):
- retry-ить opportunistically;
- не ломать primary operator flow;
- сохранять bounded queue semantics;
- предотвращать duplicate durable writes при повторной доставке того же batch/event.

#### Scenario: Ingest endpoint временно недоступен
- **GIVEN** браузер накопил telemetry batch и ingest endpoint временно недоступен
- **WHEN** flush attempt завершается ошибкой
- **THEN** операторский flow продолжается без user-visible failure из-за telemetry path
- **AND** клиент retry-ит или удерживает batch только в пределах bounded capacity
- **AND** повторная доставка не создаёт duplicate durable events после восстановления сервиса

### Requirement: Query access MUST be tenant-scoped and explicitly authorized

Система ДОЛЖНА (SHALL) защищать query surface через explicit authorization и tenant scoping.

Actor без требуемых прав НЕ ДОЛЖЕН (SHALL NOT) получать recent incident summaries, event timelines или correlation metadata другого tenant/user.

#### Scenario: Неавторизованный actor не получает persistent UI telemetry
- **GIVEN** actor без требуемых observability прав пытается запросить recent UI incidents
- **WHEN** он вызывает canonical query surface
- **THEN** система fail-close'ится с authorization error
- **AND** никакие incident details или correlation fields не возвращаются
