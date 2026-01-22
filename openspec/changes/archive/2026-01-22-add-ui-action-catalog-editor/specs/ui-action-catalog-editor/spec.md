## ADDED Requirements

### Requirement: Staff-only UI редактор каталога действий
Система ДОЛЖНА (SHALL) предоставить staff-only UI для просмотра и редактирования `ui.action_catalog`.

#### Scenario: Non-staff не имеет доступа
- **WHEN** non-staff пользователь открывает страницу редактора
- **THEN** доступ запрещён (403/redirect) и данные каталога не раскрываются

#### Scenario: Staff видит текущую конфигурацию
- **WHEN** staff пользователь открывает страницу редактора
- **THEN** UI загружает текущий `ui.action_catalog` и отображает actions

### Requirement: Guided editor + Raw JSON toggle
Система ДОЛЖНА (SHALL) поддерживать два режима редактирования: guided UI и Raw JSON, с возможностью переключения.

#### Scenario: Переключение режимов
- **WHEN** staff пользователь переключает guided ↔ raw
- **THEN** изменения сохраняются в рамках текущей сессии редактирования и не теряются без явного Save

### Requirement: Поддержка executor kinds
Система ДОЛЖНА (SHALL) поддерживать в редакторе executor kinds `ibcmd_cli`, `designer_cli` и `workflow`.

#### Scenario: ibcmd_cli выбирается из driver catalog
- **WHEN** staff создаёт/редактирует действие с executor `ibcmd_cli`
- **THEN** UI позволяет выбрать `driver` и `command_id` из доступного driver catalog и сохранить конфигурацию

#### Scenario: workflow выбирается из списка workflow templates
- **WHEN** staff создаёт/редактирует действие с executor `workflow`
- **THEN** UI позволяет выбрать `workflow_id` из списка доступных workflow templates и сохранить конфигурацию

#### Scenario: designer_cli редактируется как CLI command
- **WHEN** staff создаёт/редактирует действие с executor `designer_cli`
- **THEN** UI позволяет задать команду/аргументы и сохранить конфигурацию

### Requirement: Save с серверной валидацией и отображением ошибок
Система ДОЛЖНА (SHALL) сохранять изменения через backend и показывать ошибки валидации пользователю.

#### Scenario: Ошибка валидации отображается с путём
- **WHEN** staff сохраняет невалидный action catalog
- **THEN** UI показывает список ошибок, включая пути вида `extensions.actions[i]...`, чтобы пользователь мог исправить конфигурацию

#### Scenario: Успешное сохранение
- **WHEN** staff сохраняет валидный action catalog
- **THEN** UI подтверждает успешное сохранение и отображает актуальную сохранённую версию

