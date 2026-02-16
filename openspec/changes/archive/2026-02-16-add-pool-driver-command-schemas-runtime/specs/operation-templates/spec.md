## ADDED Requirements
### Requirement: Template editor MUST поддерживать executor kind `pool_driver`
Система ДОЛЖНА (SHALL) поддерживать в templates editor executor kind `pool_driver` с выбором `driver=pool`, `command_id` и schema-driven параметров.

#### Scenario: Пользователь создаёт template для pool distribution command
- **GIVEN** в catalog доступен `driver=pool` и `command_id=distribution_calculation.top_down`
- **WHEN** пользователь создаёт template в `/templates`
- **THEN** editor валидирует форму по pool command schema
- **AND** template сохраняется с `executor_kind=pool_driver`

### Requirement: Pool runtime templates MUST управляться через стандартный template lifecycle
Система ДОЛЖНА (SHALL) применять к `pool_driver` templates стандартный lifecycle (`draft -> validate -> publish -> active`) и стандартный RBAC templates management.

#### Scenario: Публикация pool_driver template следует общему lifecycle
- **GIVEN** template с `executor_kind=pool_driver` находится в draft
- **WHEN** оператор выполняет validate/publish
- **THEN** система применяет те же policy и проверки, что и для других template executor kinds
- **AND** published template становится доступным для runtime resolve
