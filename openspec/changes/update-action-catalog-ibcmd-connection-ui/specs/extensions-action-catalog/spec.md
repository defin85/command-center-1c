# Delta: extensions-action-catalog

## MODIFIED Requirements
### Requirement: Action executors
Система ДОЛЖНА (SHALL) поддерживать action executors `ibcmd_cli`, `designer_cli` и `workflow` в action catalog.

#### Scenario: ibcmd_cli action маппится на execute-ibcmd-cli с connection override
- **GIVEN** действие использует executor `ibcmd_cli`
- **WHEN** пользователь запускает действие для одной или нескольких баз
- **THEN** действие выполняется через `POST /api/v2/operations/execute-ibcmd-cli/`
- **AND** если `executor.connection` задан, он маппится в поле `connection` запроса
- **AND** если `executor.connection` не задан, UI обеспечивает явный режим подключения для `per_database` команд (минимум `connection.offline = {}`), чтобы избежать `error.code=MISSING_CONNECTION`

## ADDED Requirements
### Requirement: User-friendly ошибки preflight для действий расширений
Система ДОЛЖНА (SHALL) показывать ошибки preflight `ibcmd_cli` при запуске действий расширений из UI в user-friendly виде, согласованном с мастером операций.

#### Scenario: OFFLINE_DB_METADATA_NOT_CONFIGURED отображается как actionable подсказка
- **GIVEN** пользователь запускает действие расширений с `executor.kind=ibcmd_cli` и `connection.offline`
- **AND** DBMS metadata для части таргетов не настроены
- **WHEN** backend возвращает `HTTP 400` с `error.code=OFFLINE_DB_METADATA_NOT_CONFIGURED`
- **THEN** UI показывает понятную инструкцию, что нужно заполнить DBMS metadata на `/databases` или задать override через `connection.offline.*`

