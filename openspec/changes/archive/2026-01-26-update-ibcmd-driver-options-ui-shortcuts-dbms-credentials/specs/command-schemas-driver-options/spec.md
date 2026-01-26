## ADDED Requirements
### Requirement: Поддержка скрытых credential-полей в driver schema
Система ДОЛЖНА (SHALL) поддерживать в `driver_schema` метаданные, позволяющие UI скрывать credential‑поля, которые резолвятся на рантайме:
- `semantics.credential_kind` (уже используется)
- `ui.hidden=true` (или эквивалентная машиночитаемая метка)

#### Scenario: UI может скрыть DBMS креды по schema metadata
- **GIVEN** effective `ibcmd.driver_schema` содержит `connection.offline.db_user/db_pwd`
- **WHEN** schema помечает эти поля как скрытые/credential-only
- **THEN** UI не отображает их как поля ввода и не сохраняет в shortcuts

### Requirement: Резолв DBMS creds per-target без передачи из UI
Система ДОЛЖНА (SHALL) резолвить DBMS креды для `ibcmd` per target database на стороне worker (или эквивалентной runtime стадии) на основе credential mapping.

Система ДОЛЖНА (SHALL) запрещать передачу DBMS кредов из UI для обычных пользователей (fail closed) и позволять только ограниченный override для staff/разрешённых ролей (если включён).

#### Scenario: DBMS creds резолвятся на worker
- **GIVEN** `scope=per_database` и выбрано N таргетов
- **WHEN** операция выполняется
- **THEN** для каждого таргета worker формирует `argv[]` с корректными `--db-user/--db-pwd`, не требуя интерактивного ввода

### Requirement: Per-target резолв `connection.offline.*` для per_database команд
Система ДОЛЖНА (SHALL) поддерживать per-target резолв offline‑параметров подключения (`dbms/db_server/db_name/db_path` и др.) для `scope=per_database`, так как значения могут отличаться для разных баз.

#### Scenario: `--db-name` различается по таргетам
- **GIVEN** операция `ibcmd` `scope=per_database` и выбраны базы с разными `db_name`
- **WHEN** операция выполняется
- **THEN** каждый task использует свой `--db-name`, полученный из настроек/метаданных конкретной базы

#### Scenario: Общий шаблон Configure дополняется per-target значениями
- **GIVEN** пользователь выбрал N баз и задал `connection.offline.dbms` и `connection.offline.db_server` в Configure
- **AND** `connection.offline.db_name` не задан явно в Configure
- **WHEN** операция выполняется
- **THEN** `--dbms` и `--db-server` берутся из Configure (общие значения)
- **AND** `--db-name` берётся per target из настроек/метаданных базы

## MODIFIED Requirements
### Requirement: Семантика credential-флагов и одновременная передача DBMS + IB creds
Система ДОЛЖНА (SHALL) формировать канонический `argv[]` для `ibcmd`, где одновременно присутствуют:
- offline‑подключение к СУБД (dbms/server/name/… + креды DBMS),
- аутентификация в ИБ (user/password),
без использования интерактивного режима.

При этом DBMS креды ДОЛЖНЫ (SHALL) приходить из credential mapping (а не из UI), а IB креды — из `ib_auth` стратегии.

#### Scenario: Одновременная передача DBMS + IB creds работает для нескольких таргетов
- **GIVEN** `scope=per_database` и выбраны N таргетов
- **WHEN** операция выполняется
- **THEN** каждый таргет получает свой набор DBMS creds + IB creds в `argv[]`
