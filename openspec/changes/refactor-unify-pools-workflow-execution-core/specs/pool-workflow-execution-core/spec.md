## ADDED Requirements
### Requirement: Pool runs MUST исполняться через workflow execution runtime
Система ДОЛЖНА (SHALL) выполнять `Pool Run` через единый workflow runtime, который отвечает за lifecycle, enqueue, retry, audit и step orchestration.

`pools` НЕ ДОЛЖЕН (SHALL NOT) иметь отдельный независимый runtime lifecycle для исполнения run-ов.

#### Scenario: Запуск unsafe pool run создаёт и запускает workflow run
- **GIVEN** пользователь инициирует запуск `/api/v2/pools/runs`
- **AND** run запрошен в режиме `unsafe`
- **WHEN** система принимает валидный запрос
- **THEN** создаётся workflow run как фактическая единица исполнения
- **AND** pool run хранит reference на соответствующий workflow run
- **AND** публикационные шаги enqueue без ручного подтверждения

#### Scenario: Запуск safe pool run создаёт workflow run без старта публикации
- **GIVEN** пользователь инициирует запуск `/api/v2/pools/runs`
- **AND** run запрошен в режиме `safe`
- **WHEN** система принимает валидный запрос
- **THEN** создаётся workflow run с `approval_required=true` и `approval_state=preparing`
- **AND** выполняются pre-publish шаги до ручного решения оператора
- **AND** после завершения pre-publish run переходит в `approval_state=awaiting_approval`
- **AND** публикационные шаги НЕ запускаются до явной команды подтверждения

### Requirement: Safe mode MUST иметь явный approval gate
Система ДОЛЖНА (SHALL) поддерживать явные команды фасада для безопасного режима:
- `confirm-publication` — разрешает переход к публикационным шагам;
- `abort-publication` — завершает исполнение без публикации.

Система ДОЛЖНА (SHALL) завершать pre-publish этап (`prepare_input`, `distribution_calculation`, `reconciliation_report`) до ожидания ручного решения в `safe` режиме.

Система ДОЛЖНА (SHALL) фиксировать фазу safe-flow через `approval_state`:
- `preparing` — pre-publish этап ещё выполняется;
- `awaiting_approval` — pre-publish завершён, run ожидает ручное решение;
- `approved` — подтверждение публикации получено;
- `not_required` — для `unsafe` режима.

#### Scenario: Подтверждение публикации переводит safe run в очередь исполнения
- **GIVEN** pool run находится в `safe` режиме и ожидает подтверждения
- **WHEN** оператор отправляет команду `confirm-publication`
- **THEN** publication step enqueue в workflow runtime
- **AND** run переходит из `validated` (`awaiting_approval`) в `validated` (`queued`) или `publishing` по факту выполнения

#### Scenario: Отмена публикации завершает safe run как failed
- **GIVEN** pool run находится в `safe` режиме и ожидает подтверждения
- **WHEN** оператор отправляет команду `abort-publication`
- **THEN** связанный workflow run помечается `cancelled`
- **AND** facade проецирует итоговый pool status как `failed`

#### Scenario: Safe run предоставляет pre-publish диагностику до подтверждения
- **GIVEN** run запущен в `safe` режиме
- **WHEN** pre-publish этап завершён
- **THEN** оператор получает diagnostics/артефакты проверки до публикации
- **AND** `publication_odata` не enqueue до `confirm-publication`

#### Scenario: Во время pre-publish safe run проецируется как validated preparing
- **GIVEN** run запущен в `safe` режиме
- **AND** pre-publish шаги ещё выполняются
- **WHEN** клиент запрашивает детали run
- **THEN** фасад возвращает статус `validated`
- **AND** поле `status_reason` равно `preparing`

### Requirement: Safe commands MUST быть выражены явными идемпотентными API-операциями
Система ДОЛЖНА (SHALL) поддерживать команды безопасного режима как отдельные endpoint'ы:
- `POST /api/v2/pools/runs/{run_id}/confirm-publication`;
- `POST /api/v2/pools/runs/{run_id}/abort-publication`.

Повторный вызов команды в том же run-state ДОЛЖЕН (SHALL) быть идемпотентным и НЕ ДОЛЖЕН (SHALL NOT) вызывать duplicate enqueue.

#### Scenario: Повторный confirm не создаёт дублирующий enqueue
- **GIVEN** `confirm-publication` уже успешно выполнен для `safe` run
- **WHEN** оператор повторно вызывает `confirm-publication`
- **THEN** состояние run не расходится с предыдущим результатом
- **AND** дополнительная публикационная задача не ставится в очередь повторно

#### Scenario: Команда на terminal run отклоняется бизнес-ошибкой
- **GIVEN** run уже находится в terminal status (`published`, `partial_success` или `failed`)
- **WHEN** оператор вызывает `confirm-publication` или `abort-publication`
- **THEN** система возвращает business conflict
- **AND** состояние run не изменяется

#### Scenario: Abort после старта publication_odata отклоняется бизнес-ошибкой
- **GIVEN** `publication_odata` уже начал исполнение
- **WHEN** оператор вызывает `abort-publication`
- **THEN** система возвращает business conflict
- **AND** состояние run не изменяется

### Requirement: Pool status projection MUST быть канонической и детерминированной
Система ДОЛЖНА (SHALL) использовать единый mapping статусов между workflow runtime и pools facade:
- `pool:draft` — только до создания workflow run;
- `workflow:(pending|running) + approval_required=true + approved_at is null + approval_state=preparing -> pool:validated` с `status_reason=preparing`;
- `workflow:pending + approval_required=true + approved_at is null + approval_state=awaiting_approval -> pool:validated` с `status_reason=awaiting_approval`;
- `workflow:pending + (approval_required=false OR approved_at is not null) -> pool:validated` с `status_reason=queued`;
- `workflow:running + (approval_required=false OR approved_at is not null) -> pool:publishing`;
- `workflow:completed + failed_targets=0 -> pool:published`;
- `workflow:completed + failed_targets>0 -> pool:partial_success`;
- `workflow:failed|cancelled -> pool:failed`.

Система ДОЛЖНА (SHALL) использовать `status_reason` только для `pool:validated` с допустимыми значениями `preparing|awaiting_approval|queued`; для остальных pool-статусов `status_reason` ДОЛЖЕН (SHALL) быть `null`.

#### Scenario: Завершение workflow с failed targets даёт partial_success
- **GIVEN** workflow run завершён со статусом `completed`
- **AND** publication summary содержит failed targets
- **WHEN** клиент запрашивает pool run details
- **THEN** фасад возвращает статус `partial_success`
- **AND** в ответе остаётся ссылка на исходный workflow run

#### Scenario: Pending workflow с approval_required проецируется как validated awaiting_approval
- **GIVEN** workflow run создан со статусом `pending`
- **AND** `approval_required=true`
- **AND** `approval_state=awaiting_approval`
- **AND** подтверждение публикации ещё не получено
- **WHEN** клиент запрашивает pool run details
- **THEN** фасад возвращает статус `validated`
- **AND** поле `status_reason` равно `awaiting_approval`

#### Scenario: Safe pre-publish в running проецируется как validated preparing
- **GIVEN** workflow run находится в состоянии `running`
- **AND** `approval_required=true`
- **AND** `approved_at is null`
- **AND** `approval_state=preparing`
- **WHEN** клиент запрашивает pool run details
- **THEN** фасад возвращает статус `validated`
- **AND** поле `status_reason` равно `preparing`

#### Scenario: Для non-validated статусов status_reason отсутствует
- **GIVEN** workflow run находится в состоянии `running`
- **AND** (`approval_required=false` ИЛИ `approved_at is not null`)
- **WHEN** клиент запрашивает pool run details
- **THEN** фасад возвращает статус `publishing`
- **AND** `status_reason` равен `null`

### Requirement: Safe-flow state machine MUST исключать архитектурно неоднозначные проекции
Система ДОЛЖНА (SHALL) обеспечивать инварианты safe/unsafe state machine:
- при `approval_required=true` и `approved_at is null` фасад НЕ ДОЛЖЕН (SHALL NOT) проецировать статус `publishing`;
- `publishing` допустим только когда `approval_required=false` ИЛИ `approved_at is not null`;
- `abort-publication` после старта шага `publication_odata` ДОЛЖЕН (SHALL) возвращать business conflict без изменения состояния.

#### Scenario: Safe run без подтверждения не может быть publishing
- **GIVEN** run находится в `safe` режиме
- **AND** `approval_required=true`
- **AND** `approved_at is null`
- **WHEN** клиент запрашивает детали run
- **THEN** фасад НЕ возвращает статус `publishing`
- **AND** run остаётся в `validated` с `status_reason=preparing` или `status_reason=awaiting_approval`

#### Scenario: Unsafe running run проецируется как publishing без approval ожидания
- **GIVEN** run запущен в `unsafe` режиме
- **AND** workflow run находится в состоянии `running`
- **WHEN** клиент запрашивает детали run
- **THEN** фасад возвращает статус `publishing`
- **AND** `status_reason` равен `null`

### Requirement: Tenant boundary MUST сохраняться между pool и workflow run
Система ДОЛЖНА (SHALL) обеспечивать tenant-изоляцию при запуске, чтении и retry:
- `pool_run.tenant_id` и `workflow_execution.tenant_id` обязаны совпадать;
- доступ к связанному workflow run из другого tenant-контекста НЕ ДОЛЖЕН (SHALL NOT) быть возможен.

#### Scenario: Cross-tenant доступ к workflow provenance отклоняется
- **GIVEN** pool run создан в tenant `A`
- **WHEN** пользователь tenant `B` запрашивает детали этого run
- **THEN** система отклоняет запрос как недоступный в текущем tenant context
- **AND** данные workflow provenance не раскрываются

### Requirement: Workflow tenant model MUST быть совместим с multi-consumer runtime
Система ДОЛЖНА (SHALL) расширить `WorkflowExecution` полями `tenant_id` и `execution_consumer`.

Для `execution_consumer=pools` поле `tenant_id` ДОЛЖНО (SHALL) быть обязательным.

Для historical/non-tenant consumers поле `tenant_id` МОЖЕТ (MAY) быть `null` до завершения их миграции.

#### Scenario: Non-pools consumer может существовать без tenant_id на переходном этапе
- **GIVEN** workflow run принадлежит consumer, отличному от `pools`
- **WHEN** запись создана до tenant-миграции этого consumer
- **THEN** `tenant_id` может быть `null` без нарушения контракта pools
- **AND** pools tenant-check не ослабляется

### Requirement: Import templates и execution plan MUST быть разделены терминологически и технически
Система ДОЛЖНА (SHALL) использовать разделённые сущности:
- `PoolImportSchemaTemplate` как execution-core термин для доменного шаблона импорта (`PoolSchemaTemplate` из foundation change);
- `PoolExecutionPlan` как runtime artifact, полученный компилятором для workflow graph.

Система ДОЛЖНА (SHALL) иметь детерминированный compiler `PoolImportSchemaTemplate + run_context -> PoolExecutionPlan`.

Система ДОЛЖНА (SHALL) трактовать foundation-поле `workflow_binding` на import template как optional compiler hint и НЕ ДОЛЖНА (SHALL NOT) трактовать его как отдельный runtime execution-template.

#### Scenario: Одинаковый pool template компилируется детерминированно
- **GIVEN** одинаковые версия import template, входные параметры, период и `source_hash`
- **WHEN** выполняется компиляция execution plan
- **THEN** структура workflow graph и binding mapping совпадают
- **AND** runtime provenance может быть воспроизведён для диагностики

#### Scenario: Legacy template с workflow_binding остаётся совместимым
- **GIVEN** import template был создан в foundation-change и содержит `workflow_binding`
- **WHEN** запускается unified execution
- **THEN** template принимается без изменения публичного API
- **AND** `workflow_binding` используется только как hint для compiler

### Requirement: Pools API MUST предоставлять domain facade над workflow run
Система ДОЛЖНА (SHALL) сохранять `pools/runs*` как доменный API, но статус, retries и diagnostics ДОЛЖНЫ (SHALL) проецироваться из workflow runtime.

Ответы facade ДОЛЖНЫ (SHALL) содержать provenance block минимум с полями:
- `workflow_run_id` (root execution chain id),
- `workflow_status` (статус active attempt),
- `execution_backend`,
- `retry_chain`.

Для unified execution `retry_chain` ДОЛЖЕН (SHALL) содержать минимум initial attempt и хранить lineage попыток (минимум `workflow_run_id`, `parent_workflow_run_id`, `attempt_number`, `attempt_kind`, `status`).

Для historical run без workflow linkage provenance block ДОЛЖЕН (SHALL) оставаться совместимым:
- `workflow_run_id=null`,
- `workflow_status=null`,
- `execution_backend=legacy_pool_runtime`,
- `retry_chain=[]` (или фактическая legacy цепочка, если доступна),
- `legacy_reference` (nullable, при наличии).

#### Scenario: Pool details отражает workflow provenance
- **GIVEN** pool run связан с workflow run
- **WHEN** клиент запрашивает детали run
- **THEN** ответ содержит pool-доменные поля
- **AND** включает workflow provenance/diagnostics, достаточные для оператора

#### Scenario: Historical pool run возвращает совместимый legacy provenance
- **GIVEN** run создан до unified execution и не имеет workflow linkage
- **WHEN** клиент запрашивает детали run
- **THEN** API возвращает provenance block с `execution_backend=legacy_pool_runtime`
- **AND** `workflow_run_id` и `workflow_status` равны `null`

#### Scenario: Retry lineage отражает root и активную попытку
- **GIVEN** run был перезапущен через retry endpoint и имеет несколько workflow попыток
- **WHEN** клиент запрашивает детали run
- **THEN** `workflow_run_id` указывает на initial/root workflow run
- **AND** `workflow_status` соответствует последней (active) попытке в `retry_chain`

### Requirement: OData publication MUST исполняться как workflow step adapter
Система ДОЛЖНА (SHALL) вызывать publication service (OData) как шаг workflow execution graph, а не как отдельный orchestrator runtime.

#### Scenario: Ошибка публикации обрабатывается политикой retry workflow
- **GIVEN** шаг публикации в OData завершился транспортной ошибкой
- **WHEN** workflow runtime применяет retry policy
- **THEN** повторяются только failed step-attempts
- **AND** статусы pool run и workflow run остаются согласованными

### Requirement: OData external document identity MUST использовать strategy-based resolver
Система ДОЛЖНА (SHALL) поддерживать strategy-based resolver идентификатора внешнего документа:
- primary strategy: стабильный GUID (`_IDRRef` или `Ref_Key`);
- fallback strategy: детерминированный `ExternalRunKey` (`runkey-<sha256[:32]>` от `run_id + target_database_id + document_kind + period`).

Система ДОЛЖНА (SHALL) сохранять выбранную стратегию и итоговый идентификатор в audit/provenance.

#### Scenario: GUID недоступен, применяется fallback стратегия
- **GIVEN** целевая конфигурация не возвращает стабильный GUID
- **WHEN** выполняется публикация
- **THEN** система использует `ExternalRunKey`
- **AND** фиксирует fallback-стратегию в audit/provenance

### Requirement: OData diagnostics MUST иметь фиксированный набор полей
Система ДОЛЖНА (SHALL) сохранять и возвращать по каждой попытке публикации минимум:
- `target_database_id`,
- `payload_summary`,
- `http_error` или `transport_error`,
- `domain_error_code`,
- `domain_error_message`,
- `attempt_number`,
- `attempt_timestamp`.

#### Scenario: Оператор получает полную диагностику failed-попытки
- **GIVEN** run содержит failed-попытки публикации
- **WHEN** оператор запрашивает детализацию run
- **THEN** в ответе присутствуют канонические diagnostic fields для каждой failed-попытки
- **AND** данных достаточно для решения о retry

### Requirement: Publication retry contract MUST быть единым для pools и workflow runtime
Система ДОЛЖНА (SHALL) поддерживать доменный контракт `max_attempts_total=5` (включая initial attempt) для публикации в OData.

Контракт ДОЛЖЕН (SHALL) быть семантически эквивалентен foundation-формулировке `max_attempts=5`.

Система ДОЛЖНА (SHALL) поддерживать `retry_interval_seconds` как конфигурируемый параметр, при этом эффективный интервал НЕ ДОЛЖЕН (SHALL NOT) превышать 120 секунд.

Система ДОЛЖНА (SHALL) исполнять retry endpoint `POST /api/v2/pools/runs/{run_id}/retry` только для failed subset, не дублируя успешные цели.

#### Scenario: Retry повторно исполняет только failed subset
- **GIVEN** pool run имеет `partial_success` и набор failed targets
- **WHEN** клиент вызывает retry endpoint
- **THEN** система создаёт/запускает workflow execution только для failed subset
- **AND** успешные публикации из предыдущих попыток не повторяются

#### Scenario: Конфигурация retry интервала выше лимита ограничивается
- **GIVEN** для run задан `retry_interval_seconds` выше 120 секунд
- **WHEN** runtime формирует retry policy
- **THEN** эффективный интервал устанавливается не выше 120 секунд
- **AND** это значение отражается в runtime metadata

### Requirement: Queueing contract MUST быть фиксирован для phase 1
Система ДОЛЖНА (SHALL) отправлять workflow execution для pools в существующий workflow stream `commands:worker:workflows` с приоритетом `normal` по умолчанию.

Система НЕ ДОЛЖНА (SHALL NOT) вводить отдельный SLA/priority lane для pools в рамках этого change.

#### Scenario: Pool run enqueue использует workflow stream phase 1
- **WHEN** запускается pool run через unified execution core
- **THEN** enqueue выполняется в workflow stream `commands:worker:workflows`
- **AND** execution config использует приоритет `normal`, если явно не задано иначе в будущем extension

#### Scenario: Safe run enqueue publication шага выполняется только после confirm-publication
- **GIVEN** run запущен в `safe` режиме
- **AND** подтверждение ещё не выполнено
- **WHEN** оператор запрашивает состояние очереди
- **THEN** publication step отсутствует в worker queue
- **AND** pre-publish шаги могут быть уже выполнены или находиться в обработке
- **AND** после `confirm-publication` publication step enqueue в `commands:worker:workflows`

### Requirement: Migration MUST сохранять historical runs и идемпотентность
Система ДОЛЖНА (SHALL) обеспечить миграцию/совместимость, при которой historical pool runs остаются читаемыми, а доменный idempotency key продолжает предотвращать дубли исполнения.

#### Scenario: Historical run читается после включения unified execution
- **GIVEN** run был создан до перевода исполнения на workflow runtime
- **WHEN** оператор открывает run details после релиза
- **THEN** система возвращает совместимое представление run
- **AND** audit/provenance остаются доступными

#### Scenario: Идемпотентный ключ сохраняет поведение после перевода на workflow runtime
- **GIVEN** существует run с ключом `pool_id + period + direction + source_hash`
- **WHEN** пользователь повторно инициирует запуск с тем же ключом
- **THEN** система выполняет upsert существующего набора результатов
- **AND** дубликаты документов/публикаций не создаются

### Requirement: Runtime source-of-truth MUST быть единым между change-ами
Система ДОЛЖНА (SHALL) трактовать runtime-семантику `pool-distribution-runs` и `pool-odata-publication` через требования этого capability.

Foundation change `add-intercompany-pool-distribution-module` ДОЛЖЕН (SHALL) использоваться как источник domain vocabulary, но НЕ ДОЛЖЕН (SHALL NOT) переопределять execution-правила после принятия этого change.

#### Scenario: Конфликт интерпретаций runtime разрешается в пользу execution-core spec
- **GIVEN** в foundation change и execution-core change есть различающиеся формулировки runtime-поведения
- **WHEN** команда реализует исполнение `pools/runs*`
- **THEN** runtime реализуется по требованиям `pool-workflow-execution-core`
- **AND** foundation change используется только для доменных терминов и baseline API surface

### Requirement: Workflows decommission MUST быть запрещён до полной миграции consumers
Система НЕ ДОЛЖНА (SHALL NOT) удалять `workflows` runtime до подтверждённой миграции всех потребителей execution-core (включая pools) на общий контракт исполнения.

Система ДОЛЖНА (SHALL) выполнять decommission preflight на основе реестра consumers (`execution_consumers_registry`) и блокировать удаление при наличии хотя бы одного `migrated=false`.

#### Scenario: Попытка удаления workflows блокируется preflight-проверкой
- **GIVEN** не все execution consumers мигрированы на unified execution core
- **WHEN** запускается decommission plan для workflows
- **THEN** preflight проверка помечает план как `No-Go`
- **AND** удаление runtime не выполняется

#### Scenario: Decommission разрешается только после полного статуса migrated=true
- **GIVEN** preflight читает `execution_consumers_registry`
- **AND** каждый consumer имеет `migrated=true`
- **WHEN** запускается decommission plan
- **THEN** preflight возвращает `Go`
- **AND** удаление runtime может быть выполнено в штатной процедуре
