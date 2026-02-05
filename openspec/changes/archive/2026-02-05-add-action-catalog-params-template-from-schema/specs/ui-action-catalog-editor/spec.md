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

#### Scenario: UI предлагает params template из command schema при создании action
- **GIVEN** staff открывает modal создания нового action в guided editor
- **AND** выбран `executor.kind` из `{ibcmd_cli, designer_cli}`
- **WHEN** staff выбирает `driver` и `command_id` из driver catalog
- **THEN** UI показывает список параметров команды из schema (`params_by_name`) с признаками required/default
- **AND** UI предлагает “Insert params template” для заполнения `executor.params` объектом-шаблоном (ключи из `params_by_name`)
- **AND** auto-fill НЕ должен затирать уже введённый JSON в `params` без явного подтверждения пользователя

#### Scenario: params template не включает disabled и ibcmd connection params
- **GIVEN** выбран `driver=ibcmd` и `command_id`
- **WHEN** UI строит список параметров и template для `executor.params`
- **THEN** UI исключает параметры, помеченные как `disabled`
- **AND** UI исключает параметры, относящиеся к connection (которые должны приходить из профиля базы), чтобы не вводить оператора в заблуждение
