# pool-factual-balance-monitoring Specification

## Purpose
Определяет bounded factual sync, materialized balance projection, operator workspace и manual review queue для контроля фактических остатков по пулу и кварталу.
## Requirements
### Requirement: Variant B architecture MUST разделять factual monitoring на три изолированные подсистемы внутри текущих runtime boundaries
Система ДОЛЖНА (SHALL) реализовывать этот change внутри текущих `frontend -> api-gateway -> orchestrator -> worker -> 1C` boundaries без нового top-level service, нового primary runtime или отдельного frontend app.

Внутри этих границ система ДОЛЖНА (SHALL) иметь три изолированные подсистемы:

- `intake subsystem` для canonical `PoolBatch`, schema-driven normalization, provenance и batch-backed run kickoff;
- `factual read/projection subsystem` для bounded чтения published 1C surfaces, freshness tracking и materialized projection / batch settlement;
- `reconcile/review subsystem` для `unattributed`, `late correction` и operator actions поверх factual read model.

Система НЕ ДОЛЖНА (SHALL NOT):

- использовать `/pools/runs` как primary workspace factual monitoring и manual review;
- смешивать execution snapshots/read-models с factual aggregate store;
- отключать `intake subsystem` автоматически только из-за backlog/staleness в `factual read/projection` или `reconcile/review`.

#### Scenario: Backlog factual sync не блокирует batch intake
- **GIVEN** `factual read/projection subsystem` отстаёт по freshness и подняла backlog/staleness сигнал
- **WHEN** оператор загружает новый `receipt` batch
- **THEN** `intake subsystem` остаётся доступной в рамках своего контракта
- **AND** система явно показывает staleness/backlog в factual context
- **AND** run execution contract не подменяется состоянием factual sync

### Requirement: Factual balance projection MUST использовать реальные документы и регистры ИБ как source of truth
Система ДОЛЖНА (SHALL) строить factual balance projection по реальным документам и регистрам ИБ, а не по ожидаемым суммам из runtime distribution artifacts.

В первой итерации бухгалтерским эталоном ДОЛЖЕН (SHALL) считаться отчёт `Продажи`, построенный на bounded чтении `РегистрБухгалтерии.Хозрасчетный.Обороты(...)`, `РегистрСведений.ДанныеПервичныхДокументов` и связанных документов `РеализацияТоваровУслуг`, `ВозвратТоваровОтПокупателя`, `КорректировкаРеализации`.

Projection ДОЛЖЕН (SHALL) хранить как минимум три денежные меры:
- `amount_with_vat`
- `amount_without_vat`
- `vat_amount`

Projection ДОЛЖЕН (SHALL) учитывать как документы, созданные Command Center, так и ручные документы пользователя, если они влияют на фактический баланс и доступны для чтения из ИБ.

Primary sync path НЕ ДОЛЖЕН (SHALL NOT) выполнять unbounded full scan всего бухгалтерского регистра; worker sync ДОЛЖЕН (SHALL) ограничивать чтение организациями пула, кварталом и счетами/типами движений, используемыми отчётом `Продажи`.

Bounded account subset ДОЛЖЕН (SHALL) резолвиться через first-class quarter-scoped factual scope selection, keyed by `pool + source_profile + quarter_start`, которая pin-ит одну published revision canonical `GLAccountSet` и её member `GLAccount` bindings, а не через hardcoded account codes в runtime defaults.

Live lookup target chart-of-accounts ДОЛЖЕН (SHALL) использоваться только в readiness/preflight path для materialize или verify `resolved_bindings` snapshot выбранной pinned revision. Worker execution и replay artifact с `factual_scope_contract.v2` НЕ ДОЛЖНЫ (SHALL NOT) silently подменять этот snapshot latest live lookup.

Primary production read path ДОЛЖЕН (SHALL) использовать только поддерживаемые published integration surfaces 1С: standard OData entities/functions/virtual tables или явный published HTTP service contract. Система НЕ ДОЛЖНА (SHALL NOT) использовать прямой доступ к таблицам БД ИБ как основной путь factual sync в production.

#### Scenario: Worker sync читает bounded slice через canonical GLAccountSet
- **GIVEN** для пула известны организации, квартал и pinned revision selected `GLAccountSet`, соответствующий отчёту `Продажи`
- **WHEN** `read worker` обновляет factual projection
- **THEN** он резолвит target account refs через member `GLAccount` bindings этого набора
- **AND** не использует hardcoded runtime constants как source-of-truth для bounded account scope

#### Scenario: Workspace, scheduler и preflight используют один selector для того же квартала
- **GIVEN** workspace default sync, scheduler и preflight работают с одним `pool + source_profile + quarter_start`
- **WHEN** каждый из них резолвит bounded factual account scope
- **THEN** все они используют один и тот же quarter-scoped factual scope selection record
- **AND** фиксируют одну и ту же published `GLAccountSet` revision до явного repin

### Requirement: Factual balance projection MUST материализовать баланс по пулу, ребру, организации, кварталу и batch
Система ДОЛЖНА (SHALL) поддерживать materialized read model не менее чем по измерениям:

- `pool`
- `organization`
- `edge`
- `quarter`
- `batch`

Projection ДОЛЖЕН (SHALL) хранить derived показатели:

- `incoming_amount`
- `outgoing_amount`
- `open_balance`

Для operator-facing semantics система ДОЛЖНА (SHALL) вычислять отдельный batch settlement status, независимый от `PoolRun.status`, включая как минимум:

- `ingested`
- `distributed`
- `partially_closed`
- `closed`
- `carried_forward`
- `attention_required`

#### Scenario: Published run остаётся execution-success, но batch имеет незакрытый остаток
- **GIVEN** связанный `PoolRun` завершился в `published`
- **AND** на leaf-узлах остался ненулевой factual balance
- **WHEN** projection пересчитывает batch settlement
- **THEN** execution status run остаётся `published`
- **AND** batch settlement status отображается как `partially_closed` или `attention_required`

### Requirement: Monitoring MUST предоставлять near-real-time summary и drill-down по factual balance

Система ДОЛЖНА (SHALL) предоставлять операторский summary/drill-down по factual balance, достаточный для ответа на вопросы:

- сколько вошло в пул;
- сколько прошло по каждому ребру;
- где сумма застряла;
- сколько уже закрыто фактическими реализациями;
- какой остаток переносится в следующий квартал.

Operator-facing factual workspace ДОЛЖЕН (SHALL) показывать эти ответы через primary UI surface, а не требовать raw JSON inspection или ручного сопоставления backend payload.

Для этого batch settlement и edge drill-down ДОЛЖНЫ (SHALL) как минимум отображать:
- `incoming_amount`;
- `outgoing_amount`;
- `open_balance`;
- carry-forward context для batch/status `carried_forward`, включая target quarter и source/target linkage, достаточные для операторского анализа.

Для reachable ИБ система ДОЛЖНА (SHALL) стремиться поддерживать freshness projection не хуже 2 минут. При недоступности ИБ, maintenance window или блокировке внешних сеансов система ДОЛЖНА (SHALL) показывать staleness/freshness metadata вместо silent freeze.

#### Scenario: Бухгалтер видит закрытую часть и carry-forward без raw JSON inspection
- **GIVEN** batch частично закрыт или переведён в `carried_forward`
- **WHEN** бухгалтер открывает centralized factual dashboard
- **THEN** factual workspace показывает `incoming_amount`, `outgoing_amount` и `open_balance` на operator-facing batch/edge drill-down
- **AND** при carry-forward оператор видит target quarter и linkage на source/target factual context
- **AND** ему не нужно читать raw metadata JSON, чтобы понять сколько уже закрыто и куда перенесён остаток

#### Scenario: Бухгалтер видит, где сумма застряла, без открытия каждой ИБ
- **GIVEN** несколько узлов и рёбер пула имеют ненулевой `open_balance`
- **WHEN** бухгалтер открывает centralized balance dashboard
- **THEN** summary показывает проблемные pool/org/edge с их остатками
- **AND** drill-down раскрывает batch и квартальный контекст без перехода в каждую ИБ вручную

### Requirement: Factual monitoring workspace MUST следовать UI platform governance и не превращаться в table-first master pane
Система ДОЛЖНА (SHALL) реализовывать operator-facing factual workspace через project UI platform layer, а не через raw page-level vendor composition как primary path.

Если factual workspace использует `MasterDetail` или иной catalog/detail shell, система ДОЛЖНА (SHALL):

- держать master pane как compact selection surface;
- НЕ ДОЛЖНА (SHALL NOT) использовать wide data grid или table toolkit как default primary composition path в master pane;
- выносить wide tables, плотные diagnostics и bulk-heavy operational density в detail pane, dedicated secondary surface или explicit full-width workspace, если это оправдано операторским сценарием;
- обеспечивать mobile-safe fallback для detail/review через `Drawer`, off-canvas panel или route/state fallback;
- НЕ ДОЛЖНА (SHALL NOT) делать page-wide или pane-wide horizontal overflow штатным режимом работы.

#### Scenario: Desktop factual workspace сохраняет compact selection/detail split
- **GIVEN** оператор открывает factual monitoring route на desktop viewport
- **WHEN** route использует catalog/detail композицию
- **THEN** primary selection context остаётся scan-friendly и компактным
- **AND** route не помещает wide table с horizontal overflow в master pane как default primary path

#### Scenario: Narrow viewport открывает factual detail без горизонтального скролла
- **GIVEN** оператор открывает factual monitoring route на narrow viewport
- **WHEN** он выбирает batch, edge или review item для просмотра detail
- **THEN** detail/review открывается через mobile-safe fallback (`Drawer`, off-canvas panel или route/state fallback)
- **AND** страница не требует horizontal overflow как основной режим взаимодействия

### Requirement: Command Center documents MUST писать machine-readable traceability marker в комментарий
Система ДОЛЖНА (SHALL) для документов, создаваемых Command Center, записывать в начало комментария machine-readable marker формата:

`CCPOOL:v=1;pool=<uuid>;run=<uuid|->;batch=<uuid|->;org=<uuid>;q=<YYYYQn>;kind=<receipt|sale|carry|manual>||<optional human text>`

Система ДОЛЖНА (SHALL):

- использовать фиксированный порядок ключей и ASCII-формат marker-блока;
- трактовать `pool` как обязательный ключ для attribution, в том числе когда одна организация участвует в нескольких пулах одного квартала;
- записывать marker как prefix comment field до публикации документа и сохранять human-readable хвост после `||`, если он был передан в policy/template/operator input;
- сохранять machine-readable блок стабильным для retry/update того же логического документа;
- считать всё, что расположено правее `||`, human-readable хвостом и игнорировать при парсинге.

Документ без валидного marker-блока НЕ ДОЛЖЕН (SHALL NOT) автоматически привязываться к конкретному pool/batch.

#### Scenario: Документ Command Center публикуется с machine-readable marker
- **GIVEN** Command Center создаёт документ по batch-backed run или closing sale
- **WHEN** документ записывается в ИБ
- **THEN** комментарий документа начинается с валидного `CCPOOL:v=1;...` marker-блока
- **AND** marker содержит `pool`, достаточный для различения нескольких пулов одной организации в одном квартале

#### Scenario: Retry публикации не меняет machine-readable часть marker
- **GIVEN** документ Command Center уже был сформирован с валидным `CCPOOL:v=1;...` marker-блоком
- **WHEN** runtime выполняет retry или update того же логического документа
- **THEN** machine-readable часть marker остаётся семантически той же
- **AND** human-readable хвост после `||` не теряется silently

### Requirement: Незакрытый остаток MUST переноситься на тот же узел следующего квартала
Система ДОЛЖНА (SHALL) переносить незакрытый factual balance на тот же узел в следующий квартал, пока он не будет закрыт фактической реализацией.

Система НЕ ДОЛЖНА (SHALL NOT) автоматически возвращать такой остаток вверх по topology без отдельной закрывающей операции, признанной доменной моделью.

#### Scenario: Ненулевой остаток на leaf-узле переносится в новый квартал
- **GIVEN** на конец квартала у leaf-узла есть ненулевой `open_balance`
- **WHEN** начинается следующий квартал и projection выполняет carry-forward
- **THEN** остаток появляется как входящий баланс того же узла в новом квартале
- **AND** исторический остаток предыдущего квартала остаётся прослеживаемым

### Requirement: Документы без traceability MUST учитываться как unattributed и требовать явной разметки
Система ДОЛЖНА (SHALL) собирать документы, влияющие на factual balance, но не несущие валидной traceability через machine-readable comment marker, в отдельную `unattributed` operator-facing очередь.

Такие документы ДОЛЖНЫ (SHALL) влиять на factual totals организации/квартала, но НЕ ДОЛЖНЫ (SHALL NOT) silently привязываться к конкретному pool edge или batch до явной пользовательской разметки.

#### Scenario: Ручная реализация без валидного marker видна в projection и review queue
- **GIVEN** пользователь вручную создаёт реализацию в 1С без traceability marker
- **WHEN** worker sync читает ИБ
- **THEN** сумма попадает в factual totals организации/квартала
- **AND** документ отображается в `unattributed` queue для последующей разметки

### Requirement: Поздние корректировки после фиксации квартала MUST требовать manual reconcile
Система ДОЛЖНА (SHALL) считать квартал `frozen` после расчёта и фиксации carry-forward по `pool + quarter`.

Если после фиксации появляется документ или изменение, влияющее на factual balance закрытого квартала, система ДОЛЖНА (SHALL):

- поднять `attention_required` сигнал;
- показать operator-facing запись для manual reconcile;
- сохранить delta как late correction.

Система НЕ ДОЛЖНА (SHALL NOT) silently пересчитывать исторический квартал и carry-forward следующего квартала.

#### Scenario: Поздняя корректировка не переписывает зафиксированный carry-forward
- **GIVEN** по пулу и кварталу уже зафиксирован carry-forward
- **AND** позже в ИБ появляется документ, влияющий на этот квартал
- **WHEN** `read worker` обнаруживает изменение
- **THEN** projection помечает late correction как `attention_required`
- **AND** historical quarter и следующий carry-forward не меняются автоматически

### Requirement: Factual preflight MUST fail-closed на incomplete reusable account coverage до worker execution
Система ДОЛЖНА (SHALL) до старта factual worker execution проверять coverage selected `GLAccountSet` по каждой target ИБ и возвращать machine-readable blocker, если хотя бы один required account не имеет валидного binding в target chart of accounts.

Система НЕ ДОЛЖНА (SHALL NOT) откладывать такую несовместимость до глубокой OData ошибки внутри running worker, если её можно детерминированно обнаружить в preflight/readiness path.

При наличии selected pinned revision readiness path ДОЛЖЕН (SHALL) materialize или verify target-specific `resolved_bindings` snapshot до enqueue. Execution artifact с `factual_scope_contract.v2` НЕ ДОЛЖЕН (SHALL NOT) полагаться на последующий implicit live lookup для тех же bindings.

#### Scenario: Missing member binding блокирует factual sync до enqueue
- **GIVEN** selected `GLAccountSet` содержит canonical account, отсутствующий в binding coverage для target ИБ
- **WHEN** factual preflight или default workspace sync проверяет readiness
- **THEN** система завершает проверку fail-closed с machine-readable blocker по `gl_account`
- **AND** factual workflow execution не enqueue'ится

#### Scenario: Preflight материализует pinned resolved_bindings snapshot до enqueue
- **GIVEN** для выбранной pinned `GLAccountSet` revision target ИБ доступна и chart lookup проходит успешно
- **WHEN** factual preflight завершает readiness path
- **THEN** система сохраняет machine-readable `resolved_bindings` snapshot для target ИБ
- **AND** downstream execution использует именно этот snapshot, а не повторный implicit live lookup

### Requirement: Factual runtime artifacts MUST pin `GLAccountSet` revision
Система ДОЛЖНА (SHALL) сохранять в factual preflight results, checkpoints и связанных runtime artifacts first-class machine-readable scope contract, включающий как минимум:
- версию scope contract;
- quarter-scoped selector key, uniquely identifying `pool + source_profile + quarter_start`;
- идентификатор selected `GLAccountSet` profile;
- идентификатор pinned `GLAccountSet` revision;
- effective member snapshot;
- target-specific `resolved_bindings` snapshot;
- stable scope fingerprint, привязанный к selector key, pinned revision, effective members и quarter scope.

Система НЕ ДОЛЖНА (SHALL NOT) silently пересчитывать historical readiness или replay на latest revision profile, если runtime context уже был создан под предыдущую revision.
Система НЕ ДОЛЖНА (SHALL NOT) повторно резолвить latest target bindings для factual artifact, который уже содержит pinned `resolved_bindings`.
Checkpoint metadata, workflow input context, inspect surfaces и enqueue idempotency ДОЛЖНЫ (SHALL) включать `scope_fingerprint`, чтобы `retry same scope` и `new scope for same quarter` были различимы машинно.

#### Scenario: Поздняя правка account set не меняет historical factual checkpoint scope
- **GIVEN** factual checkpoint уже создан с pinned `GLAccountSet` revision
- **WHEN** оператор публикует новую revision того же account set
- **THEN** существующий checkpoint сохраняет ранее pinned revision и effective members
- **AND** historical quarter scope не меняется автоматически только из-за новой latest revision

#### Scenario: Repin revision в том же квартале создаёт новый scope lineage
- **GIVEN** для `pool + source_profile + quarter_start` уже существует factual checkpoint с `scope_fingerprint=A`
- **AND** оператор или system-managed selector repin-ит другую published `GLAccountSet` revision для того же квартала
- **WHEN** runtime запускает новый sync после такого repin
- **THEN** новый readiness/execution path получает другой `scope_fingerprint`
- **AND** система не маскирует этот запуск под retry существующего checkpoint lineage

#### Scenario: Historical replay использует pinned target bindings, даже если current binding уже изменён
- **GIVEN** factual artifact уже содержит `resolved_bindings` snapshot для target ИБ
- **AND** после этого оператор изменил current `GLAccount` binding или target `Ref_Key`
- **WHEN** выполняется historical replay этого artifact
- **THEN** runtime использует pinned `resolved_bindings` snapshot из artifact
- **AND** не пере-резолвит latest binding state для той же target ИБ

#### Scenario: Missing pinned binding snapshot блокирует replay fail-closed
- **GIVEN** factual artifact требует execution по target ИБ, но `resolved_bindings` snapshot отсутствует или неполон
- **WHEN** runtime пытается выполнить replay
- **THEN** выполнение завершается fail-closed с machine-readable blocker
- **AND** система не подменяет отсутствующий snapshot latest binding lookup

### Requirement: Factual scope rollout MUST быть versioned, dual-read и rollback-safe
Система ДОЛЖНА (SHALL) публиковать versioned factual scope contract для bounded account subset, не меняя на bridge-периоде верхнеуровневые runtime envelopes `pool_factual_sync_workflow.v1` и `pool_factual_read_lane.v1`.

Для этого change nested contract `factual_scope_contract.v2` ДОЛЖЕН (SHALL) включать как минимум:
- `selector_key`;
- `gl_account_set_id`;
- `gl_account_set_revision_id`;
- `effective_members`;
- `resolved_bindings`;
- `scope_fingerprint`.

На миграционном мосте система ДОЛЖНА (SHALL) выполнять dual-write:
- nested `factual_scope_contract.v2`;
- legacy compatibility fields `account_codes`, достаточные для старого worker/runtime path.

Worker и orchestrator runtime ДОЛЖНЫ (SHALL) поддерживать dual-read на период cutover: внутри текущих `v1` envelopes предпочитать nested `factual_scope_contract.v2` и его pinned `resolved_bindings`, если они доступны, и корректно обрабатывать legacy artifact, если он был выпущен до cutover или используется при rollback.

Legacy fallback path по `account_codes` и live chart lookup ДОЛЖЕН (SHALL) применяться только к artifact, который не содержит `factual_scope_contract.v2`. Для artifact с nested scope contract система НЕ ДОЛЖНА (SHALL NOT) silently игнорировать `resolved_bindings` или подменять их поздним live lookup.

Система НЕ ДОЛЖНА (SHALL NOT) требовать rebuild historical checkpoints или recompute latest effective members только для того, чтобы пережить rollout/rollback factual scope contract.

#### Scenario: Worker предпочитает nested `factual_scope_contract.v2`, но legacy checkpoint остаётся исполнимым
- **GIVEN** новый factual checkpoint уже содержит nested `factual_scope_contract.v2` и legacy `account_codes` внутри текущего `pool_factual_sync_workflow.v1`
- **WHEN** worker читает runtime artifact после cutover
- **THEN** он использует pinned nested `factual_scope_contract.v2` как source-of-truth
- **AND** legacy fields остаются sufficient fallback для rollback-safe совместимости

#### Scenario: V2 artifact без pinned snapshot не уходит в legacy live fallback
- **GIVEN** factual artifact уже содержит `factual_scope_contract.v2`, но `resolved_bindings` snapshot отсутствует или неполон
- **WHEN** worker или replay runtime пытается его исполнить
- **THEN** выполнение завершается fail-closed
- **AND** runtime не использует legacy `account_codes` path или поздний live chart lookup как silent fallback

#### Scenario: Rollback не требует пересборки historical factual artifacts
- **GIVEN** factual artifacts были выпущены до завершения cutover и содержат только legacy `account_codes` или transitional dual-write payload
- **WHEN** команда выполняет rollback worker/orchestrator runtime
- **THEN** historical replay и inspect остаются выполнимыми без пересборки artifacts
- **AND** runtime не пересчитывает scope из latest `GLAccountSet` revision или runtime defaults

### Requirement: Factual workspace MUST давать operator-facing refresh/retry path для текущего pool и quarter

Система ДОЛЖНА (SHALL) предоставлять в shipped factual workspace явное operator-facing действие для refresh/retry factual sync в контексте конкретного `pool + quarter`.

Этот path ДОЛЖЕН (SHALL):
- работать из standard operator surface без ручного `curl`, `eval-django` или internal-service endpoint knowledge;
- reuse'ить существующий bounded factual sync contract внутри текущих runtime boundaries;
- показывать пользователю machine-readable progress/result state для pending, running, success и failure;
- respect'ить existing checkpoint/idempotency/freshness guardrails, а не enqueue'ить бесконтрольные дубликаты.

Система НЕ ДОЛЖНА (SHALL NOT) считать debug/runbook commands primary operator path для ручного обновления factual сверки.

#### Scenario: Оператор вручную обновляет factual сверку из workspace
- **GIVEN** оператор видит stale factual summary или хочет ускорить refresh для конкретного `pool + quarter`
- **WHEN** он использует shipped refresh/retry control в factual workspace
- **THEN** система запускает bounded factual sync для этого context внутри существующих runtime boundaries
- **AND** UI показывает pending/running/result state без требования ручного REST/debug вызова
- **AND** повторные нажатия не создают бесконтрольные дубликаты, если checkpoint уже находится в `pending` или `running`

### Requirement: Factual rollout cadence MUST активировать declared polling tiers через canonical activity classification

Система ДОЛЖНА (SHALL) использовать declared polling tiers `active`, `warm` и `cold` как реальный runtime contract factual sync, а не только как helper/config definitions.

Для этого система ДОЛЖНА (SHALL):
- принимать canonical activity decision на orchestrator path для factual sync context;
- проводить выбранный tier в workflow contract, checkpoint metadata и observability-facing surfaces;
- использовать `active` cadence для operator-driven/current-quarter factual contexts;
- использовать `warm` cadence для non-active, но ещё operationally relevant open factual contexts;
- использовать `cold` cadence для low-activity contexts, не подменяя им отдельный nightly reconcile path для closed quarter.

Система НЕ ДОЛЖНА (SHALL NOT) держать `warm` tier только в helper constants или unit tests без фактического runtime wiring.

#### Scenario: Scheduler выдаёт warm tier для non-active открытого factual context
- **GIVEN** factual quarter больше не считается active operator context, но по нему остаются открытые settlement или operationally relevant balances
- **WHEN** scheduler-managed factual sync выбирает cadence для этого context
- **THEN** workflow contract и checkpoint metadata получают `polling_tier=warm`
- **AND** effective poll interval соответствует warm cadence
- **AND** runtime не маскирует этот path под `active`

#### Scenario: Workspace request сохраняет active cadence без регрессии nightly reconcile
- **GIVEN** оператор открывает factual workspace для актуального quarter context
- **WHEN** route-triggered default sync или operator-triggered refresh запускает readiness/execution path
- **THEN** factual sync остаётся на `active` cadence с target freshness 2 минуты
- **AND** отдельный closed-quarter reconcile job продолжает существовать независимо от этого path

