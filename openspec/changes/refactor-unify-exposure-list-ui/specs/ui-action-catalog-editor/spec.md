# Spec Delta: ui-action-catalog-editor

## MODIFIED Requirements
### Requirement: Staff-only UI редактор каталога действий
Система ДОЛЖНА (SHALL) предоставлять staff-only редактирование action exposures внутри `/templates` через тот же list+editor flow, что и template surface.

Отдельные page-level tabs/pages для action catalog НЕ ДОЛЖНЫ (SHALL NOT) использоваться как самостоятельный editor flow.

#### Scenario: Staff редактирует action exposure из общего списка
- **GIVEN** staff пользователь открыл `/templates` и выбрал `surface=action_catalog`
- **WHEN** открывает create/edit для action exposure
- **THEN** UI использует единый `OperationExposureEditorModal`
- **AND** применяет action-specific поля/валидацию внутри этого же editor shell

#### Scenario: Non-staff не получает action editing flow
- **WHEN** non-staff пользователь открывает `/templates`
- **THEN** action surface недоступен для выбора
- **AND** редактор action exposure не открывается
