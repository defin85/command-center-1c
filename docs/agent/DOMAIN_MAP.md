# Domain Map

Статус: authoritative agent-facing guidance.

Короткая product/domain карта для первых 10-15 минут работы, когда нужно понять не только структуру репозитория, но и что именно считается продуктом, domain layer и operator-facing outcome.

## Что делает продукт

`CommandCenter1C` — control plane для централизованного управления и массовых операций по множеству баз `1C:Enterprise / 1С:Бухгалтерия 3.0`.

Canonical execution path:

`frontend -> api-gateway -> orchestrator -> worker -> 1C`

Продукт решает три уровня задач:
- операторские массовые операции и мониторинг выполнения;
- analyst-facing моделирование reusable workflow/decision/template артефактов;
- platform/staff управление runtime, каталогами, доступом и служебной диагностикой.

## Ключевые роли

- Оператор: управляет базами, пулами, master data, запускает run-ы и следит за исполнением.
- Аналитик: моделирует `workflow definition`, `decision resource`, `template` и reusable execution logic.
- Staff/platform: поддерживает runtime settings, driver catalogs, RBAC, DLQ и системную диагностику.

## Основные доменные сущности

- `database`: конкретная 1С-база, с которой работают operator- и metadata-aware flows.
- `cluster`: контур/кластер 1С, в котором живут базы и RAS/OData integration surfaces.
- `operation` / `artifact`: массовые или служебные действия и их результирующие артефакты.
- `template`: reusable execution template для low-level operation payload или workflow step.
- `workflow definition`: versioned analyst-facing схема оркестрации, переиспользуемая между несколькими доменными контекстами.
- `decision resource`: versioned business-rule layer, которую workflow и binding surfaces pin-ят как reusable policy.
- `organization`: master-справочник организаций, из которых собираются пулы.
- `pool`: конкретный graph/контур распределения между организациями.
- `topology template`: reusable structural шаблон topology graph для пула.
- `execution pack` / `binding profile`: reusable execution/binding пакет, который связывает topology slots, workflow lineage и pinned reusable references.
- `workflow binding`: pool-local attachment, который активирует reusable execution logic для конкретного `pool`.
- `pool run`: экземпляр фактического исполнения, где orchestration и 1C side effects уже происходят на runtime уровне.
- `master data`: parties, items, contracts, tax profiles и related sync flows, которые подпитывают pool execution.

## Реально существующие product surfaces на текущей ветке

Источник UI-маршрутов: [frontend/src/App.tsx](../../frontend/src/App.tsx).

### Операторские и runtime surfaces

- `/operations`
- `/artifacts`
- `/system-status`
- `/service-mesh`

### Базы и инфраструктурные surfaces

- `/databases`
- `/clusters`
- `/extensions`

### Analyst-facing authoring surfaces

- `/workflows`
- `/templates`
- `/decisions`

### Pool domain surfaces

- `/pools/catalog`
- `/pools/templates`
- `/pools/topology-templates`
- `/pools/execution-packs`
- `/pools/master-data`
- `/pools/runs`

### Admin и governance surfaces

- `/rbac`
- `/users`
- `/dlq`
- `/settings/runtime`
- `/settings/driver-catalogs`
- `/settings/command-schemas`
- `/settings/timeline`

## Где искать source-of-truth по домену

- UI route inventory: [frontend/src/App.tsx](../../frontend/src/App.tsx)
- Domain intent и project context: [openspec/project.md](../../openspec/project.md)
- Текущий shipped contract: `openspec/specs/**`
- Planned / in-flight surfaces: `openspec/changes/**`
- Live execution graph для approved work: `.beads/` и `bd ready`
- Supplemental human-readable overview: [README.md](../../README.md)

## Как различать shipped, active change и historical context

- `Shipped / current branch surface`: есть checked-in route, entry point или реализация в коде и/или current contract в `openspec/specs/**`.
- `Active change surface`: описан в `openspec/changes/**`; это планируемый или in-flight contract, а не автоматически shipped behavior. Всегда проверяй `openspec list`.
- `Historical / archived context`: находится в `openspec/changes/archive/**`, legacy docs или старом roadmap-контексте; используй только как объясняющий фон, а не как текущий source-of-truth.

## Быстрые next steps

- Если вопрос про архитектуру и runtime boundaries: открой [ARCHITECTURE_MAP.md](./ARCHITECTURE_MAP.md).
- Если нужно выбрать первый рабочий маршрут под тип задачи: открой [TASK_ROUTING.md](./TASK_ROUTING.md).
- Если требуется понять, как запускать и проверять изменение: открой [RUNBOOK.md](./RUNBOOK.md) и [VERIFY.md](./VERIFY.md).
