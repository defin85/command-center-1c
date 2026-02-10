# ui-action-catalog-editor Specification

## Purpose
TBD - created by archiving change add-ui-action-catalog-editor. Update Purpose after archive.
## Requirements
### Requirement: UI Action Catalog editor MUST быть полностью decommissioned
Система НЕ ДОЛЖНА (SHALL NOT) предоставлять UI flow редактирования `action_catalog`.

#### Scenario: Legacy mode `/templates?surface=action_catalog` недоступен
- **WHEN** пользователь открывает legacy route
- **THEN** action editor не открывается
- **AND** UI остаётся в templates-only режиме

#### Scenario: UI не показывает controls action editor
- **WHEN** пользователь открывает `/templates`
- **THEN** controls `New Action` и action-specific редактирование отсутствуют
- **AND** доступен только template editor flow

