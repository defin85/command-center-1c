## Context
Текущий UI platform baseline уже существует и частично применяется:
- canonical thin design layer зафиксирован отдельным change;
- `/decisions` и `/pools/binding-profiles` уже переведены на `WorkspacePage`, `PageHeader`, `MasterDetailShell` и related platform primitives;
- browser/lint governance доказал, что route-level rules действительно ловят regressions.

Но operational perimeter всё ещё остаётся в legacy состоянии:
- governance rules в `frontend/eslint.config.js` адресуют в основном pilot pages;
- `/operations`, `/databases`, `/pools/catalog`, `/pools/runs` по-прежнему собраны на raw `antd` containers и ad-hoc `Modal`/`Drawer` orchestration;
- `/pools/catalog` и `/pools/runs` остаются крупнейшими route modules (`5000+` и `2900+` строк), а `/databases` и `/operations` продолжают смешивать catalog, inspect, authoring и diagnostics в одном route-level canvas;
- `/` уже использует `DashboardPage`, но внутри route-level composition всё ещё держится на raw layout primitives.

Проблема здесь уже не в единичных accessibility defects, а в том, что следующий набор high-traffic workspaces не вошёл в platform-governed perimeter и поэтому продолжает накапливать UI debt быстрее, чем его можно исправлять точечными bugfix.

## Goals / Non-Goals
- Goals:
  - Расширить новый UI-подход с pilot pages на core operational workspaces.
  - Зафиксировать route-level composition rules для `/`, `/operations`, `/databases`, `/pools/catalog`, `/pools/runs`.
  - Сделать route state, task separation и responsive fallback частью enforceable contract, а не только implementation detail.
  - Расширить automated governance perimeter на эти routes.
- Non-Goals:
  - Одновременно переписать все оставшиеся admin/support routes.
  - Перепроектировать доменные backend contracts.
  - Устранять каждый raw `antd` import внутри leaf components, если route-level platform contract уже соблюдён.
  - Заходить в `/workflows` и related authoring surfaces в том же change.

## Decisions

### 1. Scope ограничивается operational workspaces следующей волны
Этот change включает только:
- `/` (dashboard completion);
- `/operations`;
- `/databases`;
- `/pools/catalog`;
- `/pools/runs`.

Причины:
- это самые частые operator-facing paths;
- именно здесь сосредоточены самые крупные monolithic pages и route-level orchestration debt;
- эти routes меньше всего пересекаются с уже активными workflow-specific changes по сравнению с `/workflows` и смежными surfaces.

### 2. Route-level migration важнее leaf-by-leaf replacement
Главная цель change не в том, чтобы механически запретить любой raw `antd` import. Цель в том, чтобы route shell, primary catalog/detail composition и primary authoring flows проходили через platform layer.

Это означает:
- page shell и main orchestration обязаны идти через `DashboardPage` / `WorkspacePage`, `PageHeader`, `MasterDetailShell` и related primitives;
- raw `antd` допустим в leaf presentational components, если там нет новой page-level self-assembly;
- canonical `DrawerFormShell` / `ModalFormShell` обязательны для primary authoring/edit flows, а raw modals/drawers могут оставаться только как вторичный технический diagnostics path или временный compatibility island.

### 3. Migration slice должен фиксировать route-local state contract
Для operational workspaces новая platform migration должна включать не только layout, но и устойчивый workspace state contract:
- selected entity / stage / active detail context должны быть URL-addressable;
- reload, deep-link, back/forward и same-route re-entry не должны ломать этот контекст;
- browser tests должны ловить regressions, где route/local state начинает oscillate или silently reset.

Это решение напрямую вытекает из уже пойманных regressions на migrated surfaces и должно стать частью следующей волны migration, а не отдельным случайным hardening later.

### 4. Pools surfaces остаются в своих доменных spec, а governance — в `ui-web-interface-guidelines`
Для `/pools/catalog` и `/pools/runs` route migration нельзя описывать только общими UI guidelines, потому что эти surfaces уже имеют сильный доменный contract:
- topology/binding workflow для `organization-pool-catalog`;
- stage-based lifecycle и diagnostics contract для `pool-distribution-runs`.

Поэтому:
- cross-cutting perimeter, lint и validation rules живут в `ui-web-interface-guidelines`;
- route-specific composition and state requirements добавляются в соответствующие domain specs.

Тот же принцип используется для `/operations` и `/databases`: domain truth остаётся в их capability, а не в новой абстрактной umbrella spec.

### 5. Dashboard включается в change только как completion step, без выделения новой domain capability
`/` уже находится в промежуточном состоянии: route использует `DashboardPage`, но page-level layout ещё не дочищен от raw composition.

Отдельную domain spec для dashboard создавать не нужно. Достаточно зафиксировать в `ui-web-interface-guidelines`, что dashboard входит в platform-governed perimeter и должен использовать platform-owned route composition.

## Alternatives Considered

### Вариант A: Один большой change на весь remaining frontend
Плюсы:
- формально закрывает весь хвост legacy routes одним планом.

Минусы:
- change становится слишком большим и плохо проверяемым;
- резко растёт вероятность конфликтов с активными product changes;
- теряется приоритет high-traffic operational paths.

Итог: отклонён.

### Вариант B: Вообще не создавать новый change и мигрировать страницы opportunistically
Плюсы:
- меньше upfront specification work.

Минусы:
- governance perimeter остаётся дырявым;
- migration продолжается бессистемно;
- легко возвращаются старые patterns и бесконтрольные route-level rewrites.

Итог: отклонён.

### Вариант C: Создать отдельную новую capability только для “ui-platform-wave-two”
Плюсы:
- удобно группировать migration work.

Минусы:
- дублирует route truth, которая уже живёт в domain specs;
- усложняет поиск canonical requirements для конкретных routes.

Итог: отклонён в пользу модификации существующих capability + одного cross-cutting UI spec.

## Risks / Trade-offs
- Миграция `/pools/catalog` и `/pools/runs` легко может разрастись в архитектурный rewrite.
  - Mitigation: фиксировать только route-level composition, task separation и state contract; backend/domain contracts не трогать.
- Расширение lint perimeter может сначала дать много шума по legacy imports.
  - Mitigation: применять governance rules только к выбранным route modules этой волны, а не ко всему `frontend/src/pages/**` сразу.
- Route-state hardening может снова породить loops при неправильной синхронизации URL и local state.
  - Mitigation: включить explicit browser tests на reload/back-forward/same-route re-entry как blocking gate.
- Dashboard — частично migrated route, и его легко недооценить.
  - Mitigation: считать dashboard completion частью shared governance slice, но не расширять его в отдельный broad redesign task.

## Migration Plan
1. Расширить spec contract и governance perimeter на выбранные routes.
2. Доработать shared platform primitives только под потребности operational workspaces.
3. Завершить dashboard completion.
4. Мигрировать `/operations` и `/databases`.
5. Мигрировать `/pools/catalog` и `/pools/runs`.
6. Добавить regression coverage и пройти blocking frontend gate.
7. После стабилизации этой волны отдельно планировать remaining admin/support routes.
