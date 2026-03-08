## ADDED Requirements
### Requirement: Templates MUST публиковать workflow-safe profile для reusable service automation
Система ДОЛЖНА (SHALL) поддерживать для template exposures явный `workflow-safe profile`, который определяет, можно ли использовать template как reusable step в service workflows.

Минимально profile ДОЛЖЕН (SHALL) поддерживать:
- `workflow_safe` boolean;
- capability/domain tags;
- target scope;
- side-effect summary;
- verification hints;
- idempotency expectation.

#### Scenario: Template без workflow-safe profile не считается reusable workflow step
- **GIVEN** template опубликован без `workflow_safe=true`
- **WHEN** пользователь пытается использовать его как reusable service workflow step
- **THEN** editor/runtime отклоняет такой выбор
- **AND** template может оставаться доступным для direct/manual execution, если домен это допускает

### Requirement: Workflow-safe template selection MUST скрывать raw command-schema details
Система ДОЛЖНА (SHALL) при выборе workflow-safe template в workflow editor показывать reusable execution contract и НЕ ДОЛЖНА (SHALL NOT) требовать от автора workflow работы с raw `Command Schema` полями или низкоуровневым `argv`.

#### Scenario: Автор workflow видит contract template, а не raw command builder
- **GIVEN** workflow-safe template основан на schema-driven executor
- **WHEN** пользователь вставляет этот template в workflow
- **THEN** editor показывает reusable contract template
- **AND** raw command-schema builder остаётся внутренним инструментом редактирования template, а не workflow step
