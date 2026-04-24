## Context
Текущий authenticated frontend уже имеет shared shell invariants на уровне spec, но route tree всё ещё собран по legacy-pattern:
- почти каждый route в `frontend/src/App.tsx` отдельно монтирует `ProtectedRoute`, `MainLayout` и `LazyBoundary`;
- capability/staff gates (`ProtectedRoute`, `StaffRoute`, `RbacRoute`, `DriverCatalogsRoute`) сами владеют bootstrap lifecycle, а не только принимают готовый shell context;
- browser contract уже проверяет shell-safe handoff между `/service-mesh` и `/pools/master-data`, и с включённым `future.v7_startTransition` этот сценарий ломается.

Это означает, что проблема не page-local и не сводится к одной нестабильной странице. Transition-mode просто проявляет существующий architectural split-brain:
- URL уже относится к новому route;
- старый subtree ещё жив и продолжает владеть shell/content;
- новый route mount зависит от duplicated guard/bootstrap/suspense ownership.

## Goals / Non-Goals
- Goals:
  - Зафиксировать single-owner route tree для authenticated shared shell.
  - Отделить shell-backed и no-shell authenticated route groups без дублирования bootstrap ownership.
  - Сделать `v7_startTransition` допустимым только после явного route-tree hardening.
  - Закрепить regression coverage для stale-content и bootstrap replay scenarios.
- Non-Goals:
  - Миграция на data router в этом change.
  - Переписывание route-local state contracts на всех страницах.
  - Рефакторинг platform primitives без прямой связи с shared-shell ownership.

## Decisions

### 1. Shared shell должен иметь единственного route-tree owner
Shell-backed authenticated routes должны монтироваться под одним parent route group, который владеет:
- auth/bootstrap gate;
- shared authz/session context;
- `MainLayout`;
- primary `Suspense` boundary;
- `Outlet`-based content swap между route pages.

Внутренний переход между такими routes не должен нормальным образом пересоздавать shell subtree ради смены page content.

Single owner здесь означает не только single network request через React Query cache. На default authenticated shell path должен быть один checked-in runtime provider/route group, который вызывает bootstrap read-model hook и отдаёт готовый context вниз. `MainLayout`, `AuthzProvider`, `I18nProvider` и route-level guards должны потреблять этот context, а не каждый заново становиться observer/owner'ом bootstrap lifecycle.

### 2. Capability/staff gating переходит на shared-context consumption
`ProtectedRoute`, `StaffRoute`, `RbacRoute` и `DriverCatalogsRoute` должны перестать быть route-local bootstrap owners.

Они должны:
- читать уже инициализированный shell context;
- принимать routing decision как thin gate around `Outlet`;
- не запускать отдельный bootstrap owner на обычном handoff внутри той же authenticated session.
- если нужен preload route module для privileged pages, он должен быть side-effect'ом route metadata/module scope или thin gate, но не причиной возвращать guard к bootstrap ownership.

### 3. No-shell/fullscreen routes остаются explicit exception group
`/login` и другие unauthenticated routes остаются отдельно.

Authenticated fullscreen/no-shell routes тоже могут жить в отдельной группе, но:
- это должно быть explicit route-group decision;
- auth/bootstrap owner остаётся общим, если route не задокументирован как separate hard-reset owner with rationale;
- исключение не должно возвращать legacy pattern, где каждый route сам владеет shell lifecycle.
- exception list должен быть checked-in через route governance inventory или эквивалентную checked-in route metadata и проверяемым static test: `public`, `redirect`, `shell-backed authenticated`, `authenticated no-shell/fullscreen`.
- отсутствие `MainLayout` в route element не является достаточным design justification для no-shell/fullscreen exception.

### 4. `v7_startTransition` включается только после route-tree refactor
Флаг сам по себе не является целью change. Он служит acceptance signal:
- до refactor флаг воспроизводимо ломает shell-safe handoff;
- после refactor тот же browser regression и auth-restore checks должны проходить с флагом включённым.

### 5. Data router migration откладывается
Миграция на `createBrowserRouter` / `RouterProvider` потенциально дала бы более широкие router primitives, но сейчас это слишком большой blast radius.

Для этого change достаточно:
- стабилизировать текущий `BrowserRouter` route tree;
- устранить duplicated shell/bootstrap ownership;
- доказать compatibility с transition-mode.

## Alternatives Considered

### Вариант A: Просто оставить `v7_startTransition` выключенным
Плюсы:
- нулевой immediate risk.

Минусы:
- warning остаётся;
- route-tree defect остаётся;
- следующий runtime change снова упрётся в тот же stale-content class.

Итог: отклонён как freeze, а не fix.

### Вариант B: Лечить symptom через preload перед navigate
Плюсы:
- потенциально меньший patch.

Минусы:
- не устраняет duplicated shell ownership;
- не решает auth/bootstrap split-brain;
- создаёт fragile route-specific workaround.

Итог: отклонён.

### Вариант C: Немедленно перейти на data router
Плюсы:
- доступ к modern router APIs и более явному route-tree model.

Минусы:
- большой blast radius для всего frontend;
- unnecessary scope expansion для текущей проблемы;
- повышенный риск collateral regressions.

Итог: отложен как отдельный follow-up, если route-tree hardening не хватит.

## Risks / Trade-offs
- Route extraction из `App.tsx` может затронуть route inventory tests и shell assumptions.
  - Mitigation: держать paths и visual contract неизменными; менять ownership layer, а не page semantics.
- Fullscreen/no-shell routes легко случайно посадить под `MainLayout`.
  - Mitigation: выделить explicit no-shell route group и покрыть его focused tests.
- Shared bootstrap owner может открыть скрытые зависимости route-local guards от собственных loading states.
  - Mitigation: заранее зафиксировать shell loading/error state как single source of truth и адаптировать guards к thin-gate модели.

## Migration Plan
1. Обновить OpenSpec contract для shared shell routing и bootstrap ownership.
2. Выделить в `App` nested route groups: shell-backed authenticated, no-shell authenticated, unauthenticated.
3. Перевести capability/staff guards на shared-context consumption и `Outlet` model.
4. Сохранить существующие browser regressions и добавить focused app-level tests для auth restore/transition-mode.
5. Включить `future.v7_startTransition` и прогнать blocking verification.

## Open Questions
- Нужен ли отдельный checked-in route-tree module (`frontend/src/routes/**`) сразу в первом rollout или достаточно bounded extraction внутри `App.tsx`. Первый rollout МОЖЕТ (MAY) оставить route declarations в `App.tsx`, если static inventory checks остаются authoritative; отдельный route module НЕ ДОЛЖЕН (SHALL NOT) быть prerequisite для включения `v7_startTransition`.
- Должен ли single bootstrap owner жить в новом `ShellRuntimeProvider`/`SharedShellRoute` module или можно оставить его внутри bounded `App.tsx` extraction. В любом варианте direct `useShellBootstrap` consumers на default shell path должны быть сведены к этому owner, а owner должен быть named checked-in component/provider, который static tests могут отличить от thin guards.
