# Change: add-agent-readable-ui-observability-access

## Почему

После `expand-ui-frontend-governance-coverage` frontend perimeter станет лучше классифицирован и проверяем lint/browser gate, но это не даёт агенту или LLM runtime-доступа к реальным UI инцидентам.

В проекте уже есть backend observability stack (`Prometheus`, `Grafana`, `Jaeger`) и frontend trace viewer для server-side traces, а также отдельно запланирован built-in UI journal в `add-ui-action-journal-and-error-correlation`. Однако до сих пор не зафиксирован canonical access path, по которому агент сможет:
- на dev-контуре получить текущий machine-readable bundle воспроизведённой UI-проблемы;
- на prod-контуре читать redacted machine-readable signals о UI ошибках и коррелированных trace/request/action идентификаторах;
- делать это без обязательного session replay, DOM video capture или прямого интерактивного доступа к пользовательскому браузеру.

Блокирующий архитектурный вопрос для этой capability закрывается так: для default agent monitoring path достаточно `machine-readable traces/errors/actions`; visual replay и full session recording остаются необязательными и явно вне минимального scope.

## Что меняется

- Добавить новый capability `agent-ui-observability-access`.
- Зафиксировать canonical agent-facing access path для UI observability на двух контурах:
  - `dev/local`: debug/export surface для active browser session;
  - `prod`: authenticated read-only diagnostics/query surface для redacted recent UI incidents и их корреляции с backend traces.
- Зафиксировать, что default agent monitoring path опирается на:
  - `trace_id`
  - `request_id`
  - `ui_action_id`
  - route/release/build/runtime metadata
  - semantic error/action/journal events
  и НЕ ДОЛЖЕН (SHALL NOT) требовать visual replay как обязательное условие.
- Зафиксировать access, redaction, sampling и retention contract для agent-readable UI diagnostics, чтобы prod path был безопасным.
- Зафиксировать dependency на `add-ui-action-journal-and-error-correlation` как на source capability для frontend journal/correlation bundle.

## Impact

- Affected specs:
  - `agent-ui-observability-access` (new)
- Related existing specs/changes:
  - `ui-frontend-governance`
  - `execution-runtime-unification`
  - `add-ui-action-journal-and-error-correlation`
  - `expand-ui-frontend-governance-coverage`
- Affected code:
  - `frontend/src/**`
  - `go-services/api-gateway/**`
  - `orchestrator/apps/api_v2/**`
  - `debug/eval-frontend.sh`
  - `scripts/dev/chrome-debug.py`
  - `docs/agent/RUNBOOK.md`
  - `DEBUG.md`
- Explicitly out of scope:
  - обязательный session replay / DOM replay / video-like capture;
  - прямой интерактивный доступ LLM к продовому браузеру пользователя;
  - замена Jaeger/Grafana произвольным SaaS monitoring vendor как primary requirement.
