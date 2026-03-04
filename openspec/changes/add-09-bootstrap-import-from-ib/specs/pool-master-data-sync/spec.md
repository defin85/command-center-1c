## ADDED Requirements
### Requirement: Bootstrap import from IB MUST использовать staged asynchronous job lifecycle
Система ДОЛЖНА (SHALL) выполнять первичный импорт canonical master-data из ИБ через асинхронный job lifecycle:
- `preflight`;
- `dry_run`;
- `execute`;
- `finalize`.

Система НЕ ДОЛЖНА (SHALL NOT) выполнять полный bootstrap import синхронно в request/response цикле API.

Система ДОЛЖНА (SHALL) публиковать machine-readable job status/read-model с прогрессом и итоговыми counters.

#### Scenario: Execute запускает асинхронный bootstrap job
- **GIVEN** оператор выбрал tenant-scoped базу и сущности для bootstrap import
- **AND** `preflight` и `dry_run` завершились успешно
- **WHEN** оператор запускает `execute`
- **THEN** API возвращает идентификатор bootstrap job и начальный статус
- **AND** фактическое чтение/применение данных выполняется асинхронно вне request/response

#### Scenario: Провал preflight блокирует execute
- **GIVEN** для выбранной базы не пройден preflight (например, недоступен source или не настроен auth mapping)
- **WHEN** оператор пытается запустить `execute`
- **THEN** система отклоняет запуск fail-closed с machine-readable кодом
- **AND** bootstrap job в состоянии исполнения не создаётся

### Requirement: Bootstrap import MUST быть dependency-aware, chunked и идемпотентным
Система ДОЛЖНА (SHALL) обрабатывать bootstrap import chunk-ами с детерминированным порядком сущностей:
`party -> item -> tax_profile -> contract -> binding`.

Система ДОЛЖНА (SHALL) поддерживать resume/retry без duplicate side effects для canonical сущностей и bindings.

Система НЕ ДОЛЖНА (SHALL NOT) silently игнорировать ошибки зависимостей; конфликтные/неконсистентные строки должны попадать в diagnostics/failed counters.

#### Scenario: Повторный запуск failed chunk не создаёт дубликаты
- **GIVEN** bootstrap job ранее завершился частично и содержит failed chunk
- **WHEN** оператор запускает retry только для failed chunk
- **THEN** успешно импортированные ранее записи не дублируются
- **AND** итоговое состояние canonical/binding остаётся идемпотентным

#### Scenario: Contract без валидного owner counterparty не применяется silently
- **GIVEN** во входных данных контракта отсутствует валидная зависимость owner counterparty
- **WHEN** bootstrap executor обрабатывает chunk контрактов
- **THEN** проблемная строка фиксируется как failed/deferred с machine-readable diagnostic
- **AND** остальные валидные строки chunk продолжают обрабатываться

### Requirement: Bootstrap import MUST сохранять sync safety инварианты
Система ДОЛЖНА (SHALL) маркировать изменения, применённые bootstrap import, как inbound-origin (`origin_system=ib` + стабильный `origin_event_id`), чтобы исключить ping-pong репликацию.

Система ДОЛЖНА (SHALL) сохранять конфликты/ошибки импорта в machine-readable виде, без silent overwrite conflicting данных.

#### Scenario: Bootstrap-применение не порождает обратный outbound echo
- **GIVEN** bootstrap executor применил canonical изменение с inbound origin от ИБ
- **WHEN** outbound sync анализирует изменение после commit
- **THEN** outbound pipeline распознаёт foreign origin
- **AND** не создаёт обратный sync event в ту же ИБ

#### Scenario: Конфликт импорта фиксируется в diagnostics без автоматического перетирания
- **GIVEN** bootstrap import обнаружил конфликт в данных для scope `(tenant, database, entity)`
- **WHEN** executor обрабатывает конфликтную запись
- **THEN** система фиксирует machine-readable conflict/diagnostic запись
- **AND** конфликтные данные не перезаписывают текущее canonical состояние silently

