# Change: add-ui-action-journal-and-error-correlation

## Why

Сейчас диагностика frontend-инцидентов в product UI опирается на ручную связку из browser console, HAR и хвостов `logs/frontend.log` / `logs/orchestrator.log` / `logs/api-gateway.log`. Такой путь помогает локально воспроизвести сбой, но не даёт bounded machine-readable trail вида `операторское действие -> route context -> HTTP запрос -> problem details / runtime error`.

В репозитории уже есть backend tracing, event correlation и admin audit для части server-side flows, но нет минимального built-in frontend action journal. `ErrorBoundary` пишет только в `console.error`, а existing debug toolkit умеет выполнить JS в браузере, но не имеет canonical session bundle, который можно снять после ручного воспроизведения UI-проблемы.

Нужен узкий phase-1 change, который:
- добавит bounded redacted UI journal для operator-facing SPA;
- свяжет key UI actions и HTTP ошибки через explicit correlation identifiers;
- зафиксирует WebSocket lifecycle observability для shared и dedicated realtime surfaces, чтобы было видно, кто массово создаёт соединения и не переиспользует их;
- даст штатный debug export path без внедрения внешнего session replay vendor и без логирования raw чувствительных данных.

## What Changes

- Добавить новый capability `ui-action-observability`.
- Зафиксировать bounded in-memory frontend journal для authenticated SPA, который хранит только semantic events:
  - route transitions;
  - key operator actions;
  - failed/suspicious API requests;
  - `ErrorBoundary`, `window.onerror` и `unhandledrejection`;
  - WebSocket connect / close / reconnect / reuse events с owner metadata;
  - route/entity context (`pool_id`, `run_id`, `operation_id` и т.п.), когда он уже известен surface.
- Зафиксировать end-to-end correlation contract для instrumented HTTP requests:
  - frontend создаёт `request_id` и `ui_action_id` для instrumented calls;
  - gateway/orchestrator сохраняют их в logs / diagnostics;
  - `application/problem+json` и эквивалентные fail-closed error payloads возвращают `request_id`, а при наличии и `ui_action_id`.
- Зафиксировать frontend-side WebSocket ownership/reuse contract:
  - long-lived shared channels объявляют стабильный `owner` / `reuse_key`;
  - journal фиксирует active connection count, reconnect churn и close codes;
  - debug bundle позволяет увидеть, какой hook/store/surface создаёт избыточные соединения вместо reuse.
- Зафиксировать безопасный debug export path для active frontend session через существующий local debug toolkit, чтобы инженер мог снять JSON bundle без ручного copy/paste из console.
- Зафиксировать redaction policy: журнал и коррелированные error payloads НЕ ДОЛЖНЫ (SHALL NOT) включать tokens, cookies, raw request/response bodies, password-like fields и другие чувствительные значения.

## Impact

- Affected specs:
  - `ui-action-observability` (new)
- Related existing specs:
  - `execution-runtime-unification`
  - `ui-frontend-governance`
- Affected code:
  - `frontend/src/App.tsx`
  - `frontend/src/components/ErrorBoundary.tsx`
  - `frontend/src/api/**`
  - `frontend/src/pages/**`
  - `go-services/api-gateway/**`
  - `orchestrator/apps/api_v2/**`
  - `orchestrator/apps/operations/**`
  - `debug/eval-frontend.sh`
  - `scripts/dev/chrome-debug.py`
  - `DEBUG.md`
- Explicitly out of scope:
  - SaaS monitoring / session replay providers (`Sentry`, `LogRocket`, `Datadog RUM` и т.п.);
  - полная запись DOM-кликов, клавиатурного ввода и session replay timeline;
  - логирование raw request/response bodies;
  - новый product-facing UI screen для просмотра журнала внутри SPA;
  - попытка заменить существующий backend audit log для доменных write-операций.
