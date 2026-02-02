# Design: Database connection profile для `ibcmd` (remote/offline) и удаление `executor.connection` из actions

## Контекст
`ibcmd` поддерживает разные способы подключения/исполнения, включая:
- `--remote=<url>` (ssh-gateway / remote standalone admin),
- `connection.offline.*` (offline режим, зависящий от путей и DBMS metadata),
- `--pid` (локальный процесс; сейчас не используется).

Action Catalog actions должны быть универсальными: “что выполнить”, а не “как подключаться к каждой базе”.
Режим подключения является свойством конкретной базы и её окружения, поэтому профиль подключения логичнее хранить per Database и переиспользовать везде.

## Цели
- Единый источник истины “как подключаться к этой базе” для `ibcmd`.
- Поддержка bulk сценариев, где разные базы могут быть в разных режимах (`remote`/`offline`) в рамках одного запуска.
- Per-run override (на уровне Operations UI) для “одноразовых” запусков, без изменения профиля базы.
- Удаление `executor.connection` из `ui.action_catalog` без миграции (actions не жалко пересоздать).

## Модель данных (MVP)
Храним в `Database.metadata` новый объект (название уточняется при реализации, пример):
```json
{
  "ibcmd_connection": {
    "mode": "auto|remote|offline",
    "remote_url": "ssh://host:port",
    "offline": {
      "config": "/path/to/config",
      "data": "/path/to/data",
      "dbms": "PostgreSQL",
      "db_server": "db-host:5432",
      "db_name": "infobase_db",
      "db_path": "/path/to/file-ib" // опционально
    }
  }
}
```

Принципы:
- **Секретов нет**: не храним `db_user/db_pwd` и IB пароли. Они резолвятся через mappings/secret store.
- `mode=auto` допускается (по умолчанию) и означает “выбрать лучший доступный режим для этой базы”.
- `pid` не является частью профиля базы.

## Резолв effective connection
### Входы
- Per-run override (из Operations UI) — применяется ко всем выбранным таргетам и имеет приоритет.
- Профиль подключения базы — per target.
- (Опционально) дефолты системы (например `mode=auto`).

### Выход
Для `scope=per_database` получаем **per-target effective connection**, который используется при формировании argv/preview и при исполнении.

Поддержка mixed mode:
- один запуск может включать базы в `remote` и `offline`;
- план/preview должен явно показывать, что connection может отличаться per target.

## API/контракты (MVP)
### Управление профилем подключения
Добавить API v2 endpoint для установки/сброса `ibcmd_connection`:
- RBAC: `databases.manage_database` (per database).
- Tenant scoped.
- Аудит: логировать факт обновления, без секретов.

### Execute / Preview
Изменить `execute-ibcmd-cli` и preview так, чтобы:
- для `scope=per_database` connection мог быть получен из per-target профилей баз, даже если в запросе нет явного `connection.*`;
- в случае отсутствующего/неполного профиля для части баз API fail-closed и возвращает 400 с машиночитаемым `error.code` и `details.missing[]` (список проблемных баз и что именно отсутствует).

## UI (MVP)
- `/databases`: единая модалка “Ibcmd connection”:
  - `mode` (auto/remote/offline),
  - `remote_url`,
  - offline: `config/data/dbms/db_server/db_name/db_path` (без секретов),
  - reset.
- Operations (`DriverCommandBuilder` / wizard):
  - по умолчанию показывает derived connection (из профилей выбранных баз),
  - позволяет включить override (remote/offline) для “одноразового” запуска,
  - при mixed mode показывает суммарно и/или предупреждение “параметры отличаются per target”.
- Action Catalog editor:
  - полностью убрать `executor.connection` из guided режима и валидации draft,
  - preview для `ibcmd_cli` требует выбрать таргеты (или одну базу-пример), иначе связь/валидация будет неполной.

## Совместимость и миграция
- `executor.connection` в `ui.action_catalog` удаляем как поддерживаемое поле (без миграции).
- Если сохранённые действия содержали `executor.connection`, они должны быть пересозданы/исправлены вручную (согласно решению “action не жалко”).

## Риски
- **Окружение путей offline**: `offline.config/data` зависят от runtime окружения (где исполняется worker). В MVP считаем, что они валидны для текущего execution environment; если появятся несколько пулов воркеров, понадобится “profile per execution_context”.
- **Preview без таргетов**: без выбора баз невозможно корректно показать effective connection. Нужен явный UX (выберите базу/таргеты для preview).
- **Конфликты с additional_args**: если в additional_args заданы `--remote`/offline флаги, конфликтуем с derived connection (fail closed).

