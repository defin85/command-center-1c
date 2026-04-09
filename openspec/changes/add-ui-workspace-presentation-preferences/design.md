## Контекст

В репозитории уже существуют оба допустимых surface family:
- `catalog-detail`, где canonical path строится вокруг `MasterDetailShell`;
- `catalog-workspace`, где detail/read flows живут в secondary drawer или modal surface.

При этом реальные route находятся на разной степени зрелости:
- `/databases` и `/decisions` уже близки к каноничному compact-catalog + detail contract;
- `/workflows` и `/templates` всё ещё table-heavy hybrids;
- `/artifacts` осознанно относится к `catalog-workspace`, а не к `catalog-detail`.

Из этого следует важная граница: user-selectable presentation mode нельзя трактовать как право оператора переписать route family. Это лишь controlled variant внутри заранее совместимого surface.

## Goals

- Ввести понятный и ограниченный contract для user-selectable workspace presentation.
- Разрешить global default и per-route override только там, где это не ломает route semantics.
- Сохранить `workspaceKind` и `masterPaneGovernance` как hard architectural boundaries.
- Подготовить staged rollout без обязательной одновременной миграции всего frontend.

## Non-Goals

- Не превращать preference в универсальный "theme switch" для всех authenticated routes.
- Не менять domain semantics routes ради поддержки preference.
- Не требовать backend persistence в первой итерации.
- Не считать table-heavy hybrid pages автоматически готовыми к opt-in.

## Решения

### 1. Route family и presentation mode разделяются явно

`workspaceKind` продолжает описывать canonical route family.

`presentation mode` описывает только layout variant внутри eligible surface. Поэтому:
- unsupported route не должен внезапно превратиться в другой workspace family;
- preference не может переопределить `catalog-workspace` в `catalog-detail`;
- route-level business navigation и ownership secondary surfaces остаются теми же.

### 2. Eligibility управляется inventory, а не UI toggle сам по себе

Route может honor-ить shared preference только если governance inventory явно объявляет:
- `allowedPresentationModes`;
- `defaultPresentationMode`.

Это позволяет:
- связать opt-in с `workspaceKind`;
- уважать `masterPaneGovernance`;
- ограничивать rollout по маршрутам, а не по глобальному флагу.

### 3. Effective mode имеет жёсткий precedence contract

Effective mode определяется в таком порядке:
1. per-route operator override;
2. global operator default;
3. route default;
4. responsive fallback.

Это даёт и controllable user preference, и предсказуемое route-local поведение.

### 4. Narrow viewport остаётся stronger invariant

Даже если на desktop выбран `split`, на narrow viewport detail должен открываться через canonical mobile-safe fallback.

Это принципиально: responsive safety важнее сохранения desktop preference один-в-один.

### 5. Persistence делаем local-first

Первая реализация должна требовать только то, что выбор переживает reload и не блокирует primary user flow.

Local-first persistence:
- быстрее внедряется;
- не требует отдельной backend модели сразу;
- не мешает позже вынести roaming sync в отдельный change.

Если позже понадобится server-backed sync, это должен быть отдельный change, а не скрытое расширение scope.

### 6. Rollout идёт от самых зрелых routes

Первая волна:
- `/databases`;
- `/decisions`.

Поздние кандидаты:
- `/workflows`;
- `/templates`.

Явные exclusions первой волны:
- `/artifacts`;
- non-`catalog-detail` routes;
- routes без устойчивого selected-entity/detail open-close contract.

## Alternatives

### A. Один глобальный переключатель для всего UI

Отклонено.

Такой подход смешивает route families, конфликтует с governance inventory и быстро приводит к inconsistent UX на routes, которые изначально не поддерживают split/detail model.

### B. Только per-route локальные toggles без global default

Частично приемлемо, но отклонено как единственный вариант.

Без global default оператор накапливает фрагментированные настройки, а shared behaviour по compatible routes остаётся непредсказуемым.

### C. Сразу делать backend-backed user preferences

Отклонено для первой итерации.

Это преждевременно расширяет scope, хотя пользовательский эффект "выбор переживает reload" можно закрыть local-first persistence.

## Риски / Trade-offs

- Если включить hybrid pages слишком рано, preference только законсервирует существующий UI debt.
  - Mitigation: staged allowlist и explicit exclusions.
- Если inventory contract будет неявным, routes начнут honor-ить preference ad hoc.
  - Mitigation: explicit metadata + governance validation.
- Если не зафиксировать precedence заранее, одна и та же route будет вести себя непредсказуемо при наличии global и route-local overrides.
  - Mitigation: normative precedence requirement в новом capability.
- Если desktop preference начнёт отменять mobile fallback, проект потеряет уже достигнутый responsive safety baseline.
  - Mitigation: responsive fallback описывается как stronger invariant.

## Migration Plan

1. Добавить capability и cross-cutting governance/platform deltas.
2. Зафиксировать eligibility metadata contract в inventory.
3. Реализовать local-first preference store и mode resolution helper.
4. Подключить pilot routes `/databases` и `/decisions`.
5. Добавить regression coverage для supported modes.
6. Отдельно решать normalisation `/workflows` и `/templates` перед их opt-in.
