## ADDED Requirements
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
