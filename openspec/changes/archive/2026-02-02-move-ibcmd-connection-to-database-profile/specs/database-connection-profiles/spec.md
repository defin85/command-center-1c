## ADDED Requirements

### Requirement: Профиль подключения `ibcmd` хранится на уровне базы
Система ДОЛЖНА (SHALL) хранить для каждой базы (Database) профиль подключения `ibcmd`, который определяет “как подключаться к этой базе” без привязки к конкретному action/операции.

Профиль ДОЛЖЕН (SHALL) поддерживать минимум:
- режим `remote` (через `--remote=<url>`),
- режим `offline` (через `connection.offline.*`, включая пути `config/data` и DBMS metadata).

Профиль НЕ ДОЛЖЕН (SHALL NOT) содержать секреты (DBMS/IB пароли).

#### Scenario: Пользователь с MANAGE задаёт remote профиль
- **GIVEN** пользователь имеет право `databases.manage_database` на базу
- **WHEN** пользователь устанавливает `mode=remote` и `remote_url`
- **THEN** система сохраняет профиль и использует его при запуске `ibcmd_cli` для этой базы
- **AND** профиль не содержит секретов

#### Scenario: Пользователь с MANAGE задаёт offline профиль, самодостаточный без Configure
- **GIVEN** пользователь имеет право `databases.manage_database` на базу
- **WHEN** пользователь устанавливает `mode=offline` и задаёт `offline.config`, `offline.data`, `offline.dbms`, `offline.db_server`, `offline.db_name` (и опционально `offline.db_path`)
- **THEN** система сохраняет профиль
- **AND** запуск `ibcmd_cli` offline может использовать этот профиль без обязательного ручного заполнения Configure для connection

#### Scenario: Пользователь без MANAGE не может изменить профиль
- **GIVEN** пользователь НЕ имеет права `databases.manage_database` на базу
- **WHEN** пользователь пытается изменить профиль подключения базы
- **THEN** система возвращает 403 и не изменяет данные

### Requirement: Запуск `ibcmd_cli` резолвит connection per target из профиля базы
Система ДОЛЖНА (SHALL) поддерживать для `scope=per_database` резолв effective connection per target database:
- per-run override имеет приоритет,
- иначе используется профиль базы,
- mixed mode допустим (разные базы могут быть в `remote` и `offline` в одном запуске).

Если для части баз effective connection не может быть получен, система ДОЛЖНА (SHALL) fail closed и вернуть 400 с машиночитаемой ошибкой и деталями проблемных таргетов (без секретов).

#### Scenario: Mixed mode в одном запуске разрешён
- **GIVEN** выбраны N баз, где часть имеет `mode=remote`, а часть `mode=offline`
- **WHEN** пользователь запускает `ibcmd_cli` как bulk для выбранных баз
- **THEN** система создаёт одну batch operation с N tasks
- **AND** каждый task использует effective connection, соответствующий профилю своей базы

#### Scenario: Per-run override применим ко всем таргетам
- **GIVEN** пользователь выбрал N баз
- **AND** пользователь включил per-run override connection (например `remote_url`) при запуске операции
- **WHEN** пользователь запускает `ibcmd_cli`
- **THEN** override применяется ко всем tasks операции
- **AND** профиль базы не изменяется

#### Scenario: Отсутствует профиль подключения у части баз → отказ до enqueue
- **GIVEN** выбраны N баз
- **AND** для части из них не настроен профиль подключения `ibcmd` (нет `remote_url` и нет валидного offline профиля)
- **WHEN** пользователь запускает `ibcmd_cli` bulk
- **THEN** API возвращает 400 с `error.code`, указывающим на отсутствие connection profile
- **AND** `error.details` содержит список проблемных баз и причину (без секретов)
- **AND** операция НЕ становится `queued`

