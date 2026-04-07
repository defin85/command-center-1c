## 1. Agent access contract

- [ ] 1.1 Зафиксировать agent-readable UI observability schema для traces/errors/actions и явно закрепить, что visual replay не является mandatory частью default path.
- [ ] 1.2 Зафиксировать dev/local access path для active browser session bundle через existing debug toolkit. (после 1.1)
- [ ] 1.3 Зафиксировать prod read-only diagnostics/query surface для recent UI incidents, summaries и correlated identifiers. (после 1.1)

## 2. Safety and correlation

- [ ] 2.1 Зафиксировать dependency на `05-add-ui-action-journal-and-error-correlation` и contract reuse для `trace_id`, `request_id`, `ui_action_id`. (после 1.1)
- [ ] 2.2 Зафиксировать RBAC, redaction, sampling и retention rules для prod agent monitoring path. (после 1.3)
- [ ] 2.3 Зафиксировать canonical backend trace lookup path, чтобы agent мог перейти от UI incident к correlated server-side diagnostics без screen scraping vendor UI. (после 2.1; можно параллельно с 2.2)

## 3. Docs and validation

- [ ] 3.1 Описать canonical agent workflow для dev и prod в runbook/debug guidance. (после 1.2, 1.3, 2.2, 2.3)
- [ ] 3.2 Добавить validation scope для agent-readable schema, redaction/RBAC и query/export contract. (после 2.2 и 2.3)
- [ ] 3.3 Прогнать `openspec validate add-agent-readable-ui-observability-access --strict --no-interactive`.
