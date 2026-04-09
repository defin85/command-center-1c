## Контекст

Текущий built-in frontend observability слой уже умеет:
- вести bounded redacted in-memory journal;
- коррелировать `request_id` / `ui_action_id` через frontend, gateway и orchestrator;
- экспортировать текущий browser bundle через local debug toolkit.

Этого достаточно для ручной диагностики после воспроизведения, но не для целевого сценария "пользователь работал, инцидент случился, позже LLM или support tooling сами читают already persisted timeline".

В репозитории уже есть отдельный active proposal `add-agent-readable-ui-observability-access`, но он описывает consumer-facing access contract и intentionally не выбирает durable producer/storage substrate. Новый change закрывает именно этот нижний слой.

## Goals / Non-Goals

- Goals:
  - Писать semantic redacted UI telemetry в durable backend store без ручного экспорта.
  - Сохранять достаточную chronology и correlation, чтобы later analysis мог восстановить `user -> route -> action -> request -> error`.
  - Дать canonical read-only query path для recent incident timelines.
  - Сохранить redaction-first и bounded-by-design contract.
  - Не блокировать operator flow и не превращать observability в noisy analytics firehose.
- Non-Goals:
  - Вводить full session replay.
  - Логировать raw request/response bodies, cookies, auth headers или arbitrary form input.
  - Делать unbounded analytics lake или требовать ClickHouse как hard dependency.
  - Генерировать natural-language incident summaries на ingest path.

## Решения

### 1. Persistent telemetry reuse-ит существующую semantic taxonomy

Persistent pipeline НЕ вводит новый произвольный event vocabulary. Source taxonomy остаётся в `ui-action-observability`:
- route transitions;
- explicit operator actions;
- failed/suspicious HTTP requests;
- runtime/render errors;
- WebSocket lifecycle и churn diagnostics.

Это исключает divergence между local export bundle и durable telemetry store.

### 2. Frontend producer остаётся bounded и асинхронным

Frontend runtime держит локальный bounded journal как source of truth, а поверх него работает background flusher:
- собирает redacted semantic events в batched envelope;
- отправляет их по size/time threshold;
- использует page-hide / unload-safe flush fallback (`sendBeacon`-style path или эквивалентный transport);
- никогда не блокирует primary user action ожиданием telemetry ACK.

При недоступности ingest endpoint клиент:
- retries opportunistically;
- хранит только bounded queue;
- при переполнении drop-ит oldest lower-value buffered events;
- не ломает operator flow.

### 3. Durable store phase-1 опирается на PostgreSQL, а не на optional analytics stack

Для phase-1 durable storage canonical choice — append-only relational store в существующем обязательном PostgreSQL, а не ClickHouse/внешний vendor.

Причины:
- PostgreSQL уже обязателен и operationally understood;
- объём semantic events существенно меньше session replay / clickstream;
- проще обеспечить RBAC, retention, backup и query contracts в основном runtime.

Храним:
- normalized indexed columns (`tenant_id`, `user_id`, `session_id`, `occurred_at`, `event_type`, `route_path`, `request_id`, `ui_action_id`, `trace_id`);
- redacted event envelope/payload;
- batch metadata и idempotency keys.

### 4. Query layer возвращает machine-readable summaries и ordered timelines

Новый слой обязан давать не только raw event list, но и canonical query shape для recent incident analysis:
- list recent incidents/summaries по фильтрам;
- detail/timeline path для ordered событий в окне инцидента;
- фильтры минимум по `tenant`, `user`, `session`, `request_id`, `ui_action_id`, route и time window.

Query result остаётся machine-readable. LLM narration строится поверх этого ответа, а не в write path.

### 5. Server-side ingest повторно валидирует и редактирует payload

Нельзя считать client redaction достаточной. Ingest pipeline обязан:
- повторно прогонять allowlist/redaction policy;
- reject/trim oversize payloads;
- отбрасывать unknown sensitive fragments;
- обеспечивать duplicate-safe semantics через `batch_id` / `event_id`.

То есть durable store никогда не должен становиться "сырой копией browser state".

### 6. Access split: producer/storage here, consumer-facing prod access there

Этот change определяет:
- background producer;
- durable store;
- canonical read-only query contract как substrate.

Широкий agent-facing access governance, RBAC productization и multi-surface prod access policy остаются связаны с `add-agent-readable-ui-observability-access`. Новый change не дублирует тот proposal, а даёт ему storage/retrieval foundation.

## Alternatives

### A. Оставить только local export bundle
Отклонено. Не решает post-factum анализ уже завершённой пользовательской session.

### B. Сразу писать telemetry в ClickHouse
Отклонено как mandatory phase-1. Усложняет rollout и добавляет hard dependency на optional analytics stack.

### C. Писать каждый event синхронно в request path
Отклонено. Это увеличивает latency user actions и делает observability path operationally fragile.

### D. Положиться только на backend traces/problem details
Отклонено. Без frontend route/action chronology теряется человеческий контекст "что пользователь делал до ошибки".

## Risks / Trade-offs

- Semantic event volume может вырасти выше ожидаемого.
  - Mitigation: bounded taxonomy, batching, optional sampling для low-value success events, bounded retention.
- Ошибка redaction policy может превратить store в privacy risk.
  - Mitigation: server-side re-sanitization, explicit allowlist, fail-close on unknown sensitive keys.
- Query path может стать слишком "сырым" для LLM и support tooling.
  - Mitigation: хранить normalized columns + timeline-oriented response shape, а не только blob JSON.
- PostgreSQL append-only store со временем может стать дорогим.
  - Mitigation: bounded retention, indexed recent-window lookups, возможность future archive/move в analytics store без смены contract.

## Migration Plan

1. Зафиксировать capability `ui-incident-telemetry` и relation к `ui-action-observability`.
2. Добавить frontend producer contract: batching, flush policy, bounded retry queue.
3. Добавить authenticated ingest path и durable append-only store с idempotent writes.
4. Добавить read-only query contract для recent incident summaries/timelines.
5. Добавить validation scope для redaction, duplicate-safe ingest, retention и query filtering.
6. После этого расширить/реализовать consumer-facing path в `add-agent-readable-ui-observability-access`.

## Open Questions

- Нужен ли phase-2 archival/export в analytics storage для длинной retention beyond recent incidents.
- Должны ли sampled successful requests попадать в durable store по умолчанию или только explicit operator actions / failures.
- Нужна ли отдельная incident grouping materialization table, или phase-1 достаточно on-read grouping поверх normalized event rows.
