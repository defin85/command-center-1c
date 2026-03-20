## Context
В authenticated shell остался последний небольшой, но всё ещё legacy блок route:
- `/clusters`;
- `/system-status`;
- `/service-mesh`.

По коду видно, что эти pages ещё не вошли в platform-governed perimeter:
- `Clusters.tsx` держит page-level catalog/actions/modals на raw `antd`;
- `SystemStatus.tsx` собирает observability canvas вручную через `Card`, `Row`, `Col` и internal polling loop;
- `ServiceMeshPage.tsx` вообще использует собственный div/css shell вместо platform route composition.

Даже если эти surfaces меньше operational и workflow waves, они важны как завершающий residual perimeter: пока они вне governance, проект всё ещё поддерживает два разных route-level подхода внутри одного authenticated frontend.

## Goals / Non-Goals
- Goals:
  - Расширить platform-governed perimeter на remaining infra/observability routes из epic `command-center-1c-zl2l`.
  - Зафиксировать route-level UI contract для `/clusters`, `/system-status` и `/service-mesh`.
  - Сделать responsive fallback, route-addressable selected context и realtime/polling stability enforceable через spec + tests.
- Non-Goals:
  - Мигрировать workflow/template или admin/support routes.
  - Менять backend contracts cluster management, system health или service mesh transport.
  - Переписывать observability widgets глубже, чем требуется route-level shell и interaction contract.

## Decisions

### 1. Все три route живут в одном capability `infra-observability-workspaces`
Для `/clusters`, `/system-status` и `/service-mesh` сейчас нет существующего route-level UI capability в OpenSpec. Создавать по одному spec на каждую страницу не имеет смысла: surfaces меньше предыдущих waves и достаточно близки по типу operator work.

Поэтому вводится один capability `infra-observability-workspaces`, который описывает:
- management workspace `/clusters`;
- diagnostics workspace `/system-status`;
- realtime observability workspace `/service-mesh`.

### 2. Главный фокус — route shell и interaction contract, а не переосмысление telemetry widgets
`SystemStatus` и `ServiceMesh` уже имеют рабочие внутренние компоненты для health/service topology. Этот change не должен превращаться в redesign observability layer.

Он фиксирует только:
- platform-owned route shell;
- selected diagnostics context;
- responsive fallback;
- polling/realtime stability expectations.

### 3. `/clusters` считается management workspace, а не просто CRUD table
По составу действий `/clusters` уже давно больше, чем список записей: create/edit, discover, sync, credentials, reset. Поэтому route должен мигрироваться как полноценный management workspace с canonical secondary surfaces, а не как “таблица плюс пару модалок”.

## Alternatives Considered

### Вариант A: Оставить эти routes как “малый legacy island”
Плюсы:
- минимальный upfront effort.

Минусы:
- governance perimeter остаётся неполным;
- проект продолжает поддерживать два page-level подхода;
- infra/observability surfaces останутся исключением без automated contract.

Итог: отклонён.

### Вариант B: Слить infra wave в предыдущие changes
Плюсы:
- меньше отдельных change folders.

Минусы:
- admin/support и workflow/template changes уже имеют собственный фокус;
- infra surfaces отличаются по interaction model;
- сложнее отслеживать residual perimeter.

Итог: отклонён.

## Risks / Trade-offs
- `SystemStatus` и `ServiceMesh` зависят от polling/realtime behaviour, поэтому слишком жёсткий UI contract может случайно залезть в transport/runtime semantics.
  - Mitigation: spec ограничивается operator-facing shell, state persistence и responsive rules.
- `/clusters` содержит много mutating flows, и route migration может разрастись в большой CRUD refactor.
  - Mitigation: focus on route-level workspace shell, selected context и canonical secondary surfaces.

## Migration Plan
1. Расширить governance perimeter на `/clusters`, `/system-status`, `/service-mesh`.
2. Ввести capability `infra-observability-workspaces`.
3. Мигрировать `/clusters`.
4. Мигрировать `/system-status` и `/service-mesh`.
5. Добавить route-level unit/browser regressions.
6. Пройти blocking frontend gate и `openspec validate`.
