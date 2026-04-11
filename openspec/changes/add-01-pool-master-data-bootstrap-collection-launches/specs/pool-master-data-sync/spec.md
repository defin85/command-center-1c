## MODIFIED Requirements

### Requirement: Bootstrap import from IB MUST использовать staged asynchronous job lifecycle
Система ДОЛЖНА (SHALL) выполнять первичный импорт canonical master-data из ИБ через staged asynchronous lifecycle:
- `preflight`;
- `dry_run`;
- `execute`;
- `finalize`.

Система НЕ ДОЛЖНА (SHALL NOT) выполнять полный bootstrap import синхронно в request/response цикле API.

Система ДОЛЖНА (SHALL) публиковать machine-readable job status/read-model с прогрессом и итоговыми counters.

Это требование распространяется как на single-database bootstrap import, так и на parent batch collection request, который оркестрирует несколько per-database bootstrap jobs.

#### Scenario: Execute single-database bootstrap запускает асинхронный child job
- **GIVEN** оператор выбрал tenant-scoped базу и сущности для bootstrap import
- **AND** `preflight` и `dry_run` завершились успешно
- **WHEN** оператор запускает `execute`
- **THEN** API возвращает идентификатор bootstrap job и начальный статус
- **AND** фактическое чтение/применение данных выполняется асинхронно вне request/response

#### Scenario: Batch collection execute не импортирует все базы синхронно в API
- **GIVEN** оператор выбрал `cluster_all` или `database_set` для batch collection
- **AND** aggregate `preflight` и `dry_run` завершились успешно
- **WHEN** оператор запускает `execute`
- **THEN** API возвращает parent collection identifier и начальный статус
- **AND** fan-out per-database bootstrap jobs выполняется асинхронно вне request/response
- **AND** parent read-model публикует aggregate progress и per-database outcomes

### Requirement: Bootstrap import MUST быть dependency-aware, chunked и идемпотентным
Система ДОЛЖНА (SHALL) обрабатывать bootstrap import chunk-ами с детерминированным порядком сущностей:
`party -> item -> tax_profile -> contract -> binding`.

Система ДОЛЖНА (SHALL) поддерживать resume/retry без duplicate side effects для canonical сущностей и bindings.

Система НЕ ДОЛЖНА (SHALL NOT) silently игнорировать ошибки зависимостей; конфликтные/неконсистентные строки должны попадать в diagnostics/failed counters.

Batch collection ДОЛЖЕН (SHALL) переиспользовать этот child path для каждой выбранной ИБ, а не вводить отдельный bulk executor с другой dependency semantics.

#### Scenario: Batch collection переиспользует child chunk order для каждой базы
- **GIVEN** parent batch collection request включает несколько ИБ
- **WHEN** система запускает child bootstrap jobs для каждой базы
- **THEN** каждая база исполняет existing dependency order `party -> item -> tax_profile -> contract -> binding`
- **AND** batch orchestration не вводит второй порядок применения для тех же сущностей

## ADDED Requirements

### Requirement: Batch bootstrap collection MUST поддерживать target mode `cluster_all` и `database_set`
Система ДОЛЖНА (SHALL) поддерживать parent batch collection request для bootstrap import с target mode:
- `cluster_all` — все ИБ выбранного кластера;
- `database_set` — явный список выбранных ИБ.

Система ДОЛЖНА (SHALL) фиксировать immutable snapshot реально выбранных `database_ids` в момент принятия batch request.

Система НЕ ДОЛЖНА (SHALL NOT) изменять snapshot уже созданного batch request после изменения cluster membership или списка доступных ИБ.

#### Scenario: Cluster-wide collection фиксирует snapshot целей
- **GIVEN** оператор создаёт batch collection request с `target_mode=cluster_all`
- **WHEN** API принимает запрос
- **THEN** система сохраняет immutable snapshot всех попавших в него `database_ids`
- **AND** дальнейшие изменения состава кластера не переписывают уже созданный batch request

### Requirement: Batch collection MUST публиковать parent read-model и per-database item outcomes
Система ДОЛЖНА (SHALL) публиковать parent read-model batch collection request минимум с полями:
- `collection_id`;
- `target_mode`;
- `cluster_id`, если применимо;
- immutable snapshot `database_ids`;
- `entity_scope`;
- aggregate counters `scheduled/coalesced/skipped/failed/completed`.

Система ДОЛЖНА (SHALL) публиковать per-database items с:
- `database_id`;
- outcome status;
- machine-readable reason;
- ссылкой на child bootstrap job, если он был создан или переиспользован.

#### Scenario: Оператор видит mixed outcome batch collection по базам
- **GIVEN** batch collection request выполнился по нескольким ИБ
- **WHEN** часть child jobs была запущена успешно, часть коалесцировалась, а часть завершилась fail-closed ошибкой
- **THEN** parent detail показывает aggregate counters
- **AND** per-database items позволяют различить `scheduled`, `coalesced`, `failed` и `completed`

### Requirement: Batch collection MUST коалесцировать уже активные child bootstrap jobs
Если для выбранной ИБ уже существует активный совместимый child bootstrap import job, система НЕ ДОЛЖНА (SHALL NOT) создавать duplicate child job только из-за повторного batch request.

Вместо этого система ДОЛЖНА (SHALL) помечать соответствующий item как `coalesced` и сохранять ссылку на уже существующий child bootstrap job.

#### Scenario: Повторный batch collection переиспользует активный child bootstrap job
- **GIVEN** для `db-1` уже идёт active bootstrap import job с тем же `entity_scope`
- **WHEN** оператор запускает новый batch collection, содержащий `db-1`
- **THEN** система не создаёт duplicate child bootstrap job
- **AND** item для `db-1` получает status `coalesced`
- **AND** parent detail показывает ссылку на уже существующий child job
