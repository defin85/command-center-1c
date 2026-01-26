## ADDED Requirements

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

