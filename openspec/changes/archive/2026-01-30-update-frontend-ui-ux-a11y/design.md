# Design: Приведение UI к Web Interface Guidelines (минимальные правки)

## Источник правил
Vercel Web Interface Guidelines (актуальная версия):
`https://raw.githubusercontent.com/vercel-labs/web-interface-guidelines/main/command.md`

## Подход
- Минимальные правки: добавление `aria-label`, замена кликабельных не-кнопок на `<Button>`, добавление keyboard handlers там, где остаётся `role="button"`.
- Избегаем внедрения новых UI библиотек или больших рефакторингов.

## Примечание о пересечениях
Если параллельно выполняется `update-frontend-performance`, line numbers в Findings могут сдвигаться (особенно в `frontend/src/stores/serviceMeshManager.ts` и хуках). В этом случае Findings нужно пересверять по файлам через поиск/контекст, а не по абсолютным строкам.

## Findings (file:line)

## frontend/src/pages/Dashboard/Dashboard.tsx
frontend/src/pages/Dashboard/Dashboard.tsx:95 - интерактивная иконка (`ReloadOutlined`) без семантики кнопки/клавиатуры; заменить на `<Button>` или добавить `role+tabIndex+onKeyDown` + `aria-label`
frontend/src/pages/Dashboard/Dashboard.tsx:117 - `role="button"` без keyboard handler (Enter/Space) → добавить `onKeyDown` или заменить на `<Button>`

## frontend/src/components/layout/MainLayout.tsx
frontend/src/components/layout/MainLayout.tsx:165 - бренд в `<div>`; для навигации лучше `<a>`/`<Link>` (Cmd/Ctrl+click и семантика)
frontend/src/components/layout/MainLayout.tsx:168 - Popover trigger на `<Tag>` (нефокусируемый/не кнопка) → заменить trigger на `<Button>`/`<a>` или добавить доступность (tabIndex/role/keyboard)
frontend/src/components/layout/MainLayout.tsx:197 - кликабельный `<Tag>` (Popover/Tooltip) без keyboard support → аналогично, сделать фокусируемым и управляемым с клавиатуры
frontend/src/components/layout/MainLayout.tsx:226 - основной контент не размечен как `<main>` и нет skip link → добавить skip link на уровне `App`/`MainLayout` и семантический контейнер

## frontend/src/pages/Workflows/WorkflowExecutions.tsx
frontend/src/pages/Workflows/WorkflowExecutions.tsx:280 - icon-only `<Button>` без `aria-label` (навигация к workflow)
frontend/src/pages/Workflows/WorkflowExecutions.tsx:285 - icon-only `<Button>` без `aria-label` (cancel)
frontend/src/pages/Workflows/WorkflowExecutions.tsx:334 - `Input` без связанного `<label>`/`aria-label` (есть только визуальный текст "Workflow ID") → добавить `aria-label` или label/linkage

## frontend/src/pages/Operations/components/OperationsFilters.tsx
frontend/src/pages/Operations/components/OperationsFilters.tsx:12 - `Input` без label/aria-label (Operation ID фильтр)
frontend/src/pages/Operations/components/OperationsFilters.tsx:19 - `Input` без label/aria-label (Workflow execution ID фильтр)
frontend/src/pages/Operations/components/OperationsFilters.tsx:26 - `Input` без label/aria-label (Node ID фильтр)

## frontend/src/pages/Operations/components/OperationsTableColumns.tsx
frontend/src/pages/Operations/components/OperationsTableColumns.tsx:53 - icon-only `<Button>` без `aria-label` (filter by workflow)
frontend/src/pages/Operations/components/OperationsTableColumns.tsx:63 - icon-only `<Button>` без `aria-label` (filter by node)

## frontend/src/pages/Databases/Databases.tsx
frontend/src/pages/Databases/Databases.tsx:458 - `Select` без label/aria-label (фильтр по кластеру рядом с заголовком) → добавить `aria-label`

## frontend/src/pages/Databases/components/useDatabasesColumns.tsx
frontend/src/pages/Databases/components/useDatabasesColumns.tsx:242 - icon-only `<Button>` без `aria-label` (credentials)
frontend/src/pages/Databases/components/useDatabasesColumns.tsx:250 - icon-only `<Button>` без `aria-label` (extensions)

## frontend/src/stores/serviceMeshManager.ts
frontend/src/stores/serviceMeshManager.ts:303 - "..." → "…" (loading/reconnecting copy)

## frontend/src/pages/Clusters/Clusters.tsx
frontend/src/pages/Clusters/Clusters.tsx:194 - "..." → "…" (loading copy)
frontend/src/pages/Clusters/Clusters.tsx:245 - "..." → "…" (loading copy)
frontend/src/pages/Clusters/Clusters.tsx:255 - "..." → "…" (loading copy)

## frontend/src/components/service-mesh/RecentOperationsTable.tsx
frontend/src/components/service-mesh/RecentOperationsTable.tsx:134 - "..." → "…" (truncated id)

## frontend/src/components/WorkflowTracker/index.tsx
frontend/src/components/WorkflowTracker/index.tsx:160 - "..." → "…" (empty state copy)

## frontend/src/components/workflow/nodes/OperationNode.tsx
frontend/src/components/workflow/nodes/OperationNode.tsx:54 - "..." → "…" (truncation)
frontend/src/components/workflow/nodes/OperationNode.tsx:107 - "Executing..." → "Executing…" (loading copy)
frontend/src/components/workflow/nodes/OperationNode.tsx:131 - copy "click to view details" без явного onClick/Link → либо добавить действие, либо исправить copy
