## ADDED Requirements
### Requirement: Infrastructure and observability routes MUST входить в platform governance perimeter
Система ДОЛЖНА (SHALL) трактовать `/clusters`, `/system-status` и `/service-mesh` как platform-governed surfaces внутри authenticated frontend.

Для этих routes page-level composition ДОЛЖНА (SHALL) использовать `WorkspacePage`, `PageHeader` и соответствующие platform primitives для primary catalog, diagnostics и inspect flows вместо bespoke raw `antd` page shells.

#### Scenario: Lint блокирует возврат bespoke page shell на infra route
- **GIVEN** разработчик меняет `/clusters`, `/system-status` или `/service-mesh`
- **WHEN** route-level page module снова использует raw `Card`, `Row`, `Col`, `Layout`, `Modal`, `Drawer` или custom div/css shell как основу primary composition
- **THEN** frontend lint сообщает platform-boundary нарушение
- **AND** изменение не проходит validation gate до возврата к canonical platform primitives

### Requirement: Infra/observability migration MUST иметь blocking automated regression coverage
Система ДОЛЖНА (SHALL) расширить blocking frontend validation gate для migrated infra/observability routes так, чтобы automated checks покрывали:
- route-state restore и same-route stability;
- responsive fallback и отсутствие page-wide horizontal overflow;
- shell-safe handoff на соседние authenticated route;
- polling/realtime stability на operator-facing route path.

#### Scenario: Browser validation ловит regression на infra/observability route
- **GIVEN** migrated infra или observability route уже использует platform workspace
- **WHEN** regression ломает route-state restore, responsive fallback или polling/realtime interaction contract
- **THEN** automated browser test фиксирует нарушение
- **AND** frontend validation gate завершается ошибкой до принятия change
