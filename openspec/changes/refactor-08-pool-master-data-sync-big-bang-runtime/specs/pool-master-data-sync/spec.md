## ADDED Requirements
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
