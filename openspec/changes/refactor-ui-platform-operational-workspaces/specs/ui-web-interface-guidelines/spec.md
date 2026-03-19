## ADDED Requirements
### Requirement: High-traffic operational routes MUST входить в platform governance perimeter
Система ДОЛЖНА (SHALL) трактовать route pages `/`, `/operations`, `/databases`, `/pools/catalog` и `/pools/runs` как platform-governed surfaces следующей волны UI migration.

Для этих routes page-level composition ДОЛЖНА (SHALL) использовать `DashboardPage` или `WorkspacePage`, `PageHeader` и соответствующие platform primitives для primary catalog/detail/authoring flows вместо raw `antd` containers как page-level foundation.

Raw `antd` imports МОГУТ (MAY) оставаться внутри leaf presentational blocks, если route shell и primary orchestration уже проходят через platform layer, но НЕ ДОЛЖНЫ (SHALL NOT) оставаться основным способом сборки route-level workspace.

#### Scenario: Lint блокирует возврат raw page shell на platform-governed route
- **GIVEN** разработчик меняет `/operations` или другой route из governance perimeter
- **WHEN** route-level page module снова импортирует raw `Card`, `Row`, `Col`, `Table`, `Drawer` или аналогичный container как основу primary composition
- **THEN** frontend lint сообщает явное platform-boundary нарушение
- **AND** изменение не проходит validation gate до возврата к canonical platform primitives

### Requirement: Operational platform migration MUST иметь blocking automated regression coverage
Система ДОЛЖНА (SHALL) расширить blocking frontend validation gate для migrated operational routes так, чтобы automated checks покрывали:
- platform-boundary regressions, которые ловятся lint;
- route-state restore и same-route stability, которые проверяются browser-level tests;
- mobile-safe detail fallback и отсутствие page-wide horizontal overflow на primary operator path.

#### Scenario: Browser validation ловит regression в route-state и responsive contract
- **GIVEN** migrated operational route уже использует platform workspace
- **WHEN** regression ломает reload/back-forward restore, same-route re-entry или narrow-viewport detail flow
- **THEN** automated browser test фиксирует нарушение
- **AND** frontend validation gate завершается ошибкой до принятия change
