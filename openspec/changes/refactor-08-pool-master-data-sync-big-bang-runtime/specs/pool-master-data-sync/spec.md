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
- **THEN** запрос отклоняется fail-closed с machine-readable кодом
- **AND** side effects вне workflow pipeline не выполняются

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

### Requirement: Big-bang enablement MUST проходить через fail-closed readiness gates
Система ДОЛЖНА (SHALL) блокировать включение big-bang режима, пока не пройдены обязательные gates:
- load;
- replay/consistency;
- failover/restart;
- security diagnostics.

#### Scenario: Провал readiness gate блокирует cutover
- **GIVEN** перед включением big-bang режима не пройден хотя бы один обязательный gate
- **WHEN** выполняется enablement
- **THEN** система отклоняет включение режима
- **AND** runtime остаётся в состоянии до cutover
