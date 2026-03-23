## Context

Topology templates уже существуют как backend capability и как consumer input для `/pools/catalog`, но у оператора нет UI surface для их authoring. Из-за этого template-based topology instantiation формально доступен, но practically требует внепродуктового шага.

С точки зрения product model reusable topology template и concrete pool topology — это разные уровни:
- `/pools/topology-templates` author'ит reusable abstract graph;
- `/pools/catalog` materialize'ит выбранную revision в concrete `pool`.

Смешивать оба уровня в одном route не нужно: это вернёт monolithic canvas и снова сделает reusable authoring competing flow рядом с concrete pool editing.

## Goals / Non-Goals

- Goals:
  - дать operator-facing UI для topology template catalog и revision authoring;
  - убрать dead-end из `/pools/catalog`, где consumer path требует внешний producer step;
  - сохранить `/pools/catalog` как concrete instantiation workspace;
  - сохранить operator context при handoff между reusable и concrete surfaces.
- Non-Goals:
  - менять backend domain contract topology templates;
  - добавлять graph cloning/export из existing concrete pool;
  - проектировать новый lifecycle workflow для deactivate/archive template;
  - переносить reusable topology authoring обратно inline в `/pools/catalog`.

## Decisions

### 1. Dedicated route `/pools/topology-templates`

Reusable topology template authoring живёт в отдельном route, а не внутри `/pools/catalog`.

Почему:
- reusable graph и concrete pool topology — разные operator tasks;
- `/pools/catalog` уже перегружен pool-local contexts;
- existing pattern с `/pools/binding-profiles` показывает более устойчивую модель: reusable layer author'ится в dedicated route, а consumer workspace делает handoff.

### 2. Workspace composition через platform primitives

Новый route должен использовать canonical platform layout:
- list/detail shell для catalog;
- dedicated create/revise form shell;
- mobile-safe detail fallback без page-wide horizontal overflow.

Это сохраняет UI governance и не добавляет ещё один ad-hoc admin surface.

### 3. Minimal authoring scope: create template + revise template

MVP surface покрывает только два producer flow:
- создать новый topology template вместе с initial revision;
- выпустить новую revision для существующего template.

Этого достаточно, чтобы закрыть current UX gap в `/pools/catalog`. Actions вроде deactivate/archive или import из existing graph остаются вне scope.

### 4. Explicit handoff и return context

`/pools/catalog` должен иметь явный handoff в `/pools/topology-templates`, а новый route должен уметь вернуть оператора обратно в тот же `pool` и topology task context.

Возвращаемый context должен оставаться URL-addressable. Конкретный transport может быть через query params или route state с URL mirror, но shipped path не должен требовать повторного ручного выбора `pool`.

### 5. Existing backend API остаётся canonical producer backend

Новый surface использует уже существующие endpoints:
- `GET /api/v2/pools/topology-templates/`
- `POST /api/v2/pools/topology-templates/`
- `POST /api/v2/pools/topology-templates/{topology_template_id}/revisions/`

Change не требует нового backend capability, только frontend wiring, typed wrappers, contract asserts и docs.

## Risks / Trade-offs

- Если route сделать без explicit handoff обратно в `/pools/catalog`, оператор всё равно потеряет continuity между reusable и concrete workflow.
- Если попытаться встроить template authoring inline в `/pools/catalog`, снова вырастет page complexity и competing flows.
- Так как current backend не даёт отдельный deactivate/archive path, UI surface временно будет асимметричен относительно status visibility. Это acceptable для текущего scope, если operator не вводится в заблуждение насчёт доступных actions.

## Migration Plan

1. Добавить новый route и навигационный entry.
2. Добавить typed frontend wrappers/contract assertions для topology template mutations.
3. Реализовать catalog/detail/create/revise surface.
4. Добавить handoff из `/pools/catalog` и возврат в topology task context.
5. Обновить runbook/release note и acceptance coverage.

## Open Questions

- Нет. Для текущего scope достаточно existing backend API и current topology template domain contract.
