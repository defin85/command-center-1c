## ADDED Requirements
### Requirement: Templates MUST быть единым runtime source of truth атомарных extensions-операций
Система ДОЛЖНА (SHALL) использовать `operation_exposure(surface="template")` как единственный runtime источник атомарных операций домена extensions во всех execution-путях.

`action_catalog` НЕ ДОЛЖЕН (SHALL NOT) быть runtime источником атомарной операции для `extensions.*`.

#### Scenario: Workflow node резолвится через template exposure
- **GIVEN** workflow содержит node для операции домена extensions
- **WHEN** запускается workflow execution
- **THEN** runtime configuration резолвится по `template_id`
- **AND** не используется `action_catalog` для выбора executor

#### Scenario: UI execution path резолвится через template exposure
- **GIVEN** пользователь запускает `extensions.*` операцию из UI execution path
- **WHEN** подтверждён запуск с выбранным `template_id`
- **THEN** backend строит execution на основе template exposure
- **AND** runtime-resolve через `action_catalog` не выполняется
