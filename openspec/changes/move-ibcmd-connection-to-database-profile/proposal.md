# Change: Перенести `ibcmd` connection на уровень базы (Database connection profile)

## Why
Сейчас в проекте одновременно существуют несколько мест, где пытаются задавать `connection.*` для `ibcmd_cli`:
- мастер операций (Operations) — на уровне запуска;
- action catalog (`ui.action_catalog`) — на уровне action (что делает action менее “универсальным” между базами);
- частично — per-target metadata базы (`Database.metadata.dbms/db_server/db_name`) и credential mappings.

Это приводит к проблемам:
- action перестаёт быть переносимым между базами (а должен быть “шаблоном намерения”);
- логика подключения дублируется в UI/валидации/preview и расходится между экранами;
- для bulk сценариев по N базам нет единого источника истины “как подключаться к конкретной базе”.

## What Changes
1) **Ввести профиль подключения `ibcmd` на уровне базы** (per database):
   - поддерживаемые режимы: `remote` (через `--remote=<url>`) и `offline` (через `connection.offline.*`);
   - `offline` хранит также пути `offline.config/offline.data/...`, чтобы offline был самодостаточен без Configure;
   - профиль не хранит секреты (DBMS/IB креды всегда резолвятся через mappings/secret store).

2) **Единый резолв “effective connection” для всех сценариев запуска**:
   - per-run override (Operations UI) имеет приоритет над профилем базы;
   - если override не задан, берётся профиль базы;
   - поддерживается mixed mode: в одной bulk операции разные базы могут использовать разные режимы (`remote`/`offline`) по своим профилям.

3) **Удалить `executor.connection` из `ui.action_catalog`**:
   - actions содержат только `driver/command_id/params` и остаются универсальными между базами;
   - все места запуска (Operations, Extensions actions, Action Catalog Preview) используют connection из профиля базы (или per-run override).

4) **Preview и ошибки**:
   - preview для `ibcmd_cli` становится привязанным к выбранным таргетам (или “примерной базе”), иначе невозможно корректно оценить effective connection;
   - ошибки типа `OFFLINE_DB_METADATA_NOT_CONFIGURED` и “отсутствует профиль подключения” отображаются как actionable (куда идти чинить).

## Impact
- Затрагиваемые подсистемы: Orchestrator API v2 (databases + execute-ibcmd-cli + preview), Worker (пер-target argv), Frontend (Operations, /databases, Extensions, Action Catalog editor).
- Затрагиваемые спеки: `extensions-action-catalog`, `ui-action-catalog-editor`, `ui-driver-command-builder`, `command-schemas-driver-options`.
- Изменение контракта: action catalog больше не поддерживает `executor.connection` (осознанно; миграция не требуется — action можно пересоздать).

## Non-goals
- Не вводим поддержку `connection.pid` как часть профиля базы (PID нестабилен; остаётся только как отладочный per-run override при необходимости).
- Не строим общий фреймворк профилей подключения для всех драйверов (MVP только для `ibcmd`).
- Не добавляем хранение секретов в профиле подключения базы.

