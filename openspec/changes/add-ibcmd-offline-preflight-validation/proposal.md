# Change: Preflight-валидация offline-подключения для `ibcmd_cli`

## Why
Сейчас операции `ibcmd_cli` в режиме `connection.offline` могут быть успешно поставлены в очередь, но затем быстро падать на worker с ошибками вида:
- отсутствуют DBMS метаданные для подключения (`dbms/db_server/db_name`), или
- отсутствуют нужные credential mappings для DBMS/ИБ.

Это приводит к плохому UX и лишней нагрузке:
- пользователь видит `QUEUED`/`PROCESSING`, а ошибка приходит поздно;
- тратится очередь/время на заведомо невыполнимую операцию;
- ошибку трудно интерпретировать (особенно когда часть параметров должна резолвиться “per target”).

Нужно fail-fast на стороне API Gateway/Orchestrator: до enqueue в Redis проверять, что для выбранных таргетов offline-подключение разрешимо без раскрытия секретов, и возвращать понятную, “починяемую” ошибку.

## What Changes
- Добавить preflight-валидацию для `ibcmd_cli` (MVP: `scope=per_database`):
  - если выбран `connection.offline` (и не задан `connection.remote`, `connection.pid`, `offline.db_path`),
    система проверяет, что DBMS метаданные (`dbms/db_server/db_name`) могут быть получены из комбинации:
    - request-level `connection.offline.*` (если задано),
    - per-target `Database.metadata.*`.
  - при невозможности резолва возвращает 400 с машиночитаемым `error.code` и списком проблемных таргетов (без секретов).
- UI: `DriverCommandBuilder` и экран запуска операции показывают эту ошибку как actionable:
  - подсказка “что исправить” (DBMS metadata vs mappings),
  - список баз (ограниченный) и недостающих полей.
- Добавить API + UI для управления DBMS metadata базы (минимум: `dbms`, `db_server`, `db_name`):
  - API обновления/сброса DBMS metadata для конкретной базы (RBAC: `databases.manage_database`).
  - UI-форма редактирования DBMS metadata на экране `/databases` (доступна только при праве MANAGE на базу).

## Impact
- Затронутые спеки: `command-schemas-driver-options`, `ui-driver-command-builder`, `database-dbms-metadata` (new)
- Затронутый код (план): Orchestrator API v2 `execute_ibcmd_cli` + Frontend обработка ошибок.
- Ломающих изменений нет: меняется только поведение валидации (раньше падало на worker, теперь будет отказ до enqueue).

## Non-Goals
- Не меняем семантику worker инъекции DBMS/ИБ аргументов и источники секретов.
- Не делаем общий фреймворк “preflight validation для любых драйверов” (только `ibcmd_cli` как MVP).
- Не делаем автоматический импорт DBMS metadata из RAS/кластера (остаётся как сейчас; данный change добавляет ручное управление).
