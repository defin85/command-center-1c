# Delta: command-schemas-driver-options

## ADDED Requirements

### Requirement: `connection` может резолвиться per-target из профиля базы
Система ДОЛЖНА (SHALL) поддерживать для `scope=per_database` резолв driver-level connection параметров `ibcmd` per target database из профиля подключения базы.

Система ДОЛЖНА (SHALL) поддерживать минимум:
- `--remote=<url>` из профиля базы для remote режима,
- offline пути (`connection.offline.config`, `connection.offline.data`, `connection.offline.db_path`) и offline DBMS metadata (`dbms/db_server/db_name`) из профиля базы для offline режима.

Система ДОЛЖНА (SHALL) отражать происхождение значений в `bindings[]`/provenance, указывая источник `database` и стадию резолва (`resolve_at=worker` для per-target), без раскрытия секретов.

#### Scenario: Remote URL берётся из профиля базы per target
- **GIVEN** `scope=per_database` и выбраны N баз
- **AND** часть баз имеет `mode=remote` и `remote_url` в профиле подключения
- **WHEN** система формирует план/argv для исполнения
- **THEN** для соответствующих таргетов `--remote=<url>` берётся из профиля их базы
- **AND** provenance отмечает источник как `database` и `resolve_at=worker`

#### Scenario: Offline пути берутся из профиля базы и дополняются per-target metadata
- **GIVEN** `scope=per_database` и выбраны N баз
- **AND** база имеет offline профиль с `offline.config` и `offline.data`
- **WHEN** система формирует план/argv
- **THEN** offline пути берутся из профиля базы
- **AND** offline DBMS metadata могут быть дополнены per-target `Database.metadata` (если часть ключей не задана в профиле)

