# Delta: ui-driver-command-builder

## ADDED Requirements

### Requirement: Derived connection показывает summary+diff для `ibcmd` per_database
Система ДОЛЖНА (SHALL) в UI `DriverCommandBuilder` для `driver=ibcmd` и `scope=per_database`, когда override connection отключён, показывать:
- аггрегированную сводку derived connection (counts по effective mode, mixed mode);
- diff по ключам connection, которые отличаются между выбранными базами.

UI НЕ ДОЛЖЕН (SHALL NOT) отображать или запрашивать секреты (пароли и т.п.) в этой сводке/diff.

#### Scenario: Mixed mode отображается как сводка и diff
- **GIVEN** выбрано несколько баз, часть с `mode=remote`, часть с `mode=offline`
- **WHEN** пользователь открывает Configure/Driver options для `ibcmd` per_database без override
- **THEN** UI показывает сводку (remote_count/offline_count, mixed_mode=true)
- **AND** UI показывает diff по ключам, где значения отличаются между таргетами (например `remote_url`, `offline.config`, `offline.data`, `offline.db_name`)

#### Scenario: Все таргеты remote с одинаковым URL не создают “лишний diff”
- **GIVEN** выбрано N баз с effective mode `remote` и одинаковым `remote_url`
- **WHEN** UI показывает derived connection
- **THEN** UI показывает summary
- **AND** diff не содержит строку `remote_url` как отличающийся ключ

