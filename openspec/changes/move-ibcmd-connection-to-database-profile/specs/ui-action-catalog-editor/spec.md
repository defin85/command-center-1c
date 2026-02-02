# Delta: ui-action-catalog-editor

## MODIFIED Requirements

### Requirement: Поддержка executor kinds
Система ДОЛЖНА (SHALL) поддерживать в редакторе executor kinds `ibcmd_cli`, `designer_cli` и `workflow`.

#### Scenario: ibcmd_cli выбирается из driver catalog и не содержит connection на уровне action
- **WHEN** staff создаёт/редактирует действие с executor `ibcmd_cli`
- **THEN** UI позволяет выбрать `driver` и `command_id` из доступного driver catalog и сохранить конфигурацию
- **AND** UI НЕ позволяет задавать `executor.connection` в action (connection резолвится из профиля базы при запуске)

#### Scenario: workflow выбирается из списка workflow templates
- **WHEN** staff создаёт/редактирует действие с executor `workflow`
- **THEN** UI позволяет выбрать `workflow_id` из списка доступных workflow templates и сохранить конфигурацию

#### Scenario: designer_cli редактируется как CLI command
- **WHEN** staff создаёт/редактирует действие с executor `designer_cli`
- **THEN** UI позволяет задать команду/аргументы и сохранить конфигурацию

## ADDED Requirements

### Requirement: Preview для `ibcmd_cli` требует выбранные таргеты (или базу-пример)
Система ДОЛЖНА (SHALL) делать preview execution plan для `ibcmd_cli` с учётом effective connection, который зависит от профиля выбранных баз.

#### Scenario: Preview без таргетов не считается достоверным
- **GIVEN** staff открывает редактор action catalog
- **AND** выбран action `executor.kind=ibcmd_cli`
- **WHEN** staff пытается сделать Preview без указания базы/таргетов
- **THEN** UI сообщает, что для Preview нужно выбрать базу (или набор баз), так как connection резолвится per database

