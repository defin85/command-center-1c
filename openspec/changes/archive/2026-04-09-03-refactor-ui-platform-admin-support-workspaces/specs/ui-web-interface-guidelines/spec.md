## ADDED Requirements
### Requirement: Privileged admin/support routes MUST входить в platform governance perimeter
Система ДОЛЖНА (SHALL) трактовать route pages `/rbac`, `/users`, `/dlq`, `/artifacts`, `/extensions`, `/settings/runtime`, `/settings/command-schemas` и `/settings/timeline` как следующую волну platform-governed surfaces внутри authenticated shell.

Для этих routes page-level composition ДОЛЖНА (SHALL) использовать `WorkspacePage`, `PageHeader` и соответствующие platform primitives для primary catalog/detail/authoring flows вместо raw `antd` containers как page-level foundation.

Raw `antd` imports МОГУТ (MAY) оставаться внутри leaf presentational blocks, если route shell и primary orchestration уже проходят через platform layer, но НЕ ДОЛЖНЫ (SHALL NOT) оставаться основным способом сборки route-level workspace.

#### Scenario: Lint блокирует возврат raw page shell на privileged route
- **GIVEN** разработчик меняет `/rbac`, `/extensions` или другой route из admin/support perimeter
- **WHEN** route-level page module снова использует raw `Card`, `Row`, `Col`, `Drawer`, `Modal`, `Tabs` или аналогичный container как основу primary composition
- **THEN** frontend lint сообщает platform-boundary нарушение
- **AND** изменение не проходит validation gate до возврата к canonical platform primitives

### Requirement: Admin/support platform migration MUST иметь blocking automated regression coverage
Система ДОЛЖНА (SHALL) расширить blocking frontend validation gate для migrated admin/support routes так, чтобы automated checks покрывали:
- platform-boundary regressions, которые ловятся lint;
- route-state restore и same-route stability;
- shell-safe handoff на соседние authenticated route;
- mobile-safe detail fallback и отсутствие page-wide horizontal overflow на primary operator path.

#### Scenario: Browser validation ловит regression на migrated admin/support route
- **GIVEN** migrated admin/support route уже использует platform workspace
- **WHEN** regression ломает reload/deep-link restore, same-route re-entry, shell-safe handoff или narrow-viewport detail flow
- **THEN** automated browser test фиксирует нарушение
- **AND** frontend validation gate завершается ошибкой до принятия change
