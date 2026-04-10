## ADDED Requirements

### Requirement: Runtime-control keys MUST remain global-only outside tenant override APIs
Система ДОЛЖНА (SHALL) трактовать runtime-control и scheduler policy keys как global-only settings, а не tenant-scoped overrides.

Tenant override list/update APIs и tenant-aware effective resolution НЕ ДОЛЖНЫ (SHALL NOT) включать такие keys в supported override surface.

#### Scenario: Tenant override API отклоняет global-only scheduler key
- **GIVEN** key `runtime.scheduler.job.pool_factual_active_sync.enabled` зарегистрирован как runtime-control policy key
- **WHEN** tenant admin пытается увидеть или изменить override для этого key
- **THEN** key отсутствует в tenant override list либо update отклоняется как unsupported/global-only
- **AND** effective значение этого key берётся из global baseline/bootstrap path, а не из tenant override
