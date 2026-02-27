## MODIFIED Requirements
### Requirement: Runtime settings имеют tenant overrides
Система ДОЛЖНА (SHALL) поддерживать overrides runtime settings per-tenant для поддерживаемых runtime keys, сохраняя глобальные значения как baseline.

Система ДОЛЖНА (SHALL) поддерживать tenant override для ключа `pools.master_data.gate_enabled`, чтобы staged rollout master-data gate мог управляться в tenant scope.

Система ДОЛЖНА (SHALL) вычислять effective значение `pools.master_data.gate_enabled` по детерминированной precedence:
1. tenant override;
2. global runtime setting;
3. env default.

Decommissioned key `ui.action_catalog` НЕ ДОЛЖЕН (SHALL NOT) поддерживаться через runtime settings override API.

#### Scenario: Tenant override переопределяет global для поддерживаемого ключа
- **GIVEN** глобально задан `ui.operations.max_live_streams`
- **AND** tenant A имеет published override `ui.operations.max_live_streams`
- **WHEN** пользователь работает в tenant A
- **THEN** effective значение берётся из tenant override

#### Scenario: Tenant override выключает master-data gate для конкретного tenant
- **GIVEN** global baseline для `pools.master_data.gate_enabled=true`
- **AND** tenant A имеет published override `pools.master_data.gate_enabled=false`
- **WHEN** runtime вычисляет effective settings для tenant A
- **THEN** effective значение `pools.master_data.gate_enabled` равно `false`
- **AND** поведение gate определяется tenant override, а не global baseline

#### Scenario: При отсутствии tenant override используется global baseline
- **GIVEN** для tenant A отсутствует override `pools.master_data.gate_enabled`
- **AND** global runtime setting для ключа установлен в `true`
- **WHEN** runtime вычисляет effective settings для tenant A
- **THEN** effective значение `pools.master_data.gate_enabled` равно `true`

#### Scenario: При отсутствии override и global baseline используется env default
- **GIVEN** для tenant A отсутствует override `pools.master_data.gate_enabled`
- **AND** global runtime setting для ключа отсутствует
- **WHEN** runtime вычисляет effective settings для tenant A
- **THEN** effective значение берётся из env default

#### Scenario: Decommissioned key `ui.action_catalog` отклоняется
- **WHEN** клиент пытается прочитать или изменить override для `ui.action_catalog`
- **THEN** API возвращает ошибку unsupported/decommissioned key
- **AND** значение key не попадает в effective runtime settings
