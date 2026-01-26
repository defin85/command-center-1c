## ADDED Requirements
### Requirement: Binding Provenance отражает per-target резолв DBMS connection и creds
Система ДОЛЖНА (SHALL) отражать в `bindings[]` (Binding Provenance) для `ibcmd_cli`:
- что `connection.offline.db_name` и другие offline‑параметры резолвятся per target database;
- что DBMS creds резолвятся через credential mapping;
- что секретные значения не раскрываются.

#### Scenario: bindings показывают источники per-target резолва
- **GIVEN** операция `ibcmd_cli` `scope=per_database` с N таргетами
- **WHEN** система строит execution plan и bindings
- **THEN** bindings содержат записи со `source_ref` вида `target_db.metadata.*` (или эквивалентно)
- **AND** bindings содержат запись `credentials.db_user_mapping` (или эквивалентно) для DBMS creds
- **AND** такие bindings имеют `sensitive=true` и не содержат raw значений секретов

