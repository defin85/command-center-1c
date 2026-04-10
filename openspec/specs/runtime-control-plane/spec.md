# runtime-control-plane Specification

## Purpose
TBD - created by archiving change add-runtime-control-plane. Update Purpose after archive.
## Requirements
### Requirement: Runtime control catalog MUST expose only allowlisted runtimes and capabilities
Система ДОЛЖНА (SHALL) предоставлять runtime control catalog только для allowlisted runtime instances.

Для каждой runtime instance catalog ДОЛЖЕН (SHALL) описывать:
- stable runtime instance identifier, достаточный для host/provider-aware targeting;
- observed runtime state и health summary;
- supported actions для этого runtime;
- provider/control backend metadata;
- наличие scheduler/job control affordances;
- доступность logs/history surfaces.

Система НЕ ДОЛЖНА (SHALL NOT) представлять unknown runtimes, abstract service classes без достаточной target identity или arbitrary commands как generic control targets.

#### Scenario: Staff operator получает bounded runtime catalog
- **GIVEN** staff пользователь с runtime-control capability запрашивает runtime control catalog
- **WHEN** API формирует ответ
- **THEN** ответ содержит только allowlisted runtime instances и их supported capabilities
- **AND** отсутствуют arbitrary command strings или unknown runtime targets

### Requirement: Runtime actions MUST execute asynchronously with audit trail
Система ДОЛЖНА (SHALL) исполнять imperative runtime actions через async action run contract, а не через long-running synchronous HTTP.

Каждый accepted action run ДОЛЖЕН (SHALL) фиксировать:
- actor;
- explicit reason для dangerous actions;
- target runtime и action type;
- requested/started/finished timestamps;
- terminal status;
- bounded result/output excerpt.

Accepted action run ДОЛЖЕН (SHALL) быть persisted до provider dispatch.

#### Scenario: Restart action возвращает action run и сохраняет terminal outcome
- **GIVEN** staff оператор запрашивает `restart` для `worker-workflows` и передаёт reason
- **WHEN** runtime control API принимает запрос
- **THEN** API отвечает `202 Accepted` и возвращает `action_id` с initial status
- **AND** action history сохраняет actor, reason, target runtime и terminal outcome этого action run

### Requirement: Runtime action completion MUST remain observable for self-targeting lifecycle actions
Система ДОЛЖНА (SHALL) сохранять наблюдаемость terminal outcome даже для lifecycle actions, которые затрагивают runtime, обслуживающий сам dispatch path или provider host path.

Completion такой операции НЕ ДОЛЖЕН (SHALL NOT) зависеть только от живости initiating HTTP request/process.

#### Scenario: Restart orchestrator не теряет terminal outcome action run
- **GIVEN** accepted runtime action перезапускает runtime, через который operator API или provider path инициировал dispatch
- **WHEN** initiating process прерывается из-за этого restart
- **THEN** action run остаётся доступным по `action_id`
- **AND** terminal outcome восстанавливается через detached provider execution или external observation path

### Requirement: Runtime controls MUST enforce dedicated RBAC and destructive-action gating
Система ДОЛЖНА (SHALL) иметь dedicated permission/capability для runtime control surface.

Система ДОЛЖНА (SHALL) скрывать или fail-closed блокировать mutating runtime actions для пользователей без этого доступа.

Dangerous actions ДОЛЖНЫ (SHALL) требовать явный operator intent, включая reason.

#### Scenario: Пользователь без runtime-control capability не может выполнить mutating action
- **GIVEN** аутентифицированный пользователь не имеет runtime-control capability
- **WHEN** он пытается вызвать mutating runtime action
- **THEN** API возвращает forbidden/fail-closed ответ
- **AND** UI остаётся diagnostics-only и не показывает destructive control affordances

### Requirement: Scheduler desired state MUST be controlled independently from process lifecycle
Система ДОЛЖНА (SHALL) управлять scheduler global state и per-job desired state отдельно от lifecycle конкретного runtime process.

Scheduler desired state ДОЛЖЕН (SHALL) поддерживать как минимум:
- global scheduler enablement;
- per-job enablement;
- immediate `trigger_now` для allowlisted jobs;
- policy values для per-job cadence/schedule.

Поддерживаемые global/per-job enablement toggles и `trigger_now` НЕ ДОЛЖНЫ (SHALL NOT) требовать обязательный process restart для standard operator path.

Declarative edits `schedule/cadence` ДОЛЖНЫ (SHALL) иметь явный controlled apply path. До появления explicit live reschedule contract такие edits МОГУТ (MAY) требовать controlled runtime reload/restart, если effective policy и operator audit trail остаются прозрачными.

Bootstrap env flag может оставаться coarse safety fallback, но НЕ ДОЛЖЕН (SHALL NOT) быть единственным operator control path.

#### Scenario: Оператор выключает factual active sync без остановки runtime process
- **GIVEN** `worker-workflows` запущен и job `pool_factual_active_sync` включён
- **WHEN** оператор меняет desired state этой job на disabled
- **THEN** новые scheduler launches для этой job больше не стартуют
- **AND** `worker-workflows` продолжает работать как runtime process

### Requirement: Operator-triggered scheduler actions MUST correlate with scheduler execution history
Система ДОЛЖНА (SHALL) связывать operator-triggered scheduler actions с scheduler execution history, чтобы `trigger_now` был прослеживаем до конкретного job execution record.

#### Scenario: Trigger now приводит к коррелируемому scheduler run
- **GIVEN** staff оператор запускает `trigger_now` для allowlisted scheduler job
- **WHEN** job execution стартует и завершается
- **THEN** operator action history содержит ссылку или correlation key на соответствующий scheduler run
- **AND** оператор может проследить, какой именно scheduler execution был вызван этим действием

### Requirement: Runtime control execution MUST use bounded providers instead of generic shell
Система ДОЛЖНА (SHALL) исполнять runtime actions через bounded provider contract, скрытый за одним runtime-control API.

Local/hybrid provider МОЖЕТ (MAY) использовать checked-in inventory/probe/restart/log helpers.

Managed providers МОГУТ (MAY) использовать service-manager integrations.

Система НЕ ДОЛЖНА (SHALL NOT) принимать arbitrary shell commands, script paths или unbounded executor input от UI/API клиентов.

#### Scenario: Unsupported action или target отклоняется fail-closed
- **GIVEN** клиент запрашивает action, который не входит в supported catalog для выбранного runtime
- **WHEN** runtime control API валидирует запрос
- **THEN** запрос отклоняется fail-closed ошибкой unsupported action/target
- **AND** provider execution не запускается

### Requirement: Runtime-control logs and result excerpts MUST be bounded and redacted
Система ДОЛЖНА (SHALL) ограничивать объём log/output данных, возвращаемых в runtime-control surfaces, и редактировать credentials, secrets и другие чувствительные значения до их показа оператору.

#### Scenario: Tail logs не раскрывает секреты напрямую
- **GIVEN** source log/output содержит credential-like или secret-like значение
- **WHEN** оператор открывает runtime-control logs или action result excerpt
- **THEN** UI/API получает bounded excerpt
- **AND** чувствительное значение возвращается только в redacted форме

### Requirement: Global scheduler trigger MUST remain distinct from domain-specific factual refresh
Система ДОЛЖНА (SHALL) различать global scheduler actions и domain-specific workspace refresh actions.

`trigger_now` для factual scheduler job НЕ ДОЛЖЕН (SHALL NOT) silently подменять bounded action `Refresh factual sync` для конкретного `pool + quarter` context.

#### Scenario: Factual workspace refresh не remap-ится в global scheduler trigger
- **GIVEN** оператор находится в `/pools/factual` на конкретном `pool + quarter`
- **WHEN** он использует bounded action `Refresh factual sync`
- **THEN** система выполняет domain-specific refresh для этого workspace context
- **AND** это действие не маскируется под global scheduler `trigger_now` для всего job window

