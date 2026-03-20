## Context
После operational wave и выделенного admin/support backlog в frontend остаётся отдельный workflow/template slice, который всё ещё живёт на старой page assembly:
- workflow library `/workflows`;
- workflow executions `/workflows/executions`;
- workflow designer `/workflows/new` и `/workflows/:id`;
- workflow monitor `/workflows/executions/:executionId`;
- templates catalog `/templates`;
- pool schema templates `/pools/templates`;
- pool master-data workspace `/pools/master-data`.

По исходникам видно несколько стабильных признаков legacy-состояния:
- route files крупные и монолитные (`WorkflowDesigner.tsx`, `TemplatesPage.tsx`, `WorkflowMonitor.tsx`);
- route-level composition строится через raw `Layout`, `Card`, `Tabs`, `Table`, `Modal`, `Drawer` и bespoke CSS/layout;
- часть workflow routes вообще не использует `MainLayout`, а значит живёт вне уже стабилизированного workspace shell;
- в этих route directories нет usage canonical page primitives (`WorkspacePage`, `PageHeader`, `MasterDetailShell`, `DrawerFormShell`, `ModalFormShell`, `RouteButton`) на route-page уровне.

Это именно тот тип surfaces, где без route-level migration снова возникают route-state regressions, brittle handoff path и перегруженный authoring canvas.

## Goals / Non-Goals
- Goals:
  - Расширить platform-governed perimeter на workflow/template routes из epic `command-center-1c-i8l5`.
  - Зафиксировать route-level UI contract для workflow library, designer, executions, monitor, templates, pool schema templates и pool master-data workspace.
  - Сделать selected context, authoring surfaces и responsive fallback enforceable через spec + tests.
- Non-Goals:
  - Мигрировать admin/support routes.
  - Мигрировать infra/observability routes.
  - Менять backend semantics workflow runtime, templates persistence или master-data APIs.
  - Проводить большой visual redesign поверх уже принятого platform layer.

## Decisions

### 1. Workflow routes получают отдельный UI capability
Существующие workflow-related specs в основном описывают runtime semantics (`execution-runtime-unification`, `pool-workflow-execution-core`) или доменную бизнес-логику. Они не подходят как canonical source of truth для route-level UI contract `/workflows*`.

Поэтому вводится новый capability `workflow-management-workspaces`, который фиксирует:
- workflow library как catalog workspace;
- workflow designer как authoring workspace;
- workflow executions и workflow monitor как diagnostics/inspect workspaces;
- route-addressable selected workflow/execution/node context.

### 2. Templates и pool surfaces остаются в своих доменных specs
`/templates`, `/pools/templates` и `/pools/master-data` уже привязаны к существующим capability:
- `operation-templates`;
- `organization-pool-catalog`;
- `pool-master-data-hub-ui`.

Их route migration нужно описывать именно там, чтобы route-level UI truth оставался рядом с доменным контрактом, а не переезжал в абстрактный “wave-two UI” документ.

### 3. Workflow authoring/monitor routes считаются частью platform-governed shell даже если сейчас обходят `MainLayout`
Сейчас `/workflows/new`, `/workflows/:id` и `/workflows/executions/:executionId` живут отдельно от `MainLayout`, но это не должно оставаться оправданием для bespoke full-page assembly.

Change фиксирует, что canonical workflow shell должен быть platform-owned независимо от того, остаётся ли route standalone или встраивается в общий shell через layout composition.

### 4. Route-local state важнее визуальной унификации
Для workflow/template pages главный источник regressions — не столько отсутствие одинаковых карточек, сколько потеря selected context:
- выбранный workflow;
- surface/library mode;
- execution filter;
- selected node;
- active template/master-data zone;
- remediation handoff context.

Поэтому change фиксирует прежде всего URL-addressable workspace state и canonical authoring/detail surfaces, а не требует механически привести все страницы к одному visual layout.

## Alternatives Considered

### Вариант A: Дописать workflow/template migration в `refactor-ui-platform-operational-workspaces`
Плюсы:
- меньше отдельных change folders.

Минусы:
- operational change уже имеет отдельный residual backlog;
- workflow/template surfaces отличаются по рискам и authoring complexity;
- change стал бы слишком широким и конфликтным.

Итог: отклонён.

### Вариант B: Разделить workflows и templates в два независимых changes
Плюсы:
- меньше scope на change.

Минусы:
- governance/perimeter work пришлось бы дублировать;
- `i8l5` уже описывает их как одну согласованную волну;
- часть runtime handoff между `/templates`, `/workflows` и pool-related workspaces пришлось бы координировать между двумя proposals.

Итог: отклонён.

## Risks / Trade-offs
- Workflow designer легко разрастается в архитектурный rewrite canvas/editor logic.
  - Mitigation: change фиксирует route shell, selected context и canonical authoring surfaces, а не переписывает все внутренние workflow widgets.
- Workflow monitor имеет тяжёлый realtime/diagnostics path, и mobile-safe fallback может потребовать неочевидных компромиссов.
  - Mitigation: spec требует responsive inspect fallback, но не диктует один конкретный internal widget layout.
- Pool master-data route уже имеет доменный spec и рабочие tabs; слишком агрессивная миграция может смешать UI refactor с domain work.
  - Mitigation: ограничить scope route-level shell, tab/remediation state и responsive fallback.

## Migration Plan
1. Расширить governance perimeter на workflow/template routes.
2. Ввести новый capability `workflow-management-workspaces`.
3. Мигрировать workflow list/executions и designer/monitor.
4. Мигрировать `/templates`, `/pools/templates`, `/pools/master-data`.
5. Добавить route-level unit/browser regressions.
6. Пройти blocking frontend gate и `openspec validate`.
