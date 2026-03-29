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

Primary production read path ДОЛЖЕН (SHALL) использовать только поддерживаемые published integration surfaces 1С: standard OData entities/functions/virtual tables или явный published HTTP service contract. Система НЕ ДОЛЖНА (SHALL NOT) использовать прямой доступ к таблицам БД ИБ как основной путь factual sync в production.

#### Scenario: Ручная правка в 1С меняет factual projection
- **GIVEN** после публикации run пользователь вручную создаёт или изменяет документ в 1С
- **WHEN** worker sync повторно читает документы и регистры ИБ
- **THEN** centralized projection отражает новое фактическое состояние
- **AND** не сохраняет устаревшее "ожидаемое" значение только из distribution artifact

#### Scenario: Worker sync читает bounded slice бухгалтерских данных
- **GIVEN** для пула известны организации, квартал и счета отчёта `Продажи`
- **WHEN** `read worker` обновляет factual projection
- **THEN** он читает только bounded slice бухгалтерских источников, необходимых для этого пула/квартала
- **AND** не требует отдельного extension/change-log в первой итерации
- **AND** использует поддерживаемую published integration surface 1С, а не прямой доступ к таблицам БД ИБ

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

Для reachable ИБ система ДОЛЖНА (SHALL) стремиться поддерживать freshness projection не хуже 2 минут. При недоступности ИБ, maintenance window или блокировке внешних сеансов система ДОЛЖНА (SHALL) показывать staleness/freshness metadata вместо silent freeze.

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
