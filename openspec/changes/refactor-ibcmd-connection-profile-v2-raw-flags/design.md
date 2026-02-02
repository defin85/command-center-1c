## Контекст
Сейчас профиль подключения `ibcmd` на уровне базы содержит `mode` и `remote_url`, что вводит скрытую семантику (`auto/remote/offline`) и мешает “плоской” модели флагов `ibcmd/ibsrv`. Также поле `remote_url` в UI/примерах может интерпретироваться как HTTP, тогда как `ibcmd --remote` предназначен для SSH URL.

Новая цель: сделать профиль “raw flags”: хранить connection параметры как есть и не пытаться выводить режим или тип инфобазы из структуры. Пользователь отвечает за корректные комбинации.

## Goals
- Профиль v2 хранит raw flags, близкие к driver schema:
  - `remote` (строго `ssh://...`),
  - `pid`,
  - `offline` (dict, любые ключи из схемы, без секретов).
- Разрешить пустой профиль (storage допускает), но derived запуск без override остаётся fail-closed.
- Сохранить запрет секретов в профиле (fail-closed).

## Non-goals
- Универсальный профиль для любого драйвера (вынести в отдельный change).
- Валидация совместимости комбинаций флагов (remote+pid+offline, db_path vs dbms и т.д.).

## Решение
### Схема профиля v2 (concept)
Профиль хранится в `Database.metadata.ibcmd_connection` как объект v2. Поля:
- `remote?: string` — SSH URL для `--remote=<url>`, принимается только `ssh://...`.
- `pid?: number` — значение `--pid=<pid>`.
- `offline?: object` — произвольный dict без секретов; ключи/значения трактуются как driver-level offline flags.

Пустой профиль допустим (все поля отсутствуют/пустые), но считается “непригодным” для derived запуска.

### Отношение к DBMS metadata базы
Для `ibcmd` connection profile v2 система НЕ использует `Database.dbms/db_server/db_name` как fallback источник значений для `offline.*`.
Если пользователю нужен offline DBMS сценарий, он обязан указать `offline.dbms/offline.db_server/offline.db_name` в профиле (или per-run override).

### Derived validation
Для `execute-ibcmd-cli` при `scope=per_database` и отсутствии per-run override:
- если профиль отсутствует или пустой у части таргетов → 400 `IBCMD_CONNECTION_PROFILE_INVALID` до enqueue;
- детали возвращаются через `error.details.missing[]` (без секретов).

### Миграция v1 → v2
Возможные варианты реализации:
1) one-time migration (предпочтительно для чистого breaking):
   - преобразовать все записи `metadata.ibcmd_connection` на v2;
   - `remote_url` → `remote` (требует соответствия `ssh://...`, иначе поле удаляется и требуется ручная настройка);
   - `mode` удалить;
   - `offline` перенести как есть, удалив секретные ключи при наличии.
2) on-read normalize + write-back (допустимо только как временная мера, если миграция данных слишком дорогая).

Выбор варианта фиксируется в реализации (см. tasks).

## UX заметки
- UI не пытается объяснить “режимы”, он показывает поля профиля как raw параметры.
- `remote` отображается явно как “SSH URL”.
- Derived summary/diff может работать как “визуализация заполненных полей” (не семантика).
