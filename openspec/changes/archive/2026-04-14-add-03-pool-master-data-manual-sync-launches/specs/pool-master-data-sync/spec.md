## MODIFIED Requirements

### Requirement: Sync orchestration MUST проходить через workflow+operations execution path
Система ДОЛЖНА (SHALL) исполнять long-running sync через цепочку:
- domain master-data sync;
- workflow execution;
- operations enqueue/outbox;
- worker execution.

Система НЕ ДОЛЖНА (SHALL NOT) выполнять долгие sync-операции синхронно в API request/response цикле.

Это требование распространяется как на per-scope child sync jobs, так и на operator-initiated manual launch requests, которые fan-out'ят множество child scope.

#### Scenario: Запуск per-scope sync возвращает execution identifiers, а выполнение идёт асинхронно
- **GIVEN** оператор или системный процесс запускает sync job для tenant/database/entity scope
- **WHEN** запрос принят API
- **THEN** создаётся child sync job и запускается workflow execution
- **AND** sync job связывается с `workflow_execution_id` и `operation_id`
- **AND** фактические OData/exchange-plan side effects выполняются worker-процессом

#### Scenario: Cluster-wide manual launch не fan-out'ит child scope синхронно в API
- **GIVEN** оператор запускает manual sync для всех ИБ выбранного кластера
- **WHEN** API принимает launch request
- **THEN** система сохраняет parent launch request и возвращает `launch_id` без ожидания завершения всех child scope
- **AND** дальнейший fan-out выполняется асинхронно через workflow/operations path
- **AND** child `(tenant, database, entity)` sync jobs создаются или коалесцируются через существующий runtime path

### Requirement: Система MUST публиковать операторский read-model синхронизации
Система ДОЛЖНА (SHALL) предоставлять read-model статуса синхронизации по tenant/database/entity:
- checkpoint position;
- lag;
- pending/retry counts;
- conflict counts;
- last_success_at / last_error_code.

Система ДОЛЖНА (SHALL) предоставлять mutating действия для operator remediation: `retry`, `reconcile`, `resolve conflict`.

Система ДОЛЖНА (SHALL) дополнительно публиковать read-model history/detail для operator-initiated manual launch requests:
- `launch_id`, `mode`, `target_mode`, `cluster_id` (если применимо);
- immutable snapshot `database_ids` и `entity_scope`;
- aggregate counters `scheduled/coalesced/skipped/failed/completed`;
- per-scope item outcomes с machine-readable причиной и ссылкой на child `sync_job_id`, если он существует.

#### Scenario: Оператор видит mixed outcome ручного запуска в launch history
- **GIVEN** manual launch был создан для нескольких ИБ и entity scopes
- **WHEN** часть child scope уже имела активные sync jobs, а часть завершилась ошибкой policy/affinity
- **THEN** launch detail показывает aggregate counters и per-scope item outcomes
- **AND** оператор различает `scheduled`, `coalesced` и `failed` scope без чтения raw JSON

## ADDED Requirements

### Requirement: Manual sync launch MUST поддерживать target mode `cluster_all` и `database_set`
Система ДОЛЖНА (SHALL) принимать operator-initiated manual sync launch request в одном из режимов:
- `inbound`;
- `outbound`;
- `reconcile`.

Launch request ДОЛЖЕН (SHALL) поддерживать target mode:
- `cluster_all` — все ИБ выбранного кластера;
- `database_set` — явный список выбранных ИБ.

Система ДОЛЖНА (SHALL) фиксировать immutable snapshot реально выбранных target databases в момент принятия запроса.

Система НЕ ДОЛЖНА (SHALL NOT) переписывать target snapshot уже созданного launch request, если после этого изменился состав кластера или список доступных ИБ.

#### Scenario: Cluster membership change не меняет уже принятый launch snapshot
- **GIVEN** оператор создал launch request с `target_mode=cluster_all` для кластера `cluster-a`
- **AND** в момент принятия запроса в snapshot вошли `db-1`, `db-2`, `db-3`
- **WHEN** позже в кластере появляется новая ИБ `db-4`
- **THEN** launch detail продолжает показывать исходный snapshot `db-1..db-3`
- **AND** новая ИБ не добавляется в уже созданный launch автоматически

#### Scenario: Explicit database set отклоняется при пустом или недоступном target наборе
- **GIVEN** оператор отправляет manual launch с `target_mode=database_set`
- **WHEN** список `database_ids` пуст или содержит ИБ вне допустимого tenant scope
- **THEN** API отклоняет запрос fail-closed
- **AND** parent launch request не создаётся

### Requirement: Manual launch fan-out MUST переиспользовать существующие child scope jobs и коалесцировать активные scope
Система ДОЛЖНА (SHALL) для каждого `(database, entity)` из launch snapshot запускать fan-out только через существующие child sync trigger entrypoint-ы.

Если в совместимом direction уже существует активный child sync job для того же `(tenant, database, entity)`, система НЕ ДОЛЖНА (SHALL NOT) создавать duplicate child job.

Вместо этого система ДОЛЖНА (SHALL) помечать launch item как `coalesced` и сохранять ссылку на существующий child `sync_job_id`.

#### Scenario: Повторный ручной запуск переиспользует активный child scope
- **GIVEN** для `(tenant=t-1, database=db-1, entity=item)` уже существует активный `outbound` child sync job
- **WHEN** оператор создаёт новый manual launch, включающий тот же scope
- **THEN** система не создаёт duplicate child job
- **AND** launch item получает status `coalesced`
- **AND** operator detail показывает ссылку на уже существующий child sync job

### Requirement: Manual launch MUST сохранять per-scope fail-closed outcome без silent partial success
Система ДОЛЖНА (SHALL) оценивать capability, effective policy, affinity и runtime enablement на child scope уровне при fan-out manual launch.

Если отдельный scope не может быть запущен из-за policy violation, affinity resolution failure или runtime-disabled path, система ДОЛЖНА (SHALL) сохранить для него machine-readable `failed` или `skipped` outcome с причиной.

Система НЕ ДОЛЖНА (SHALL NOT) трактовать такой scope как успешно запущенный.

#### Scenario: Один scope блокируется policy gate, остальные продолжают fan-out
- **GIVEN** operator launch snapshot содержит несколько ИБ
- **AND** для `db-2/item` effective policy запрещает выбранный `mode`
- **WHEN** fan-out запускает child scope
- **THEN** launch item для `db-2/item` получает `failed` outcome с machine-readable причиной
- **AND** остальные scope продолжают fan-out по обычному path
- **AND** aggregate launch history отражает смешанный результат без silent overwrite
