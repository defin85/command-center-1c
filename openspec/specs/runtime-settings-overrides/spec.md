# runtime-settings-overrides Specification

## Purpose
TBD - created by archiving change add-tenancy-extensions-plan-apply. Update Purpose after archive.
## Requirements
### Requirement: Runtime settings имеют tenant overrides
Система ДОЛЖНА (SHALL) поддерживать overrides runtime settings per-tenant для поддерживаемых runtime keys, сохраняя глобальные значения как baseline.

Decommissioned key `ui.action_catalog` НЕ ДОЛЖЕН (SHALL NOT) поддерживаться через runtime settings override API.

Система ДОЛЖНА (SHALL) поддерживать tenant overrides для sync-ключей:
- `pools.master_data.sync.enabled`;
- `pools.master_data.sync.inbound.enabled`;
- `pools.master_data.sync.outbound.enabled`;
- `pools.master_data.sync.default_policy`.

Система ДОЛЖНА (SHALL) вычислять effective значения sync-ключей по precedence:
1. tenant override;
2. global runtime setting;
3. env default.

#### Scenario: Tenant override переопределяет global для поддерживаемого ключа
- **GIVEN** глобально задан `ui.operations.max_live_streams`
- **AND** tenant A имеет published override `ui.operations.max_live_streams`
- **WHEN** пользователь работает в tenant A
- **THEN** effective значение берётся из tenant override

#### Scenario: Decommissioned key `ui.action_catalog` отклоняется
- **WHEN** клиент пытается прочитать или изменить override для `ui.action_catalog`
- **THEN** API возвращает ошибку unsupported/decommissioned key
- **AND** значение key не попадает в effective runtime settings

#### Scenario: Tenant override выключает outbound sync для конкретного tenant
- **GIVEN** global baseline для `pools.master_data.sync.outbound.enabled=true`
- **AND** tenant A имеет published override `pools.master_data.sync.outbound.enabled=false`
- **WHEN** runtime вычисляет effective settings для tenant A
- **THEN** effective значение `pools.master_data.sync.outbound.enabled` равно `false`
- **AND** outbound worker не запускает mutating sync side effects для tenant A

#### Scenario: При отсутствии override используется global baseline для inbound sync
- **GIVEN** для tenant A отсутствует override `pools.master_data.sync.inbound.enabled`
- **AND** global runtime setting для ключа установлен в `true`
- **WHEN** runtime вычисляет effective settings для tenant A
- **THEN** effective значение `pools.master_data.sync.inbound.enabled` равно `true`

#### Scenario: При отсутствии override и global baseline используется env default для sync enablement
- **GIVEN** для tenant A отсутствует override `pools.master_data.sync.enabled`
- **AND** global runtime setting для ключа отсутствует
- **WHEN** runtime вычисляет effective settings для tenant A
- **THEN** effective значение `pools.master_data.sync.enabled` берётся из env default

### Requirement: Runtime-control keys MUST remain global-only outside tenant override APIs
Система ДОЛЖНА (SHALL) трактовать runtime-control и scheduler policy keys как global-only settings, а не tenant-scoped overrides.

Tenant override list/update APIs и tenant-aware effective resolution НЕ ДОЛЖНЫ (SHALL NOT) включать такие keys в supported override surface.

#### Scenario: Tenant override API отклоняет global-only scheduler key
- **GIVEN** key `runtime.scheduler.job.pool_factual_active_sync.enabled` зарегистрирован как runtime-control policy key
- **WHEN** tenant admin пытается увидеть или изменить override для этого key
- **THEN** key отсутствует в tenant override list либо update отклоняется как unsupported/global-only
- **AND** effective значение этого key берётся из global baseline/bootstrap path, а не из tenant override

