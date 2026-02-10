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

## ADDED Requirements
### Requirement: Target binding для `extensions.set_flags` MUST настраиваться в unified action editor
Система ДОЛЖНА (SHALL) настраивать `target_binding.extension_name_param` в staff-only action editor внутри `/templates` как capability-specific поле action exposure.

Для `capability="extensions.set_flags"` UI ДОЛЖЕН (SHALL) показывать selector по параметрам выбранного `command_id` (из `params_by_name` схемы команды), а не требовать только свободный ввод строки.

#### Scenario: Staff выбирает target-параметр из схемы команды
- **GIVEN** staff редактирует action `extensions.set_flags` в `/templates`
- **AND** выбран `command_id` с доступной схемой `params_by_name`
- **WHEN** открывает capability-specific binding поле
- **THEN** UI показывает selector доступных command params
- **AND** выбранное значение записывается в `target_binding.extension_name_param`

#### Scenario: Binding остаётся частью action editor, а не command-schemas
- **WHEN** staff настраивает target binding для `extensions.set_flags`
- **THEN** настройка выполняется в modal editor action exposure внутри `/templates`
- **AND** `command-schemas` экран не используется как место хранения/редактирования binding
