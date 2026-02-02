## ADDED Requirements

### Requirement: UI показывает actionable ошибку при отсутствии offline DBMS metadata
Система ДОЛЖНА (SHALL) отображать понятную и actionable ошибку, если запуск `ibcmd_cli` в `connection.offline` невозможен из-за отсутствующих DBMS metadata (`dbms/db_server/db_name`) у части выбранных баз.

UI ДОЛЖЕН (SHALL):
- показать пользователю, какие поля отсутствуют (без секретов),
- подсказать, что часть значений можно задать в Configure (общие), а часть может требоваться per target (например `db_name`),
- подсказать, где именно исправить DBMS metadata (например, на экране `/databases` через UI редактирования DBMS metadata),
- не начинать выполнение/не показывать “queued” при таком отказе.

#### Scenario: Ошибка показывает список баз и missing keys
- **GIVEN** пользователь запускает `ibcmd_cli` с `connection.offline`
- **AND** API возвращает `error.code=OFFLINE_DB_METADATA_NOT_CONFIGURED` и список проблемных таргетов
- **WHEN** UI отображает результат
- **THEN** UI показывает ошибку и список проблемных баз (ограниченно) и missing keys
- **AND** UI не сохраняет/не отображает секретные значения

#### Scenario: UI подсказывает путь исправления (через /databases)
- **GIVEN** API вернул `error.code=OFFLINE_DB_METADATA_NOT_CONFIGURED`
- **WHEN** UI отображает ошибку
- **THEN** UI содержит подсказку “заполните DBMS metadata базы на /databases” (или эквивалентный CTA)
