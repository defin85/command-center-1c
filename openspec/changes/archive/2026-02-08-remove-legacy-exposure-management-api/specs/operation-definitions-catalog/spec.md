# Spec Delta: operation-definitions-catalog

## MODIFIED Requirements
### Requirement: Unified contract MUST иметь явный API для definitions/exposures
Система ДОЛЖНА (SHALL) использовать `operation-catalog` API как основной management-контур для обеих surfaces:
- `template`,
- `action_catalog`.

API ДОЛЖЕН (SHALL) применять surface-aware RBAC:
- `template` surface: доступ по template permissions (view/manage, включая object-level),
- `action_catalog` surface: staff-only.

#### Scenario: Пользователь с template view видит только template exposures
- **GIVEN** пользователь не staff, но имеет право просмотра templates
- **WHEN** вызывает list exposures для `surface=template`
- **THEN** API возвращает доступные template exposures
- **AND** не раскрывает `action_catalog` exposures

#### Scenario: Non-staff не может управлять action_catalog surface
- **WHEN** non-staff вызывает upsert/publish/list для `surface=action_catalog`
- **THEN** API возвращает `403 Forbidden`
- **AND** состояние action exposures не изменяется

#### Scenario: Пользователь с template manage может изменить template exposure
- **GIVEN** пользователь имеет `templates.manage_operation_template`
- **WHEN** вызывает upsert/publish для `surface=template`
- **THEN** API применяет изменение в unified store
- **AND** валидация выполняется по unified exposure contract
