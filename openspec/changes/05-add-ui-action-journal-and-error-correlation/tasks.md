## 1. Journal Contract

- [ ] 1.1 Зафиксировать schema `ui_action_journal` bundle, bounded retention, semantic event taxonomy и redaction policy для frontend session.
- [ ] 1.2 Зафиксировать canonical shared frontend instrumentation points: route transitions через router, semantic operator actions, network failures, `ErrorBoundary`, `window.onerror`, `unhandledrejection`. (после 1.1)
- [ ] 1.3 Зафиксировать WebSocket lifecycle event model: `owner`, `reuse_key`, `socket_instance_id`, connect/close/reconnect причины, active connection count и churn diagnostics. (после 1.1; можно выполнять параллельно с 1.2)

## 2. Correlation Wiring

- [ ] 2.1 Зафиксировать contract для `request_id` и `ui_action_id` между shared frontend API client, API Gateway и Orchestrator logs/problem details, включая additive/backward-compatible transport и error payload rollout. (после 1.1; можно выполнять параллельно с 1.2)
- [ ] 2.2 Зафиксировать fail-closed redaction rules для correlated diagnostics, чтобы request journal и server-side error plumbing не публиковали raw secrets или payload bodies. (после 2.1)
- [ ] 2.3 Зафиксировать frontend-side reuse policy для long-lived WebSocket channels и criteria, по которым journal должен сигнализировать о массовом пересоздании соединений вместо reuse. (после 1.3)

## 3. Tooling, Docs, Validation

- [ ] 3.1 Зафиксировать debug export path для active browser session через existing local toolkit (`eval-frontend` / Chrome CDP) и описать operator/engineer workflow, включая dump по active WebSocket owners и churn. (после 1.2, 1.3 и 2.1)
- [ ] 3.2 Добавить automated validation scope для journal schema, redaction, WebSocket reuse/churn diagnostics и end-to-end correlation plumbing на frontend/backend boundary, начиная с shared boundaries и затем расширяя route/surface-specific instrumentation. (после 1.2, 1.3, 2.2 и 2.3; можно выполнять параллельно с 3.1)
- [ ] 3.3 Прогнать `openspec validate 05-add-ui-action-journal-and-error-correlation --strict --no-interactive`.
