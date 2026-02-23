# Target IA Structure (refactor-04)

Дата: 2026-02-23
Назначение: зафиксировать целевую информационную архитектуру до кодовых правок UI.

## `/pools/catalog` (task-oriented zones)

Primary zones (tabs):
- `Organizations`
- `Pools`
- `Topology Editor`
- `Graph Preview`

Правила:
- В каждом табе показываются только релевантные controls и таблицы текущей задачи.
- `selectedPoolId` и `selectedOrganizationId` остаются единым page context между табами.
- Mutating guard (`staff without active tenant`) сохраняется в зонах с mutating controls.

Advanced disclosure:
- В `Topology Editor` скрыть advanced JSON-блоки по умолчанию.
- Для `nodes[].metadata`, `edges[].metadata`, `edges[].document_policy` использовать явные toggles/Collapse.

## `/pools/runs` (stage-based workflow)

Primary stages (tabs):
- `Create`
- `Inspect`
- `Safe Actions`
- `Retry Failed`

Правила:
- `selectedRunId` сохраняется единым контекстом при переходах между стадиями.
- Create stage содержит только запуск run + минимальный контекст пула.
- Inspect stage содержит runs table + provenance/report.
- Safe stage содержит только confirm/abort контекст и статусы.
- Retry stage содержит только retry-форму и итог accepted/summary.

Advanced disclosure:
- В Inspect stage diagnostics тяжелые блоки (`Run Input`, `Validation Summary`, `Publication Summary`, `Step Diagnostics`) скрыты по умолчанию и раскрываются по явному действию.
- Базовая сводка статуса (tags + compact descriptions) остаётся видимой без раскрытия.

## `/pools/templates` (baseline retention)

- Сохраняется текущий edit-flow: таблица -> `Edit` -> modal prefill -> save/update.
- JSON validation (`schema_json`, `metadata_json`) остаётся обязательной перед submit.
- Допускается только минимальная UX-полировка без расширения scope.

## Primary vs Secondary Actions

Primary actions:
- Catalog: `Create org`, `Edit org`, `Create pool`, `Edit pool`, `Save topology`.
- Runs: `Create / Upsert Run`, `Confirm publication`, `Abort publication`, `Retry Failed`.
- Templates: `Create Template`, `Save`.

Secondary actions:
- Refresh/load actions.
- View-only diagnostics and JSON panels.
- Optional metadata/document_policy editing.

## Acceptance markers for implementation

- Catalog и Runs больше не отображают все workflow-зоны одновременно.
- Advanced JSON/diagnostics не видны по умолчанию.
- Переход между зонами/стадиями не сбрасывает selected context.
