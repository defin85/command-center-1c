## MODIFIED Requirements
### Requirement: Runtime settings имеют tenant overrides
Система ДОЛЖНА (SHALL) поддерживать overrides runtime settings per-tenant для поддерживаемых runtime keys, сохраняя глобальные значения как baseline.

Decommissioned key `ui.action_catalog` НЕ ДОЛЖЕН (SHALL NOT) поддерживаться через runtime settings override API.

#### Scenario: Tenant override переопределяет global для поддерживаемого ключа
- **GIVEN** глобально задан `ui.operations.max_live_streams`
- **AND** tenant A имеет published override `ui.operations.max_live_streams`
- **WHEN** пользователь работает в tenant A
- **THEN** effective значение берётся из tenant override

#### Scenario: Decommissioned key `ui.action_catalog` отклоняется
- **WHEN** клиент пытается прочитать или изменить override для `ui.action_catalog`
- **THEN** API возвращает ошибку unsupported/decommissioned key
- **AND** значение key не попадает в effective runtime settings
