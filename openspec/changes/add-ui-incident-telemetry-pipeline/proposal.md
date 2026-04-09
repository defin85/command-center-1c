# Change: add-ui-incident-telemetry-pipeline

## Почему

`ui-action-observability` уже закрывает phase-1 задачу: browser ведёт bounded redacted journal, а engineer может вручную снять bundle после воспроизведения инцидента. Этого недостаточно для целевого сценария, где оператор просто работает, а LLM или support tooling позже самостоятельно анализируют уже случившийся UI инцидент без ручного browser dump.

Сейчас после закрытия вкладки или потери локальной browser session in-memory journal исчезает. В результате:
- нельзя автоматически собрать timeline `user -> route -> action -> request -> error` для уже произошедшего инцидента;
- нельзя читать recent UI incidents по tenant/user/session/request без подключения к живому браузеру;
- активный change `add-agent-readable-ui-observability-access` остаётся без durable producer/storage substrate.

Нужен отдельный change, который добавит persistent redacted telemetry pipeline: background upload из SPA, durable append-only storage и canonical read-only query path для recent incident timelines.

## Что меняется

- Добавить новый capability `ui-incident-telemetry`.
- Зафиксировать, что operator-facing SPA ДОЛЖНА (SHALL) асинхронно и в фоне отправлять redacted semantic UI events, пока пользователь работает, без ручного export шага.
- Зафиксировать canonical batch envelope для client -> backend ingest, включая:
  - tenant/user/session/release metadata;
  - route context;
  - event chronology;
  - `trace_id`, `request_id`, `ui_action_id` при наличии;
  - flush reason и idempotency fields.
- Зафиксировать durable append-only storage для recent UI incident telemetry с bounded retention и индексами по `tenant_id`, `user_id`, `session_id`, `request_id`, `ui_action_id` и time window.
- Зафиксировать authenticated read-only query surface для recent incident summaries и ordered timelines, пригодных для последующего LLM анализа без browser attach.
- Зафиксировать fail-closed redaction, bounded buffering, retry/backpressure и duplicate-safe ingest semantics.
- Зафиксировать relation:
  - `ui-action-observability` остаётся source-of-truth для semantic event taxonomy и local debug export;
  - `add-agent-readable-ui-observability-access` использует этот durable telemetry substrate как prod/dev retrieval layer, а не дублирует его.

## Impact

- Affected specs:
  - `ui-incident-telemetry` (new)
- Related existing specs/changes:
  - `ui-action-observability`
  - `execution-runtime-unification`
  - `tenancy-tenant-context`
  - `add-agent-readable-ui-observability-access`
- Affected code:
  - `frontend/src/observability/**`
  - `frontend/src/api/**`
  - `go-services/api-gateway/**`
  - `orchestrator/apps/api_v2/**`
  - `docs/agent/RUNBOOK.md`
  - `DEBUG.md`
- Explicitly out of scope:
  - обязательный session replay / DOM replay / video capture;
  - запись каждого DOM click/keypress или full browser console mirror;
  - неограниченное хранение UI telemetry;
  - inline LLM summarization на write path ingestion endpoint.
