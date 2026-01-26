# Спецификация: command-schemas-driver-options

## Purpose
Определяет разделение схемы на driver-level (`driver_schema`) и command-level (`commands_by_id.<id>.params_by_name`) для schema-driven драйверов (MVP: `ibcmd`), включая правила сборки канонического `argv[]` и политику конфликтов.
## Requirements
### Requirement: Driver schema для schema-driven драйверов
Система ДОЛЖНА (SHALL) поддерживать driver-level schema (отдельно от command schema) для schema-driven драйверов (минимум `ibcmd`, а также `cli` для driver-level опций).

#### Scenario: Driver schema описывает execution context и опции драйвера
- **WHEN** UI загружает driver schema для `ibcmd`
- **THEN** schema содержит описание driver-level полей execution context (например `connection.*`, `timeout_seconds`, `stdin`, `auth_database_id`) и их UI‑метаданные (группировка/порядок)

#### Scenario: Driver schema описывает CLI extra options
- **WHEN** UI загружает driver schema для `cli`
- **THEN** schema содержит описание `cli_options.*` (startup/logging) как driver-level опций, отдельно от `params_by_name` команд

### Requirement: Connection options не валидируются как params команды
Система ДОЛЖНА (SHALL) обрабатывать `connection.*` и прочие driver-level поля execution context (включая `timeout_seconds`, `stdin`, `auth_database_id`) как driver-level options и НЕ валидировать их через `commands_by_id.<id>.params_by_name`.

#### Scenario: Команда без params_by_name принимает driver-level execution context
- **GIVEN** в каталоге команда имеет пустой `params_by_name`
- **WHEN** пользователь выполняет schema-driven команду и задаёт `connection.remote` и `timeout_seconds`
- **THEN** запрос не завершается ошибкой вида `params are not supported for this command`

### Requirement: Канонический argv включает driver options + command params
Система ДОЛЖНА (SHALL) формировать канонический `argv[]` (и `argv_masked[]`) на стороне API до постановки операции в очередь, включая:
1) driver-level connection options (`connection.*`)
2) command-level params (`params`)
3) `additional_args` после нормализации

Система ДОЛЖНА (SHALL) дополнительно формировать `bindings[]` (Binding Provenance), описывающий происхождение каждого добавленного/нормализованного элемента `argv` и его источник (request/driver catalog/action catalog/database/env), без хранения секретов.

#### Scenario: Preview отражает provenance для argv
- **WHEN** staff делает preview для schema-driven команды с заполненными `connection`/`params`/`additional_args`
- **THEN** preview возвращает `argv_masked[]` и `bindings[]`, где видно, какие элементы пришли из `connection`, какие из `params`, а какие из `additional_args`/нормализации

### Requirement: Поддержка overrides для driver schema
Система ДОЛЖНА (SHALL) позволять переопределять driver-level schema через overrides (аналогично overrides для команд), чтобы изменения проходили через те же пайплайны “Command Schemas”.

#### Scenario: Overrides изменяют driver-level schema без правки base
- **GIVEN** базовый каталог определяет driver schema
- **WHEN** администратор сохраняет overrides, меняя driver-level schema
- **THEN** effective catalog отражает изменения driver schema без изменения base-версии

### Requirement: Явная политика конфликтов
Система ДОЛЖНА (SHALL) иметь документированную и реализованную политику конфликтов для driver-level флагов, когда один и тот же параметр задан в нескольких местах (например `connection` и `additional_args`).

#### Scenario: Конфликт remote между connection и additional_args
- **WHEN** пользователь задаёт `connection.remote` и одновременно добавляет `--remote=...` в `additional_args`
- **THEN** система возвращает ошибку валидации (error), и это поведение документировано

### Requirement: Полное отображение общих флагов `ibcmd` (4.10.2) в driver schema
Система ДОЛЖНА (SHALL) отражать в `ibcmd.driver_schema` полный набор “общих параметров” `ibcmd` из раздела 4.10.2 документации, включая алиасы флагов.

Система ДОЛЖНА (SHALL) помечать секретные поля (`db_password`, `ib_password`) как `sensitive=true`, чтобы:
- `argv_masked[]` не содержал raw значения,
- `bindings[]` отражали `sensitive=true` без раскрытия секретов.

#### Scenario: UI может отрисовать все common flags из driver schema
- **GIVEN** выбран `driver=ibcmd`
- **WHEN** UI загружает effective driver schema
- **THEN** schema включает все флаги 4.10.2 как driver-level поля (включая offline‑параметры и filesystem‑параметры)

#### Scenario: Алиасы флагов представлены в schema
- **WHEN** driver schema включает поле для пароля СУБД
- **THEN** schema содержит алиасы, эквивалентные `--db-pwd` и `--database-password`

### Requirement: Семантика credential-флагов и одновременная передача DBMS + IB creds
Система ДОЛЖНА (SHALL) иметь машиночитаемую семантику credential-флагов в effective schema для `ibcmd`, чтобы различать:
- DBMS creds (offline): `db_user`, `db_password`
- Infobase creds: `ib_user`, `ib_password`

Система ДОЛЖНА (SHALL) поддерживать формирование канонического `argv[]` для `ibcmd`, где одновременно присутствуют:
- offline‑подключение к СУБД (dbms/server/name/user/password),
- аутентификация в ИБ (user/password),
без использования интерактивного режима.

#### Scenario: Одновременная передача DBMS + IB creds работает в одной команде
- **GIVEN** команда `ibcmd` требует offline‑подключения к СУБД и аутентификации в ИБ
- **WHEN** выполняется schema-driven команда с заданными DBMS creds и IB creds
- **THEN** канонический `argv[]` содержит оба набора флагов, и выполнение не требует интерактивного ввода

### Requirement: Стратегия `ib_auth` поддерживает service‑аккаунт только для allowlist safe‑команд
Система ДОЛЖНА (SHALL) поддерживать driver-level стратегию `ib_auth.strategy` со значениями `actor|service|none`.

Система ДОЛЖНА (SHALL) разрешать `ib_auth.strategy=service` только при выполнении ВСЕХ условий:
- команда имеет `risk_level=safe`;
- `command_id` находится в allowlist (минимум: extensions list/sync);
- пользователь имеет право использовать service‑стратегию (RBAC/permission или staff).

В остальных случаях система ДОЛЖНА (SHALL) fail closed (ошибка валидации) и не выполнять команду.

#### Scenario: service разрешён только для allowlist safe‑команды
- **GIVEN** пользователь имеет разрешение на service‑стратегию
- **AND** `command_id` находится в allowlist и `risk_level=safe`
- **WHEN** пользователь выбирает `ib_auth.strategy=service`
- **THEN** запрос валиден и может быть поставлен в очередь

#### Scenario: service запрещён для неallowlist или dangerous команды
- **WHEN** пользователь выбирает `ib_auth.strategy=service` для команды вне allowlist или с `risk_level=dangerous`
- **THEN** система возвращает ошибку валидации, операция не создаётся

### Requirement: Политика `db_pwd` только как argv‑флаг (без stdin)
Система ДОЛЖНА (SHALL) стандартизировать передачу DBMS пароля только через argv‑флаг (`--db-pwd`/`--database-password`) в guided режиме.

Система ДОЛЖНА (SHALL) fail closed, если пользователь пытается использовать stdin‑флаг `--request-db-pwd` (`-W`) в schema-driven (guided) исполнении `ibcmd`.

#### Scenario: Использование `-W` в guided режиме запрещено
- **WHEN** пользователь добавляет `--request-db-pwd` или `-W` в additional_args
- **THEN** система возвращает ошибку валидации и не создаёт операцию

