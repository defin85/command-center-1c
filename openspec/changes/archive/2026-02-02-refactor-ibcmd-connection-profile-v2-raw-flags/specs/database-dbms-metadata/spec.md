## MODIFIED Requirements

### Requirement: Управление DBMS metadata базы (dbms/db_server/db_name)
Система ДОЛЖНА (SHALL) позволять вручную устанавливать и сбрасывать DBMS metadata для конкретной базы данных (инфобазы) в CommandCenter:
- `dbms`
- `db_server`
- `db_name`

DBMS metadata относится к базе и используется другими компонентами, где это требуется, но для `ibcmd` connection profile v2 (raw flags) система НЕ ДОЛЖНА (SHALL NOT) использовать DBMS metadata как fallback источник значений.

#### Scenario: IBCMD v2 не использует DBMS metadata как fallback
- **GIVEN** у базы заполнены `dbms/db_server/db_name`
- **AND** `ibcmd` connection profile v2 не содержит `offline.dbms/offline.db_server/offline.db_name`
- **WHEN** пользователь запускает `ibcmd_cli` в derived режиме без per-run override
- **THEN** система НЕ подставляет значения из DBMS metadata в offline flags
- **AND** поведение определяется только профилем и/или per-run override

