# Delta: database-connection-profiles

## MODIFIED Requirements
### Requirement: Профиль подключения `ibcmd` хранится на уровне базы
Система ДОЛЖНА (SHALL) хранить для каждой базы (Database) профиль подключения `ibcmd`, который определяет “какие driver-level connection параметры применять” без привязки к конкретной операции.

Профиль ДОЛЖЕН (SHALL) быть “raw flags” (без интерпретации режима) и поддерживать минимум:
- `remote` (строго `ssh://...` для `--remote=<url>`),
- `pid` (для `--pid=<pid>`),
- `offline` (dict произвольных `offline.*` ключей, соответствующих driver schema).

Профиль МОЖЕТ (MAY) быть пустым.

Профиль НЕ ДОЛЖЕН (SHALL NOT) содержать секреты (DBMS/IB пароли и эквиваленты). При попытке сохранить секреты система ДОЛЖНА (SHALL) fail-closed.

#### Scenario: UI `/databases` не добавляет offline флаги по умолчанию
- **GIVEN** пользователь открыл редактирование `IBCMD connection profile` для базы с отсутствующим/пустым профилем
- **WHEN** UI отображает форму
- **THEN** UI не показывает никаких offline‑строк по умолчанию и не требует заполнения `config/data`
- **AND** пользователь может самостоятельно добавить нужные offline‑ключи и значения

#### Scenario: UI позволяет выбрать offline ключ из driver schema
- **GIVEN** UI имеет доступ к effective `driver_schema` для `driver=ibcmd`
- **WHEN** пользователь выбирает offline‑ключ из списка, построенного из `driver_schema.connection.offline`
- **THEN** UI добавляет выбранный ключ в редактируемый профиль и позволяет задать значение

