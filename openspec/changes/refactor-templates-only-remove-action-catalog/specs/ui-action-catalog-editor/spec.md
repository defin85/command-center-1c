## ADDED Requirements
### Requirement: UI Action Catalog editor MUST быть decommissioned
Система НЕ ДОЛЖНА (SHALL NOT) предоставлять UI flow редактирования `action_catalog`.

Единый editor shell ДОЛЖЕН (SHALL) использоваться только для templates.

#### Scenario: Legacy route/режим action editor недоступен
- **WHEN** staff открывает legacy deep-link `/templates?surface=action_catalog`
- **THEN** UI не открывает action editor режим
- **AND** пользователь переводится в templates-only flow

#### Scenario: В `/templates` отсутствуют controls создания/редактирования actions
- **WHEN** staff открывает `/templates`
- **THEN** UI не показывает `New Action` и action-specific controls
- **AND** доступны только template editor controls

## REMOVED Requirements
### Requirement: Staff-only UI редактор каталога действий
**Reason**: action editor decommissioned.
**Migration**: использовать templates-only editor shell.

### Requirement: Guided editor + Raw JSON toggle
**Reason**: относится к удалённому action-catalog editor flow.
**Migration**: аналогичное поведение (где нужно) поддерживается в templates editor.

### Requirement: Поддержка executor kinds
**Reason**: requirement был определён для action editor capability.
**Migration**: executor support фиксируется в template editor и backend template contracts.

### Requirement: Save с серверной валидацией и отображением ошибок
**Reason**: action-specific save flow удаляется.
**Migration**: server validation остаётся в templates save flow.

### Requirement: Preview execution plan в редакторе action catalog
**Reason**: action editor decommissioned.
**Migration**: preview доступен в template-based manual execution flow.

### Requirement: Preview и ошибки `ibcmd_cli` согласованы с Operations
**Reason**: action editor decommissioned.
**Migration**: требования применяются к template-based execution UX.

### Requirement: Preview для `ibcmd_cli` требует выбранные таргеты (или базу-пример)
**Reason**: action editor decommissioned.
**Migration**: preview правила применяются в template-based manual flow.

### Requirement: Safe params template UX в Action Catalog
**Reason**: action-catalog редактор удаляется.
**Migration**: schema-driven params UX остаётся в templates editor.

### Requirement: Guided/Raw JSON редактор params в Action Catalog
**Reason**: action editor decommissioned.
**Migration**: guided/raw params остаются в templates editor.

### Requirement: Staff-only endpoint для Action Catalog editor hints
**Reason**: endpoint contract для action-catalog editor деcommissioned.
**Migration**: hints endpoint поддерживается только для templates editor сценариев (при необходимости).

### Requirement: Editor MUST записывать action exposures в unified persistent store
**Reason**: action exposure contract удалён.
**Migration**: editor записывает только template exposures.

### Requirement: Editor MUST использовать shared command-config contract с Templates UI
**Reason**: упоминание surfaces `template` + `action_catalog` больше неактуально.
**Migration**: shared contract применяется только к templates flow.

### Requirement: Editor hints MUST включать `target_binding` schema для `extensions.set_flags`
**Reason**: action-specific hints contract удаляется.
**Migration**: binding validation переносится в template compatibility checks.

### Requirement: Editor MUST показывать migration/validation diagnostics для unified exposure
**Reason**: action-catalog migration diagnostics больше не требуются для UI editor capability.
**Migration**: diagnostics остаются в template management/error reporting.

### Requirement: Target binding для `extensions.set_flags` MUST настраиваться в unified action editor
**Reason**: unified action editor удалён.
**Migration**: binding настраивается/валидируется в template-based модели.

### Requirement: Editor SHALL скрывать runtime-поля selective apply для `extensions.set_flags`
**Reason**: action editor удалён.
**Migration**: runtime selective state задаётся только при запуске template-based операции.

### Requirement: Editor SHALL показывать подсказку про runtime source `$flags.*`
**Reason**: действие относится к удалённому action editor flow.
**Migration**: helper text переносится в template/manual execution UI.
