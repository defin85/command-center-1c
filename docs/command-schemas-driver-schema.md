# Driver schema + Command schema (MVP: `ibcmd`)

## Зачем это нужно
Для schema-driven драйверов (пока MVP только `ibcmd`) есть два разных класса входных параметров:

- **Driver-level connection options** — параметры подключения/контекста выполнения (`remote`, `pid`, `offline.*`).
- **Command-level params** — параметры конкретной команды (`params_by_name` у `commands_by_id.<command_id>`).

Если смешивать connection options с `params`, то команды без `params_by_name` начинают неожиданно падать с ошибкой вида
`params are not supported for this command`.

## Структура каталога (v2)
Каталог `DriverCatalogV2` расширен дополнительным (additive) полем:

- `driver_schema` — схема для driver-level connection options.
- `commands_by_id.<id>.params_by_name` — схема параметров команды (как было раньше).

Для `ibcmd` используется вложенная структура:

- `driver_schema.connection.remote`
- `driver_schema.connection.pid`
- `driver_schema.connection.offline.{config,data,dbms,db_server,db_name,db_user,db_pwd}`

## Как формируется канонический `argv[]`
Для `execute-ibcmd-cli` API формирует `argv[]` и `argv_masked[]` заранее (до постановки операции в очередь) в таком порядке:

1) `command.argv[]` (токены команды)
2) driver-level connection options (`connection.*`) — по `driver_schema`
3) command-level params (`params`) — по `commands_by_id.<id>.params_by_name`
4) `additional_args` (после нормализации/strip секретов)

## Контракт `execute-ibcmd-cli`
Запрос принимает три независимых блока:

- `connection` — **только** driver-level connection options
- `params` — **только** параметры команды
- `additional_args` — «сырые» дополнительные аргументы

## Политика конфликтов (строго: error)
Чтобы избежать неоднозначностей и не терять воспроизводимость:

- Если один и тот же driver-level флаг задан и в `connection`, и в `additional_args` — это **ошибка** (`VALIDATION_ERROR`).
- `--pid` (и алиас `-p`) запрещён в `additional_args` — нужно использовать `connection.pid` (`PID_IN_ARGS_NOT_ALLOWED`).
- Если `connection` задан и одновременно те же driver-level ключи присутствуют в `params` (например `remote`, `db_user`) — это **ошибка** (`VALIDATION_ERROR`), чтобы исключить «тихие» конфликты.

## Где это редактировать
UI “Command Schemas” (guided) содержит отдельную вкладку **Driver** для редактирования `overrides.driver_schema` (через JSON),
независимо от выбранной команды. Raw JSON режим остаётся доступным переключателем Mode.

