# Delta: ui-action-catalog-editor

## MODIFIED Requirements
### Requirement: Поддержка executor kinds
Система ДОЛЖНА (SHALL) поддерживать в редакторе executor kinds `ibcmd_cli`, `designer_cli` и `workflow`.

#### Scenario: ibcmd_cli выбирается из driver catalog и поддерживает connection override
- **WHEN** staff создаёт/редактирует действие с executor `ibcmd_cli`
- **THEN** UI позволяет выбрать `driver` и `command_id` из доступного driver catalog и сохранить конфигурацию
- **AND** UI позволяет настроить `executor.connection` (минимум `connection.remote`, `connection.pid`, `connection.offline.*`)
- **AND** UI не позволяет вводить/сохранять DBMS секреты (например `connection.offline.db_user/db_pwd`)

#### Scenario: workflow выбирается из списка workflow templates
- **WHEN** staff создаёт/редактирует действие с executor `workflow`
- **THEN** UI позволяет выбрать `workflow_id` из списка доступных workflow templates и сохранить конфигурацию

#### Scenario: designer_cli редактируется как CLI command
- **WHEN** staff создаёт/редактирует действие с executor `designer_cli`
- **THEN** UI позволяет задать команду/аргументы и сохранить конфигурацию

## ADDED Requirements
### Requirement: Preview и ошибки `ibcmd_cli` согласованы с Operations
Система ДОЛЖНА (SHALL) показывать ошибки preview для `executor.kind=ibcmd_cli` в user-friendly виде, согласованном с UX запуска `ibcmd` в мастере операций.

#### Scenario: OFFLINE_DB_METADATA_NOT_CONFIGURED отображается с инструкцией
- **GIVEN** staff нажимает Preview для action с `executor.kind=ibcmd_cli`
- **AND** backend возвращает `HTTP 400` с `error.code=OFFLINE_DB_METADATA_NOT_CONFIGURED`
- **WHEN** UI отображает ошибку
- **THEN** UI показывает actionable подсказку, где исправить проблему (минимум: `/databases` и `connection.offline.*`)

