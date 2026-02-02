# Change: Refactor IBCMD connection profile v2 (raw flags, breaking)

## Why
Текущий `IBCMD connection profile` на уровне базы содержит “семантику” (`mode`, `remote_url`) и одновременно используется как источник derived connection для `ibcmd_cli`. На практике флаги `ibcmd/ibsrv` являются плоскими и равнозначными, а попытка вывести режим из структуры приводит к неоднозначностям (например, пересечение file/DBMS сценариев) и неверной терминологии (`remote` как HTTP вместо SSH).

Нужно сделать профиль “как есть”: хранить набор connection‑параметров без интерпретации и переложить ответственность за корректные комбинации на пользователя, сохранив при этом безопасность (без секретов) и fail-closed поведение для derived запуска (если профиль отсутствует/пустой).

## Goals
- Сделать `IBCMD connection profile` на уровне базы “raw flags”:
  - **BREAKING**: заменить `remote_url` на `remote` и валидировать строго `ssh://...`.
  - Убрать `mode` (никакой семантики `auto/remote/offline`).
  - Оставить `pid` в профиле.
  - Разрешить и хранить любые `offline.*` ключи из driver schema (кроме секретов).
  - Разрешить хранить пустой профиль (но derived запуск без override остаётся fail-closed).
- Сохранить инварианты:
  - Профиль НЕ хранит секреты (DBMS/IB пароли).
  - Для `scope=per_database` и derived connection: если у части баз профиль отсутствует или пустой → 400 `IBCMD_CONNECTION_PROFILE_INVALID` до enqueue.

## Non-goals
- Не вводить “универсальный профиль для любого драйвера” в этом change (это отдельная задача, когда появится второй драйвер с реальной потребностью).
- Не добавлять “умную” семантику/валидацию комбинаций флагов (remote+pid+offline, db_path vs dbms и т.д.) — ответственность на пользователе.
- Не менять семантику DBMS/IB credential mapping: секреты остаются вне профиля.
- Не использовать `Database.dbms/db_server/db_name` как fallback для `ibcmd` connection (v2 полностью self-contained для `ibcmd`).

## What changes
- **Contracts/OpenAPI**:
  - **BREAKING**: обновить `Database.ibcmd_connection` и payload `update-ibcmd-connection-profile` под v2 raw flags:
    - `remote` (ssh url), `pid`, `offline` (dict), `reset`.
    - удалить `mode` и `remote_url`.
- **Orchestrator**:
  - endpoint `POST /api/v2/databases/update-ibcmd-connection-profile/` принимает v2 payload, сохраняет в `Database.metadata.ibcmd_connection`, запрещает секреты, валидирует `remote` как `ssh://...`.
  - `execute-ibcmd-cli` derived-mode: отсутствие/пустота профиля у части баз → `IBCMD_CONNECTION_PROFILE_INVALID` (как сейчас), но критерий “пустой” обновить на v2.
- **Frontend**:
  - `/databases`: UI редактирования профиля обновить под v2 (remote ssh url, pid, offline.* без mode).
  - Operations/DriverCommandBuilder: derived summary+diff и тексты обновить под v2 поля (без `mode/remote_url`).
  - DBMS metadata UI остаётся отдельным, но `ibcmd` v2 перестаёт использовать DBMS metadata как fallback.

## Migration
- Требуется миграция данных `Database.metadata.ibcmd_connection`:
  - перенос `remote_url` → `remote` (строго `ssh://...`; некорректные значения помечаются как невалидные и требуют ручного исправления),
  - `mode` удаляется,
  - `offline` переносится как есть (с удалением запрещённых секретных ключей, если найдены).
  - DBMS metadata базы (`dbms/db_server/db_name`) не участвует в резолве `ibcmd` v2 и не мигрируется в профиль автоматически.

## Impact
- Затронутые спецификации: `database-connection-profiles`, `ui-driver-command-builder`.
- Затронутые компоненты: Orchestrator, Frontend, contracts/codegen.
- Риск: breaking change для клиентов и существующих данных профиля.
