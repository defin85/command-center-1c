## Context
В текущем checked-in контуре уже есть observability surfaces и куски runtime instrumentation, но нет единого control plane:
- `/system-status` и `/service-mesh` сейчас выполняют diagnostics/observability роль, а не service control;
- `/settings/runtime` показывает runtime settings catalog, но не lifecycle console;
- shell bootstrap отдаёт только `can_manage_rbac` и `can_manage_driver_catalogs`, то есть отдельного capability для runtime controls пока нет;
- `worker-workflows` поднимает Go scheduler с `ENABLE_GO_SCHEDULER`, а `worker` запускается без scheduler;
- `SchedulerJobRun` уже хранит историю scheduler runs, но истории operator-triggered runtime actions в доменной модели нет;
- runtime settings override API сейчас считает support-list просто как `RUNTIME_SETTINGS.keys()`, поэтому новые runtime-control keys нельзя бездумно добавлять в registry: иначе они автоматически окажутся tenant-overridable.

Из этого следует, что задача не сводится к "добавить кнопку restart". Нужен bounded runtime control plane с отдельными semantics для:
- observed runtime state;
- desired scheduler state;
- imperative actions;
- RBAC/audit;
- provider-backed execution.

## Goals / Non-Goals
- Goals:
  - Дать staff оператору canonical UI path для runtime/scheduler control без ухода в shell/debug scripts.
  - Сохранить `/system-status` primary operator route и встроить туда privileged control drill-down.
  - Ввести backend contract для allowlisted runtime actions, async action history и desired scheduler state.
  - Развести global-only runtime-control keys и tenant-scoped runtime overrides.
- Non-Goals:
  - Делать generic remote shell API.
  - Переводить весь runtime fleet на production-grade service manager integration в рамках одной реализации.
  - Дублировать live process controls в `/settings/runtime`.
  - Пересматривать domain semantics factual sync beyond control-plane/operator affordances.

## Decisions

### 1. `/system-status` остаётся primary operator route
Новый top-level route для runtime management не вводится. `/system-status` уже является canonical route для инфраструктурной диагностики, поэтому именно он получает runtime drill-down:
- один canonical selected runtime/service context без параллельных независимых URL selectors для diagnostics и controls;
- privileged tabs `Overview`, `Controls`, `Scheduler`, `Logs`;
- route-addressable selected tab/job/runtime;
- responsive fallback без page-wide overflow.

`/service-mesh` остаётся observability-only surface и может давать deep-link в `/system-status`, но не становится второй control console.

### 2. Route-level UI contract и backend control capability фиксируются разными spec слоями
UI truth для route остаётся в `infra-observability-workspaces` и `settings-management-workspaces`.

Backend/runtime semantics выносятся в отдельный capability `runtime-control-plane`, чтобы не смешивать:
- route shell behaviour;
- runtime action execution semantics;
- permission/audit model;
- provider implementation constraints.

### 3. Control model разделяет observed state, desired state и action runs
Runtime control plane оперирует тремя сущностями:
- `RuntimeInstance`: stable runtime instance identity, observed runtime state, health, supported actions, provider metadata, scheduler capability flags;
- `RuntimeDesiredState`: global/per-job scheduler enablement и связанные policy values;
- `RuntimeActionRun`: async action execution с actor, reason, target, status, timestamps и bounded result excerpt.

Это исключает смешение "что runtime сейчас делает" и "чего оператор хочет добиться".

Stable runtime instance identity должна быть достаточной для host/provider-aware expansion. Target identity не должен зависеть только от абстрактного service class name, если в будущем одна logical service существует в нескольких host/provider contexts.

### 4. API остаётся async и allowlisted
Imperative actions не должны блокировать HTTP до завершения restart/probe/log collection. Recommended API shape:
- `GET /api/v2/system/runtime-control/catalog/`
- `GET /api/v2/system/runtime-control/runtimes/{runtime_id}/`
- `GET /api/v2/system/runtime-control/runtimes/{runtime_id}/actions/`
- `POST /api/v2/system/runtime-control/actions/`
- `GET /api/v2/system/runtime-control/actions/{action_id}/`
- `PATCH /api/v2/system/runtime-control/runtimes/{runtime_id}/desired-state/`
- `GET /api/v2/system/runtime-control/scheduler/jobs/`

`POST /actions/` должен возвращать `202 Accepted` и `action_id`.

Catalog определяет supported actions per runtime. Это позволяет первой реализации поддержать только bounded набор (`probe`, `restart`, `tail_logs`, `trigger_now`, `enable_job`, `disable_job`) без обещания universal `start/stop` для всех runtimes.

Accepted action run должен быть persisted до provider dispatch. Если action может нарушить процесс, обслуживающий сам runtime-control API или provider host path, terminal outcome не должен зависеть от живости initiating HTTP request/process и должен восстанавливаться через external observation или supervising executor.

### 5. Execution идёт через provider backend, а не через shell-from-browser
UI и публичный API не принимают произвольные команды, пути скриптов или raw shell input.

Execution contract должен идти через provider abstraction:
- local/hybrid provider может использовать checked-in inventory/probe/restart helpers и known log sources;
- managed provider позже сможет оборачивать systemd/Nomad/Kubernetes-style runtime managers;
- unsupported target/action combinations отклоняются fail-closed.

Такой подход оставляет один control API и не превращает orchestrator в ad-hoc remote shell.

Logs/result excerpts, возвращаемые в runtime-control surfaces, должны быть bounded и redacted для credentials/secrets, чтобы `tail_logs` не превращался в обходной канал утечки чувствительных данных.

### 6. Scheduler desired state становится live-config, а env остаётся bootstrap kill-switch
Startup env (`ENABLE_GO_SCHEDULER`) остаётся coarse bootstrap flag и safety fallback, но operator-facing scheduler controls не должны требовать обязательный process restart.

Для этого change вводит global-only runtime-control policy keys, например:
- `runtime.scheduler.enabled`
- `runtime.scheduler.job.<job_name>.enabled`
- `runtime.scheduler.job.<job_name>.schedule`

Worker scheduler должен перечитывать effective global policy и применять как минимум global/per-job enablement без полного restart для стандартного operator path.

Для `V1` этот change не должен обещать universal live-reschedule всех cron expressions. Declarative edits `schedule/cadence` живут в `/settings/runtime`; до появления явного re-register/reload path допустим controlled runtime restart или provider-mediated reconcile, если effective policy и audit trail остаются прозрачными для оператора.

### 7. `/settings/runtime` остаётся advanced policy surface
Live lifecycle actions и immediate trigger flows не дублируются в `/settings/runtime`.

`/settings/runtime` получает роль advanced authoring workspace для declarative policy:
- scheduler enablement;
- per-job enablement;
- per-job schedule/cadence;
- связанных rollout keys.

`/system-status` должен уметь deep-link'ить в `/settings/runtime` на конкретный section/key context, если оператор хочет редактировать долгоживущую policy, а не выполнить immediate action.

### 7a. Domain-specific manual actions не подменяются global scheduler console
Global runtime control plane управляет runtime/job surfaces, а не domain-specific workspace actions.

Это особенно важно для factual monitoring:
- `trigger_now` для `pool_factual_active_sync` означает запуск scheduler window/job path;
- `Refresh factual sync` в `/pools/factual` остаётся bounded pool+quarter action и не должен silently remap-иться в global scheduler trigger.

Иначе оператор потеряет различие между глобальным runtime control и domain-specific refresh semantics.

### 8. Runtime-control keys не должны попадать в tenant override APIs
Текущий override path считает поддерживаемыми все keys из `RUNTIME_SETTINGS`, поэтому runtime-control keys нельзя просто добавить в registry без дополнительной семантики.

Change вводит global-only classification для runtime-control keys:
- tenant override list/update API не возвращает и не принимает такие keys;
- tenant-aware effective resolution не трактует их как tenant-scoped;
- operator control plane работает только с global baseline/bootstrap.

### 9. Permission model разделяет доступ к control plane и destructive actions
Нужен dedicated permission/shell capability для runtime control surface. Минимальная модель:
- отдельный capability для показа control UI;
- explicit reason для dangerous actions;
- fail-closed API responses для неавторизованных вызовов;
- diagnostics-only fallback для пользователей без control capability.

При необходимости реализация может разделить safe/dangerous action permissions, но capability surface уже сейчас должен учитывать такую эволюцию.

### 10. Operator-triggered scheduler actions должны коррелироваться с scheduler run history
В системе уже есть `SchedulerJobRun` как журнал scheduler executions. Новый `RuntimeActionRun` не должен создавать вторую изолированную историю для `trigger_now`.

Поэтому operator-triggered scheduler actions должны сохранять correlation path между:
- operator action history;
- scheduler execution history;
- job name/target runtime.

Это нужно, чтобы оператор видел, что `trigger_now` привёл к конкретному scheduler run, а не к абстрактному "успешному клику".

## Alternatives Considered

### Вариант A: Новый top-level route для runtime controls
Плюсы:
- визуально отделяет diagnostics и control.

Минусы:
- дублирует entrypoint для одного и того же operator workflow;
- уводит service inspection и service control в разные места;
- усложняет navigation и route governance.

Итог: отклонён.

### Вариант B: Кнопки в UI вызывают repo scripts напрямую
Плюсы:
- быстрый прототип для local dev.

Минусы:
- нет нормального RBAC/audit;
- получается generic shell bridge;
- модель плохо переносится на multi-host/prod.

Итог: отклонён.

### Вариант C: Scheduler controls остаются restart-only через env
Плюсы:
- меньше runtime plumbing.

Минусы:
- UI будет обещать live control, которого фактически нет;
- pause/resume и per-job control станут дорогими operationally;
- desired state и observed runtime state останутся смешанными.

Итог: отклонён.

### Вариант D: Считать `trigger_now` эквивалентом domain-specific factual refresh
Плюсы:
- меньше control affordances.

Минусы:
- смешиваются global scheduler semantics и bounded pool+quarter refresh;
- теряется различие между runtime console и domain workspace;
- возрастает риск operator confusion и audit ambiguity.

Итог: отклонён.

## Risks / Trade-offs
- Provider abstraction добавляет upfront complexity.
  - Mitigation: первая реализация ограничивается local/hybrid provider и allowlisted actions per runtime.
- Runtime-control keys легко случайно сделать tenant-overridable через существующий registry path.
  - Mitigation: отдельная global-only semantics в `runtime-settings-overrides` и explicit filtering в API/effective resolution.
- Слишком широкий action catalog может разрастись до полу-shell API.
  - Mitigation: catalog-driven allowlist, explicit action types и fail-closed rejection для unknown actions.
- `V1` может переобещать live schedule editing, если контракт не ограничить.
  - Mitigation: live path обязателен для enable/disable и `trigger_now`; schedule/cadence edits остаются declarative до явного scheduler reload contract.
- Self-target lifecycle actions могут потерять terminal outcome, если completion завязан на тот же процесс, который оператор перезапускает.
  - Mitigation: persist-before-dispatch, detached provider execution и external outcome reconciliation.
- Log/drill-down surfaces могут случайно показывать секреты из process output.
  - Mitigation: bounded excerpts, explicit redaction rules и separate privileged access gate.
- `trigger_now` без correlation с scheduler history создаст две несвязанные operator истории.
  - Mitigation: correlation ID / explicit linkage между `RuntimeActionRun` и `SchedulerJobRun`.
- `/system-status` может стать перегруженным, если control plane конкурирует с diagnostics grid.
  - Mitigation: detail-first drill-down, deep-linkable tabs и responsive stacked layout вместо второй page-level dashboard.

## Migration Plan
1. Ввести new capability `runtime-control-plane` и обновить route specs для `/system-status` и `/settings/runtime`.
2. Добавить permission/shell capability и bounded runtime-control API contract.
3. Реализовать local/hybrid provider для allowlisted runtimes и supported actions.
4. Добавить global-only runtime-control settings semantics, live enable/disable path и controlled policy-apply path для schedule/cadence.
5. Связать operator-triggered scheduler actions с existing scheduler run history.
6. Встроить privileged control drill-down в `/system-status` и deep-link в `/settings/runtime`.
7. Покрыть authz, async action audit, global-only key filtering, correlation, route state restore и responsive fallback тестами.
