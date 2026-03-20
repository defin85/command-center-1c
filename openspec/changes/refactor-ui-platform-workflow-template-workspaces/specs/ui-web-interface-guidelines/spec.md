## ADDED Requirements
### Requirement: Workflow and template routes MUST входить в platform governance perimeter
Система ДОЛЖНА (SHALL) трактовать `/workflows`, `/workflows/executions`, `/workflows/new`, `/workflows/:id`, `/workflows/executions/:executionId`, `/templates`, `/pools/templates` и `/pools/master-data` как следующую волну platform-governed surfaces.

Для этих routes page-level composition ДОЛЖНА (SHALL) использовать `WorkspacePage`, `PageHeader` и соответствующие platform primitives для primary catalog/detail/authoring flows вместо raw `antd` containers как page-level foundation.

#### Scenario: Lint блокирует возврат raw page shell на workflow/template route
- **GIVEN** разработчик меняет `/workflows` или другой route из workflow/template perimeter
- **WHEN** route-level page module снова использует raw `Layout`, `Card`, `Tabs`, `Table`, `Modal` или `Drawer` как основу primary composition
- **THEN** frontend lint сообщает platform-boundary нарушение
- **AND** изменение не проходит validation gate до возврата к canonical platform primitives

### Requirement: Workflow/template migration MUST иметь blocking automated regression coverage
Система ДОЛЖНА (SHALL) расширить blocking frontend validation gate для migrated workflow/template routes так, чтобы automated checks покрывали:
- route-state restore и same-route stability;
- shell-safe handoff между workflow/template route и соседними authenticated route;
- mobile-safe detail or inspect fallback;
- отсутствие page-wide horizontal overflow на primary operator path.

#### Scenario: Browser validation ловит regression на workflow/template route
- **GIVEN** migrated workflow или template route уже использует platform workspace
- **WHEN** regression ломает reload/deep-link restore, same-route re-entry, shell-safe handoff или narrow-viewport inspect flow
- **THEN** automated browser test фиксирует нарушение
- **AND** frontend validation gate завершается ошибкой до принятия change
