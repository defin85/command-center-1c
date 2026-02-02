# Delta: extensions-action-catalog

## MODIFIED Requirements

### Requirement: Action executors
Система ДОЛЖНА (SHALL) поддерживать action executors `ibcmd_cli`, `designer_cli` и `workflow` в action catalog.

#### Scenario: ibcmd_cli action маппится на execute-ibcmd-cli и использует профиль подключения базы
- **WHEN** действие использует executor `ibcmd_cli`
- **THEN** его можно выполнить через `POST /api/v2/operations/execute-ibcmd-cli/` с промаппленными полями
- **AND** действие НЕ содержит `executor.connection` (connection не хранится на уровне action)
- **AND** connection для каждой таргет-базы резолвится из профиля подключения этой базы (или per-run override, если задан)
- **AND** mixed mode допустим (часть баз remote, часть offline) в рамках одного bulk запуска

#### Scenario: workflow action маппится на execute-workflow
- **WHEN** действие использует executor `workflow`
- **THEN** его можно выполнить через `POST /api/v2/workflows/execute-workflow/` с промаппленными `workflow_id` и `input_context`

