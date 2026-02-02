## ADDED Requirements

### Requirement: Preflight-валидация offline DBMS metadata для `ibcmd_cli`
Система ДОЛЖНА (SHALL) валидировать перед enqueue, что для `ibcmd_cli` в режиме `connection.offline` (не `remote`, не `pid`, не `db_path`) DBMS metadata подключения разрешима для каждого выбранного таргета.

DBMS metadata включает минимум:
- `dbms`
- `db_server`
- `db_name`

Система ДОЛЖНА (SHALL) резолвить эти значения как комбинацию:
- request-level `connection.offline.*` (если задано),
- per-target `Database.metadata.*`.

Если хотя бы для одного таргета значения неразрешимы, система ДОЛЖНА (SHALL) fail closed и НЕ создавать операцию.

#### Scenario: Отсутствуют DBMS metadata у части баз → отказ до enqueue
- **GIVEN** `scope=per_database`
- **AND** `connection.remote` и `connection.pid` не заданы
- **AND** `connection.offline.db_path` не задан
- **AND** выбраны N баз, у части из них отсутствуют `Database.metadata.dbms/db_server/db_name`
- **WHEN** пользователь запускает `ibcmd_cli`
- **THEN** API возвращает 400 с `error.code=OFFLINE_DB_METADATA_NOT_CONFIGURED`
- **AND** error details указывают проблемные базы и missing keys (без секретов)
- **AND** операция НЕ становится `queued`
- **AND** система предоставляет способ управления DBMS metadata (например отдельный API/UI для редактирования метаданных базы)

#### Scenario: request-level dbms/db_server + per-target db_name → запуск разрешён
- **GIVEN** `scope=per_database`
- **AND** `connection.offline.dbms` и `connection.offline.db_server` заданы в Configure
- **AND** `connection.offline.db_name` не задан
- **AND** каждая выбранная база имеет `Database.metadata.db_name`
- **WHEN** пользователь запускает `ibcmd_cli`
- **THEN** запрос валиден и операция может быть поставлена в очередь
