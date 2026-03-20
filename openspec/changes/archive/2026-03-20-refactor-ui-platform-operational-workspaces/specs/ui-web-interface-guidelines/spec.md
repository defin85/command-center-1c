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
- shell-safe internal handoff и отсутствие redundant shell reads на authenticated route;
- mobile-safe detail fallback и отсутствие page-wide horizontal overflow на primary operator path.

#### Scenario: Browser validation ловит regression в route-state и responsive contract
- **GIVEN** migrated operational route уже использует platform workspace
- **WHEN** regression ломает reload/back-forward restore, same-route re-entry, shell-safe internal handoff или narrow-viewport detail flow
- **THEN** automated browser test фиксирует нарушение
- **AND** frontend validation gate завершается ошибкой до принятия change

### Requirement: Authenticated internal navigation MUST сохранять shared shell runtime
Система ДОЛЖНА (SHALL) использовать SPA navigation для внутренних переходов между authenticated frontend route, которые живут под общим application shell.

Такие handoff path НЕ ДОЛЖНЫ (SHALL NOT) использовать full-document navigation как основной путь, если целевой route находится внутри того же frontend приложения и может быть открыт через router navigation.

Shared shell/bootstrap + authz providers ДОЛЖНЫ (SHALL) оставаться canonical owner для user/staff/tenant context. Route pages НЕ ДОЛЖНЫ (SHALL NOT) дублировать `/api/v2/system/bootstrap/`, `/api/v2/system/me/` и `/api/v2/tenants/list-my-tenants/` на default operator path, если тот же context уже доступен через shared shell runtime.

Исключения допускаются только для dedicated login/logout path, explicit refresh flows, tenant-management surfaces или route, где shell context ещё не инициализирован по design.

#### Scenario: Internal CTA переводит оператора на другой route без document reload
- **GIVEN** оператор находится на authenticated route внутри frontend shell
- **WHEN** он нажимает internal CTA или handoff action, ведущий на другой route того же приложения
- **THEN** navigation выполняется внутри SPA shell без full-document reload
- **AND** bootstrap budget не расходуется повторно только из-за этого перехода

#### Scenario: Route page использует shell-owned user и tenant context вместо повторных shell reads
- **GIVEN** shared shell runtime уже загрузил bootstrap и синхронизировал `isStaff` и active tenant
- **WHEN** route page монтируется по своему default operator path
- **THEN** страница получает user/staff/tenant context через shared providers
- **AND** не инициирует redundant вызовы `/api/v2/system/bootstrap/`, `/api/v2/system/me/` и `/api/v2/tenants/list-my-tenants/` без явного runtime trigger
