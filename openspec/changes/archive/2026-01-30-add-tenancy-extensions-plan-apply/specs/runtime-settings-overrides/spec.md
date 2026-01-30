## ADDED Requirements

### Requirement: Runtime settings имеют tenant overrides
Система ДОЛЖНА (SHALL) поддерживать overrides runtime settings per-tenant, сохраняя глобальные значения как baseline.

#### Scenario: Tenant override переопределяет global
- **GIVEN** глобально задан `ui.action_catalog`
- **AND** tenant A имеет published override `ui.action_catalog`
- **WHEN** пользователь работает в tenant A
- **THEN** effective `ui.action_catalog` берётся из tenant override

#### Scenario: Без override используется global
- **GIVEN** tenant B не имеет override для `ui.action_catalog`
- **WHEN** пользователь работает в tenant B
- **THEN** effective `ui.action_catalog` берётся из global значения

