## ADDED Requirements
### Requirement: Templates MUST быть единым runtime source of truth атомарных extensions-операций
Система ДОЛЖНА (SHALL) использовать `operation_exposure(surface="template")` как единственный runtime источник атомарных операций домена extensions для обоих путей:
- workflow execution,
- manual execution из `/operations`.

`action_catalog` НЕ ДОЛЖЕН (SHALL NOT) быть runtime источником атомарной операции для `extensions.*`.

#### Scenario: Workflow node резолвится через template exposure
- **GIVEN** workflow содержит node для операции домена extensions
- **WHEN** запускается workflow execution
- **THEN** runtime configuration резолвится по `template_id`
- **AND** не используется `action_catalog` для выбора executor

#### Scenario: Manual запуск в `/operations` резолвится через template exposure
- **GIVEN** оператор запускает ручную extensions-операцию из `/operations`
- **WHEN** подтверждён запуск с выбранным `template_id`
- **THEN** backend строит execution на основе template exposure
- **AND** источник executor конфигурации остаётся единым с workflow path

