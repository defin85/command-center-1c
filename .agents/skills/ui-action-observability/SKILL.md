---
name: ui-action-observability
description: Use when debugging frontend incidents through the shipped UI action journal bundle, request_id/ui_action_id correlation, WebSocket churn diagnostics, or when extending this observability wiring in frontend and orchestrator.
---

# UI Action Observability

## What This Skill Does

Пакует repeatable workflow для shipped capability `ui-action-observability`: снять bounded UI journal bundle, связать его с `request_id` / `ui_action_id` на backend boundary и безопасно расширить instrumentation без поломки redaction-first contract.

## When To Use

Используй, когда пользователь просит:

- "сними UI journal"
- "разбери frontend-инцидент через request_id/ui_action_id"
- "проверь, почему action сломался и как это связано с backend error"
- "добавь/исправь trackUiAction, request correlation или websocket observability"
- "проверь churn/reuse WebSocket"

Не используй для обычной UI-правки без observability/debug scope.

## Primary Surfaces

- spec: `openspec/specs/ui-action-observability/spec.md`
- frontend journal core: `frontend/src/observability/uiActionJournal.ts`
- frontend wiring: `frontend/src/App.tsx`
- shared HTTP correlation: `frontend/src/api/client.ts`
- semantic confirm helper: `frontend/src/observability/confirmWithTracking.ts`
- boundary capture: `frontend/src/components/ErrorBoundary.tsx`
- realtime instrumentation example: `frontend/src/hooks/useWorkflowExecution.ts`
- backend correlation + redaction: `orchestrator/apps/api_v2/observability.py`
- debug export path: `debug/export-ui-journal.sh`

## Workflow

1. Прочитай `docs/agent/RUNBOOK.md`, `docs/agent/VERIFY.md` и `DEBUG.md`, если задача про runtime incident или export bundle.
2. Для usage/debug сначала воспроизведи проблему на аутентифицированной frontend session.
3. Сними bundle через `./debug/export-ui-journal.sh [url-pattern]` или `./debug/eval-frontend.sh "JSON.stringify(window.__CC1C_UI_JOURNAL__?.exportBundle() ?? null, null, 2)"`.
4. В bundle анализируй:
   - `events[]` для route/action/error chronology;
   - `active_http_requests`;
   - `active_websockets_by_owner`;
   - `active_websockets_by_reuse_key`;
   - `recent_churn_anomalies`.
5. Для HTTP failure path сопоставь `request_id` и `ui_action_id` из bundle с backend problem payload и server logs.
6. Если меняешь instrumentation, сначала найди правильный boundary:
   - route/global runtime hooks: `frontend/src/App.tsx`
   - form/modal/drawer confirms: platform shells и `confirmWithTracking.ts`
   - API request lifecycle: `frontend/src/api/client.ts`
   - render/runtime failures: `frontend/src/components/ErrorBoundary.tsx`
   - realtime lifecycle: конкретный hook/store, по примеру `frontend/src/hooks/useWorkflowExecution.ts`
   - server-side correlation/redaction: `orchestrator/apps/api_v2/observability.py`

## Implementation Rules

- Instrument only semantic events. Не добавляй raw DOM/session replay stream.
- Для explicit operator actions используй `trackUiAction(...)` или `confirmWithTracking(...)`.
- Не прокидывай в journal сырые form values; оставляй только whitelisted metadata.
- Не ломай transport contract: frontend должен передавать `X-Request-ID` и `X-UI-Action-ID`, backend должен возвращать их в headers/problem payloads на fail-closed paths.
- Для WebSocket instrumentation фиксируй `owner`, `reuseKey`, `channelKind`, `socketInstanceId`, lifecycle outcome и churn signal.
- Учитывай shipped guardrail: production callsites `trackUiAction` должны оставаться sync или microtask-detached; не вводи произвольные `async` handlers без обновления supporting logic и tests.

## Validation

- frontend journal/redaction/unit scope:
  - `cd frontend && npx vitest run src/observability/__tests__/uiActionJournal.test.ts src/api/__tests__/client.observability.test.ts src/observability/__tests__/trackUiActionUsage.test.ts`
- orchestrator correlation/redaction scope:
  - `./scripts/dev/pytest.sh -q orchestrator/apps/api_v2/tests/test_problem_details_request_correlation.py`
- для docs/routing изменений:
  - `./scripts/dev/check-agent-doc-freshness.sh`
- если трогал реальный UI flow, добавь runtime/export proof:
  - `./debug/export-ui-journal.sh [url-pattern]`

## Success Criteria

- UI incident можно разобрать по одному bounded bundle без console archaeology
- `request_id` / `ui_action_id` бьются между frontend bundle и backend payload/logs
- sensitive fields не попадают в journal и correlated error payloads
- validation покрывает изменённый boundary

## Practical Jobs

Примеры:
- "Сними journal bundle после падения `/pools/runs` и найди связанный backend request."
- "Добавь observability для нового confirm flow через `trackUiAction` и проверь redaction."
- "Разбери, почему dedicated/shared WebSocket churn-ится, и покажи owner/reuse_key."
