# UX Baseline Audit (refactor-04)

Дата фиксации: 2026-02-23
Источник: baseline-capture через Playwright (`openspec/changes/refactor-04-pools-ui-declutter/artifacts/scripts/pools-ui-baseline-capture.spec.ts`)

## Скриншоты
- `/pools/catalog`: `openspec/changes/refactor-04-pools-ui-declutter/artifacts/2026-02-23-baseline/pools-catalog-baseline.png`
- `/pools/runs`: `openspec/changes/refactor-04-pools-ui-declutter/artifacts/2026-02-23-baseline/pools-runs-baseline.png`
- `/pools/templates`: `openspec/changes/refactor-04-pools-ui-declutter/artifacts/2026-02-23-baseline/pools-templates-baseline.png`

## Сценарный аудит

### `/pools/catalog`
- На одном экране одновременно присутствуют независимые рабочие зоны: `Organizations`, `Organization Details`, `Pools`, `Topology snapshot editor`, `Pool Graph`.
- Для сценария "создать/исправить организацию" оператор параллельно видит topology-форму с `nodes/edges` и JSON-полями, не относящимися к текущему действию.
- Topology editor показывает advanced поля (`metadata`, `document_policy`) сразу, без progressive disclosure.

### `/pools/runs`
- Экран одновременно содержит `Create / Refresh Run`, `Pool Graph`, `Runs`, `Execution Provenance / Report`, `Safe Mode Actions`, `Retry Failed Targets`.
- Тяжёлые diagnostics блоки (`Run Input`, `Validation Summary`, `Publication Summary`, `Step Diagnostics`) раскрыты в основном потоке и конкурируют с safe/retry действиями.
- Стадии lifecycle (create/inspect/safe/retry) не разделены визуально: оператор переключает контекст по длинной прокрутке.

### `/pools/templates`
- Базовый edit-flow уже присутствует и рабочий: таблица + `Edit` action + modal prefill + JSON поля.
- Страница заметно компактнее `catalog/runs`, но требует регрессионного удержания после declutter соседних страниц.

## Вывод baseline
- Основная перегрузка подтверждена на `/pools/catalog` и `/pools/runs`: множественные независимые сценарии и advanced diagnostics отображаются одновременно.
- Целевая декомпозиция для refactor-04: task/stage segmentation + progressive disclosure без потери текущих операций.
