## ADDED Requirements
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

## REMOVED Requirements
### Requirement: Staff-only UI редактор каталога действий
**Reason**: capability decommissioned.
**Migration**: templates-only editor.

### Requirement: Guided editor + Raw JSON toggle
**Reason**: относится к action-catalog editor flow.
**Migration**: поведение сохраняется/развивается в templates editor.

### Requirement: Поддержка executor kinds
**Reason**: action editor удалён.
**Migration**: executor kinds поддерживаются в templates editor.

### Requirement: Save с серверной валидацией и отображением ошибок
**Reason**: action save flow удалён.
**Migration**: server validation остаётся в templates flow.

### Requirement: Preview execution plan в редакторе action catalog
**Reason**: action editor удалён.
**Migration**: preview в manual operations/templates execution flow.

### Requirement: Preview и ошибки `ibcmd_cli` согласованы с Operations
**Reason**: action editor удалён.
**Migration**: перенос в manual operations UI.

### Requirement: Preview для `ibcmd_cli` требует выбранные таргеты (или базу-пример)
**Reason**: action editor удалён.
**Migration**: сохраняется в manual operations preview flow.

### Requirement: Safe params template UX в Action Catalog
**Reason**: action editor удалён.
**Migration**: schema-driven UX в templates editor.

### Requirement: Guided/Raw JSON редактор params в Action Catalog
**Reason**: action editor удалён.
**Migration**: guided/raw params в templates editor.

### Requirement: Staff-only endpoint для Action Catalog editor hints
**Reason**: action-catalog editor contract удалён.
**Migration**: hints используются только templates editor (если требуется).

### Requirement: Editor MUST записывать action exposures в unified persistent store
**Reason**: action exposures удалены.
**Migration**: editor пишет только templates.

### Requirement: Editor MUST использовать shared command-config contract с Templates UI
**Reason**: упоминание двух surfaces неактуально.
**Migration**: shared contract остаётся templates-only.

### Requirement: Editor hints MUST включать `target_binding` schema для `extensions.set_flags`
**Reason**: action hints удаляются.
**Migration**: binding validation в template compatibility.

### Requirement: Editor MUST показывать migration/validation diagnostics для unified exposure
**Reason**: action-catalog diagnostics неактуальны.
**Migration**: diagnostics в templates flow.

### Requirement: Target binding для `extensions.set_flags` MUST настраиваться в unified action editor
**Reason**: action editor удалён.
**Migration**: binding хранится/валидируется в templates contract.

### Requirement: Editor SHALL скрывать runtime-поля selective apply для `extensions.set_flags`
**Reason**: action editor удалён.
**Migration**: runtime selective state задаётся при запуске manual operation.

### Requirement: Editor SHALL показывать подсказку про runtime source `$flags.*`
**Reason**: привязка к action editor удалена.
**Migration**: helper text в manual operation launch UI.
