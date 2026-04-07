## Context
Operational wave уже перевела на platform layer high-traffic operator routes, но authenticated shell всё ещё содержит отдельный блок privileged/admin pages, собранных на старом подходе:
- `/rbac`;
- `/users`;
- `/dlq`;
- `/artifacts`;
- `/extensions`;
- `/settings/runtime`;
- `/settings/command-schemas`;
- `/settings/timeline`.

По коду это видно сразу:
- `frontend/src/App.tsx` по-прежнему монтирует эти routes под `MainLayout` без platform-governed route contract;
- ключевые route files всё ещё крупные и bespoke (`Extensions.tsx` — `1262` строк, `TimelineSettingsPage.tsx` — `364`, `UsersPage.tsx` — `324`);
- в этих директориях отсутствует usage canonical route primitives (`WorkspacePage`, `PageHeader`, `MasterDetailShell`, `DrawerFormShell`, `ModalFormShell`, `RouteButton`) на route-page уровне;
- часть surfaces до сих пор строится на raw `Modal`/`Drawer`, `Tabs`, `Card`, `TableToolkit` и ручной grid/layout orchestration.

Если оставить этот слой вне следующей волны migration, проект получит тот же тип regressions, что уже был в operational slice: route-state instability, fragile mobile fallback, возврат bespoke authoring surfaces и рост page-level UI debt быстрее, чем его можно чинить bugfix-ами.

## Goals / Non-Goals
- Goals:
  - Расширить platform-governed perimeter на remaining admin/support routes из epic `command-center-1c-rxzs`.
  - Зафиксировать route-level UI contract для `/rbac`, `/users`, `/dlq`, `/artifacts`, `/extensions`, `/settings/runtime`, `/settings/command-schemas`, `/settings/timeline`.
  - Сделать URL-addressable selected context, canonical secondary surfaces и responsive fallback enforceable через spec + tests.
  - Не смешивать admin/support wave с workflow/template и infra/observability waves.
- Non-Goals:
  - Переписывать workflow/template routes.
  - Мигрировать infra/observability routes.
  - Менять backend semantics `RBAC`, `DLQ`, artifacts, runtime settings или command schemas.
  - Принудительно заменять каждый raw `antd` leaf widget.

## Decisions

### 1. Scope режется по операторским классам, а не по одному огромному “admin” зонтику
Этот change покрывает три согласованных блока:
- governance/admin catalogs: `/rbac`, `/users`, `/dlq`, `/artifacts`;
- management workspace: `/extensions`;
- settings workspace: `/settings/runtime`, `/settings/command-schemas`, `/settings/timeline`.

Это даёт две выгоды:
- можно задавать route-level contract в доменных capability, а не в одном абстрактном UI документе;
- implementation может идти независимыми slices внутри одного change без того, чтобы превращаться в big-bang rewrite.

### 2. Для route без существующего domain UI contract вводится новый capability
У `/rbac`, `/users`, `/dlq` и `/artifacts` нет собственного OpenSpec capability, описывающего route-level UI truth. Переносить эти требования в `ui-web-interface-guidelines` нельзя, потому что тогда там начнут смешиваться общие governance rules и конкретные operator workflows.

Поэтому вводится новый capability `admin-support-workspaces`, который описывает:
- selected mode/tab/entity context;
- canonical authoring/remediation surfaces;
- shell-safe handoff на смежные route;
- mobile-safe detail fallback.

### 3. Settings pages получают отдельный capability вместо перегруза `runtime-settings-overrides`
`runtime-settings-overrides` уже описывает backend semantics tenant overrides и precedence. Если добавить туда route-level contract `/settings/runtime` и `/settings/timeline`, spec начнёт смешивать разные уровни ответственности.

Поэтому вводится новый capability `settings-management-workspaces`, который фиксирует UI truth settings routes, а `runtime-settings-overrides` остаётся source of truth для semantics effective settings.

### 4. `extensions` и `command-schemas` остаются в своих доменных specs
Для `/extensions` и `/settings/command-schemas` доменные capability уже существуют:
- `extensions-overview`;
- `command-schemas-driver-options`.

Именно там и нужно описывать route-level migration, потому что эти pages уже сильно связаны со своими доменными workflow:
- preferred template bindings и drill-down для extensions;
- driver/mode/command context для command schemas.

### 5. Shared shell contract не дублируется, а наследуется
Repo-wide invariant про SPA handoff и отсутствие redundant shell reads уже введён предыдущей волной и должен оставаться базой для этого change.

В этой волне мы:
- не переписываем этот invariant заново;
- но расширяем governance perimeter и browser coverage на новые migrated routes, чтобы admin/support pages тоже перестали выпадать из общего shell contract.

### 6. Shared governance inventory остаётся единственным perimeter registry
Эта wave должна подключать `/rbac`, `/users`, `/dlq`, `/artifacts`, `/extensions`, `/settings/runtime`, `/settings/command-schemas` и `/settings/timeline` через shared governance inventory из `01-expand-ui-frontend-governance-coverage`.

Route enrollment, tier assignment и targeting route-specific rules не должны возвращаться к новой hand-maintained perimeter allowlist в `eslint.config.js`. Если в ходе migration выяснится, что generic shared rules не хватает, change расширяет inventory-driven helpers, а не создаёт второй источник истины.

## Alternatives Considered

### Вариант A: Продолжать точечными bugfix без нового change
Плюсы:
- меньше upfront spec work.

Минусы:
- privileged routes так и останутся вне enforceable platform contract;
- migration превратится в набор несвязанных patch-фиков;
- browser/lint governance снова будет покрывать только часть frontend.

Итог: отклонён.

### Вариант B: Один новый capability на все remaining routes
Плюсы:
- проще создать один spec file.

Минусы:
- смешиваются route-level rules для сильно разных domains;
- теряется доменная привязка requirements;
- сложнее искать canonical truth для конкретной страницы.

Итог: отклонён.

### Вариант C: Разбить admin/support wave на несколько отдельных changes сразу
Плюсы:
- меньше scope у каждого change.

Минусы:
- `rxzs` уже описывает единый согласованный slice;
- возрастает overhead на coordination и validation;
- часть shared governance work всё равно пришлось бы дублировать вместо переиспользования inventory из `01-expand-ui-frontend-governance-coverage`.

Итог: отклонён.

## Risks / Trade-offs
- `/extensions` слишком крупный route, и его migration легко разрастётся в скрытый domain refactor.
  - Mitigation: фиксировать только route shell, selected context, secondary surfaces и responsive fallback; backend/manual-operation semantics не трогать.
- `/settings/command-schemas` имеет сложный guided/raw editor path, и “правильный” master-detail здесь не совпадает с типовым CRUD catalog.
  - Mitigation: spec фокусируется на route-addressable state и canonical shell, а не требует механически привести всё к одному и тому же layout.
- `/rbac` и `/users` используют разные privilege gates (`RbacRoute`, `StaffRoute`), поэтому governance нельзя строить на предположении о едином доступе.
  - Mitigation: route-shell contract описывается отдельно от auth gate; change не меняет access model.
- Browser coverage на admin/support routes может стать дорогой по времени.
  - Mitigation: расширять `ui-platform` suite только на route-state, shell-safe handoff и responsive contract, а не на полный happy-path regression каждого домена.

## Migration Plan
1. Расширить governance perimeter на admin/support routes.
2. Ввести missing UI capabilities для `admin-support-workspaces` и `settings-management-workspaces`.
3. Мигрировать governance/admin catalog routes.
4. Мигрировать `extensions` и settings routes.
5. Добавить route-level unit/browser regressions.
6. Пройти blocking frontend gate и `openspec validate`.
