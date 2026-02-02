# Delta: command-schemas-driver-options

## ADDED Requirements

### Requirement: Preview provenance отражает fallback источники DBMS metadata
Система ДОЛЖНА (SHALL) в staff-only preview execution plan (`/api/v2/ui/execution-plan/preview/`) отражать в `bindings[]`/provenance источники значений для offline DBMS metadata (`dbms`, `db_server`, `db_name`) таким образом, чтобы было видно:
- значения могут приходить из `Database.metadata.ibcmd_connection.offline.*` (профиль подключения),
- либо из `Database.metadata.{dbms,db_server,db_name}` (fallback).

#### Scenario: Offline профиль без DBMS triplet показывает fallback источники
- **GIVEN** executor `ibcmd_cli`, `scope=per_database`
- **AND** connection резолвится из профиля базы (derived mode)
- **AND** offline профиль содержит `config/data`, но не содержит `dbms/db_server/db_name`
- **WHEN** staff запускает preview
- **THEN** `bindings[]` содержит элементы provenance для `connection.offline.dbms/db_server/db_name` со `source_ref`, указывающим на fallback `target_db.metadata.{dbms,db_server,db_name}`

