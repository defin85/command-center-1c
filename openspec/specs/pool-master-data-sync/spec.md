# pool-master-data-sync Specification

## Purpose
TBD - created by archiving change add-07-pool-master-data-bidirectional-sync. Update Purpose after archive.
## Requirements
### Requirement: Master-data sync MUST поддерживать двусторонний режим с явной policy источника истины
Система ДОЛЖНА (SHALL) поддерживать синхронизацию master-data между CC и ИБ в двух направлениях (`CC -> ИБ`, `ИБ -> CC`) с tenant-scoped policy:
- `cc_master`;
- `ib_master`;
- `bidirectional`.

Система НЕ ДОЛЖНА (SHALL NOT) применять неявный merge при расхождении данных без учёта policy.

#### Scenario: Tenant включает policy `bidirectional` для номенклатуры
- **GIVEN** для tenant опубликована sync policy `bidirectional` для `item`
- **WHEN** изменения появляются как в CC, так и в ИБ
- **THEN** система применяет двусторонний контракт синхронизации
- **AND** конфликтные случаи обрабатываются через conflict queue без silent overwrite

### Requirement: Sync orchestration MUST проходить через workflow+operations execution path
Система ДОЛЖНА (SHALL) исполнять long-running sync через цепочку:
- domain master-data sync;
- workflow execution;
- operations enqueue/outbox;
- worker execution.

Система НЕ ДОЛЖНА (SHALL NOT) выполнять долгие sync-операции синхронно в API request/response цикле.

#### Scenario: Запуск sync возвращает execution identifiers, а выполнение идёт асинхронно
- **GIVEN** оператор или системный процесс запускает sync job для tenant/database/entity scope
- **WHEN** запрос принят API
- **THEN** создаётся sync job и запускается workflow execution
- **AND** sync job связывается с `workflow_execution_id` и `operation_id`
- **AND** фактические OData/exchange-plan side effects выполняются worker-процессом

### Requirement: Outbound sync (`CC -> ИБ`) MUST использовать transactional outbox и идемпотентный dispatcher
Система ДОЛЖНА (SHALL) формировать outbox intents в той же транзакции, где фиксируется mutating изменение canonical master-data в CC.

Dispatcher ДОЛЖЕН (SHALL):
- обрабатывать pending intents батчами;
- поддерживать retry/backoff;
- гарантировать идемпотентность применения по dedupe key.

#### Scenario: Повторная доставка intent не создаёт duplicate side effect
- **GIVEN** один и тот же outbox intent доставлен dispatcher повторно после сбоя
- **WHEN** dispatcher повторно применяет intent в target ИБ
- **THEN** бизнес-состояние в ИБ остаётся эквивалентным одному применению
- **AND** в CC фиксируется idempotent outcome без duplicate binding write

### Requirement: Inbound sync (`ИБ -> CC`) MUST использовать checkpointed exchange-plan polling
Система ДОЛЖНА (SHALL) читать изменения из ИБ через exchange-plan polling (`SelectChanges`) с persisted checkpoint на scope `(tenant, database, entity)`.

Система ДОЛЖНА (SHALL) отправлять acknowledge (`NotifyChangesReceived`) только после успешного commit локального применения в CC.

#### Scenario: Acknowledge выполняется только после local commit
- **GIVEN** poller получил batch изменений из ИБ
- **WHEN** часть изменений не проходит local apply и транзакция откатывается
- **THEN** `NotifyChangesReceived` не отправляется для этого batch
- **AND** изменения остаются доступными для повторного чтения

### Requirement: Sync persistence MUST использовать общий Postgres с отдельными таблицами домена
Система ДОЛЖНА (SHALL) хранить `sync_job/sync_scope/sync_checkpoint/sync_outbox/sync_conflict` и dedupe metadata в общем Postgres текущего сервиса.

Система НЕ ДОЛЖНА (SHALL NOT) требовать отдельную физическую БД для sync-контуров в рамках этого change.

#### Scenario: Sync state хранится в общей БД без cross-database транзакций
- **GIVEN** mutating изменение canonical master-data и формирование outbound intent
- **WHEN** транзакция фиксируется
- **THEN** canonical изменение и sync outbox запись фиксируются атомарно в общей БД
- **AND** не используется distributed transaction между разными БД

### Requirement: Sync delivery MUST быть at-least-once с дедупликацией
Система ДОЛЖНА (SHALL) поддерживать at-least-once delivery semantics для inbound/outbound контуров.

Система ДОЛЖНА (SHALL) хранить dedupe metadata (`origin_event_id`, checkpoint markers, fingerprint) и отбрасывать повторное применение уже обработанных событий.

#### Scenario: Restart приводит к повторной выдаче событий без дублирования состояния
- **GIVEN** после crash worker восстанавливается с checkpoint до последнего обработанного сообщения
- **WHEN** источник повторно отдаёт ранее доставленное событие
- **THEN** событие распознаётся как duplicate
- **AND** canonical состояние не изменяется повторно

### Requirement: Conflict handling MUST быть fail-closed и operator-driven
Система ДОЛЖНА (SHALL) при конфликте policy/версий/ownership формировать persisted conflict record с machine-readable кодом и контекстом scope.

Система НЕ ДОЛЖНА (SHALL NOT) автоматически перетирать данные при конфликте в режиме `bidirectional`.

#### Scenario: Одновременное изменение в CC и ИБ создаёт conflict record
- **GIVEN** одна и та же canonical сущность изменена в CC и в ИБ в конфликтующем порядке
- **WHEN** sync worker выполняет reconcile
- **THEN** создаётся conflict record со статусом `pending`
- **AND** автоматический overwrite не выполняется до operator resolve

### Requirement: Sync MUST предотвращать ping-pong репликацию
Система ДОЛЖНА (SHALL) передавать и учитывать `origin_system` и `origin_event_id` в каждом sync-событии.

Система НЕ ДОЛЖНА (SHALL NOT) генерировать обратный sync event для изменения, которое уже имеет foreign origin из противоположного контура.

#### Scenario: Событие из ИБ не порождает обратную публикацию в ту же ИБ
- **GIVEN** inbound worker применил изменение с `origin_system=ib` и `origin_event_id=evt-123`
- **WHEN** outbound pipeline анализирует это изменение
- **THEN** pipeline распознаёт foreign origin
- **AND** не создаёт новый outbound intent для этого же origin

### Requirement: Система MUST публиковать операторский read-model синхронизации
Система ДОЛЖНА (SHALL) предоставлять read-model статуса синхронизации по tenant/database/entity:
- checkpoint position;
- lag;
- pending/retry counts;
- conflict counts;
- last_success_at / last_error_code.

Система ДОЛЖНА (SHALL) предоставлять mutating действия для operator remediation: `retry`, `reconcile`, `resolve conflict`.

#### Scenario: Оператор видит деградацию lag и запускает manual retry
- **GIVEN** lag для outbound sync превышает порог SLA
- **WHEN** оператор открывает sync status UI и запускает retry
- **THEN** система фиксирует операторское действие в audit trail
- **AND** статус очереди обновляется в read-model

### Requirement: Sync diagnostics MUST быть безопасными и audit-friendly
Система ДОЛЖНА (SHALL) сохранять machine-readable диагностику синхронизации без утечки секретов.

Система ДОЛЖНА (SHALL) писать audit события для mutating операторских действий (`retry/reconcile/resolve`) с идентификатором пользователя и scope.

#### Scenario: Ошибка auth transport не раскрывает пароль в diagnostics
- **GIVEN** sync step завершился auth/transport ошибкой при обращении к ИБ
- **WHEN** система формирует diagnostics и API response
- **THEN** payload содержит error code и remediation hint
- **AND** credentials/secret fields отсутствуют в response и логах

### Requirement: Master-data sync runtime MUST использовать единый big-bang execution path
Система ДОЛЖНА (SHALL) исполнять inbound/outbound/reconcile master-data sync только через цепочку `domain -> workflow -> operations -> worker`.

Система НЕ ДОЛЖНА (SHALL NOT) иметь отдельный runtime lifecycle для inbound, обходящий workflow execution path.

#### Scenario: Inbound batch обрабатывается как workflow step в общем runtime
- **GIVEN** в scope `(tenant, database, entity)` доступны изменения для inbound обработки
- **WHEN** стартует sync execution
- **THEN** inbound polling/apply/ack выполняется как workflow operation step
- **AND** execution observability и retry semantics совпадают с outbound шагами

#### Scenario: Legacy inbound entrypoint отклоняется после cutover
- **GIVEN** оператор или сервис вызывает legacy inbound path, обходящий workflow runtime
- **WHEN** система валидирует execution route
- **THEN** запрос отклоняется fail-closed с machine-readable кодом `SYNC_LEGACY_INBOUND_ROUTE_DISABLED`
- **AND** side effects вне workflow pipeline не выполняются

### Requirement: Inbound acknowledge MUST быть commit-safe
Система ДОЛЖНА (SHALL) отправлять inbound acknowledge (`NotifyChangesReceived`) только после успешного локального commit применения и фиксации checkpoint.

Система НЕ ДОЛЖНА (SHALL NOT) отправлять acknowledge для batch, где local apply завершился rollback.

#### Scenario: Rollback local apply блокирует acknowledge
- **GIVEN** inbound batch прочитан через exchange-plan/OData
- **WHEN** local apply завершается ошибкой и транзакция откатывается
- **THEN** `NotifyChangesReceived` не отправляется
- **AND** batch остаётся доступным для корректного повторного чтения

### Requirement: Reconcile MUST укладываться в 120-second window на масштабе 6x120 ИБ
Система ДОЛЖНА (SHALL) исполнять reconcile как окно с fan-out/fan-in и дедлайном 120 секунд для полного покрытия scope.

Система ДОЛЖНА (SHALL) формировать machine-readable partial outcome, если часть scope не успела к дедлайну.

#### Scenario: Fan-out/fan-in окно завершает сверку с partial outcome
- **GIVEN** создано reconcile-окно для 720 ИБ
- **WHEN** часть probe-задач завершилась после `deadline_at`
- **THEN** окно закрывается с partial outcome и детерминированной диагностикой пропусков
- **AND** успешно завершённые scope не откатываются

### Requirement: Worker topology MUST поддерживать role и server affinity в общей очереди
Система ДОЛЖНА (SHALL) использовать общую очередь sync workload с role-aware и affinity-aware обработкой:
- `role`: `inbound|outbound|reconcile|manual_remediation`;
- `server_affinity`: ключ сервера/кластера 1С.

Система НЕ ДОЛЖНА (SHALL NOT) выполнять задачу на worker, который не удовлетворяет affinity/role constraints.

#### Scenario: Задача с server affinity исполняется локальным пулом
- **GIVEN** sync job содержит `server_affinity=srv-1c-a` и `role=inbound`
- **WHEN** задача разбирается воркерами
- **THEN** job получает worker из пула `srv-1c-a` с поддержкой роли `inbound`
- **AND** worker другого affinity не подтверждает выполнение job

### Requirement: Worker scheduling MUST предотвращать starvation и сохранять operator capacity
Система ДОЛЖНА (SHALL) обеспечивать fairness scheduling для общей очереди:
- reserved capacity для `manual_remediation` в каждом server pool;
- age-based anti-starvation promotion для долго ожидающих задач;
- tenant budget limiter для noisy tenant.

#### Scenario: Mass reconcile не блокирует manual remediation
- **GIVEN** очередь перегружена reconcile-задачами
- **WHEN** оператор запускает `manual_remediation` для критичного scope
- **THEN** задача получает execution slot в пределах SLA policy
- **AND** ожидание низкоприоритетных задач не растёт бесконтрольно из-за starvation

### Requirement: Server affinity resolution MUST быть детерминированным и fail-closed
Система ДОЛЖНА (SHALL) использовать фиксированный порядок резолва `IB scope -> server_affinity`:
1. database-level override;
2. cluster-level mapping;
3. derived affinity key из нормализованного server endpoint.

Система НЕ ДОЛЖНА (SHALL NOT) публиковать enqueue в stream при неразрешимом affinity.

#### Scenario: Неразрешимый IB scope блокирует enqueue
- **GIVEN** sync execution инициирован для scope без валидного `server_affinity`
- **WHEN** выполняется affinity resolution
- **THEN** enqueue отклоняется fail-closed с кодом `SERVER_AFFINITY_UNRESOLVED`
- **AND** root operation projection не переходит в `queued`

### Requirement: Big-bang enablement MUST проходить через fail-closed readiness gates
Система ДОЛЖНА (SHALL) блокировать включение big-bang режима, пока не пройдены обязательные gates:
- load;
- replay/consistency;
- failover/restart;
- security diagnostics.

Каждый gate ДОЛЖЕН (SHALL) иметь формальные pass/fail пороги:
- load: `reconcile_window_p95_seconds <= 120`, `coverage_ratio >= 0.995`;
- replay/consistency: `lost_events_total = 0`, `duplicate_apply_total = 0`;
- failover/restart: `checkpoint_monotonicity_violations = 0`, `ack_before_commit_violations = 0`;
- security: `secrets_exposed_in_diagnostics = 0`, `secrets_exposed_in_last_error = 0`.

Система ДОЛЖНА (SHALL) сохранять machine-readable gate report со `schema_version`, измеренными значениями, порогами, ссылками на evidence и итоговым `overall_status`.

Система ДОЛЖНА (SHALL) получать ORR sign-off (`platform`, `security`, `operations`) перед enablement.

#### Scenario: Провал readiness gate блокирует cutover
- **GIVEN** перед включением big-bang режима не пройден хотя бы один обязательный gate
- **WHEN** выполняется enablement
- **THEN** система отклоняет включение режима
- **AND** runtime остаётся в состоянии до cutover

#### Scenario: Gate report неполный или без ORR sign-off блокирует enablement
- **GIVEN** gate-runner завершён, но отсутствуют обязательные поля отчёта или нет sign-off одной из ролей
- **WHEN** выполняется enablement big-bang режима
- **THEN** система отклоняет включение fail-closed
- **AND** оператор получает machine-readable причину блокировки

### Requirement: Cutover/rollback MUST сохранять in-flight консистентность
Система ДОЛЖНА (SHALL) выполнять cutover по протоколу `freeze -> drain -> watermark capture -> enable -> verify`.

Система ДОЛЖНА (SHALL) использовать watermark-based rollback/replay-safe восстановление для in-flight сообщений.

#### Scenario: Cutover выполняется без потери in-flight задач
- **GIVEN** перед enablement существуют in-flight sync сообщения
- **WHEN** запускается cutover protocol
- **THEN** новые enqueue по legacy path блокируются на этапе `freeze`
- **AND** включение big-bang режима выполняется только после `drain` и фиксации watermark

#### Scenario: Rollback после enablement не нарушает checkpoint/ack
- **GIVEN** после включения обнаружен gate-breaking инцидент
- **WHEN** выполняется rollback protocol
- **THEN** система откатывает артефакт и восстанавливает состояние по watermark
- **AND** повторный replay не приводит к потере или duplicate apply

### Requirement: Sync runtime MUST быть операторски прозрачным
Система ДОЛЖНА (SHALL) публиковать read-model очередей и задач со статусами `queued|processing|retrying|failed|completed` и scheduling-полями (`priority`, `role`, `server_affinity`, `deadline_at`, `deadline_state`).

Система ДОЛЖНА (SHALL) поддерживать фильтрацию операторских запросов по scheduling-полям.

#### Scenario: Оператор видит backlog и дедлайн-риски по affinity/role
- **GIVEN** в системе есть накопленный sync backlog
- **WHEN** оператор запрашивает read-model очереди с фильтрами `priority`, `role`, `server_affinity`
- **THEN** ответ содержит согласованные counts/lag и состояния задач
- **AND** deadline miss/partial risk виден в machine-readable виде

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

### Requirement: Master-data sync and bootstrap routing MUST читаться из executable reusable-data registry
Система ДОЛЖНА (SHALL) определять bootstrap eligibility, dependency ordering, sync enqueue и outbox fan-out через executable reusable-data registry/type handlers.

Система НЕ ДОЛЖНА (SHALL NOT) выводить routing eligibility только из enum membership, OpenAPI namespace или наличия binding row.

#### Scenario: Bootstrap routing не зависит от handwritten scope lists
- **GIVEN** reusable-data registry уже определяет bootstrap capability для shipped entity types
- **WHEN** оператор запускает bootstrap import
- **THEN** backend и frontend используют registry-driven entity catalog
- **AND** список доступных сущностей не поддерживается вручную в нескольких местах

### Requirement: Unsupported reusable-data directions MUST блокироваться fail-closed
Система ДОЛЖНА (SHALL) блокировать mutating sync/outbox actions для reusable entity types, если registry не объявляет соответствующую direction capability.

Operator-facing sync affordances ДОЛЖНЫ (SHALL) читать то же capability решение, что и backend runtime.

#### Scenario: Runtime и UI одинаково скрывают неподдержанную direction capability
- **GIVEN** reusable entity type не имеет declared outbound capability в registry
- **WHEN** система строит sync read-model и оценивает enqueue eligibility
- **THEN** backend не создаёт mutating sync intent
- **AND** UI не показывает generic action для этой direction

### Requirement: Reusable account entities MUST иметь explicit sync ownership contract
Система ДОЛЖНА (SHALL) для reusable account entities явно фиксировать поддерживаемые и запрещённые sync directions в executable capability matrix.

Для этого change:
- `GLAccount` МОЖЕТ (MAY) использовать bootstrap import path из ИБ в CC;
- `GLAccount` НЕ ДОЛЖЕН (SHALL NOT) автоматически включаться в `CC -> ИБ` outbound sync или `bidirectional` mutation policy;
- `GLAccountSet` НЕ ДОЛЖЕН (SHALL NOT) участвовать в inbound/outbound sync как target IB entity.

#### Scenario: Сохранение GLAccount не порождает automatic outbound sync intent
- **GIVEN** оператор изменяет canonical `GLAccount` в CC
- **WHEN** runtime оценивает sync ownership для этого entity type
- **THEN** automatic outbound sync intent в target ИБ не формируется
- **AND** plan-of-accounts mutation не происходит без отдельного одобренного change

#### Scenario: GLAccount bootstrap import использует existing staged lifecycle
- **GIVEN** оператор запускает bootstrap import для `GLAccount`
- **WHEN** система создаёт bootstrap job
- **THEN** job использует existing lifecycle `preflight -> dry_run -> execute -> finalize`
- **AND** не появляется отдельный account-only async pipeline

