## MODIFIED Requirements
### Requirement: Staff-only UI редактор каталога действий
Система ДОЛЖНА (SHALL) предоставлять staff-only редактирование action exposures внутри общего реестра `/templates`, без отдельного page-level flow для action catalog.

Редактирование action exposures ДОЛЖНО (SHALL) использовать тот же list+editor shell, что и templates, включая единый modal editor.

#### Scenario: Staff редактирует action exposure из mixed-surface списка
- **GIVEN** staff пользователь открыл `/templates` с `surface=all`
- **WHEN** выбирает строку action exposure и нажимает Edit
- **THEN** открывается тот же `OperationExposureEditorModal`
- **AND** применяются action-specific поля/валидация внутри общего editor shell

#### Scenario: Staff создаёт action из общего реестра
- **GIVEN** staff пользователь работает в `/templates`
- **WHEN** запускает create flow из общего toolbar
- **THEN** create выполняется в едином editor shell
- **AND** создаётся exposure surface `action_catalog` без перехода на отдельную страницу

#### Scenario: Non-staff не получает action editing controls в unified list
- **WHEN** non-staff пользователь открывает `/templates`
- **THEN** UI не показывает action create/edit controls
- **AND** action editor flow остаётся недоступным
