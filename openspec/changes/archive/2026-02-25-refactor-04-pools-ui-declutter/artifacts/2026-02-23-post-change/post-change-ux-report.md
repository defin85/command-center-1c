# Post-change UX report: refactor-04 pools UI declutter

Дата: 2026-02-23

## 1. Что упрощено

### /pools/catalog
- Введены task-зоны через tabs: `Organizations`, `Pools`, `Topology Editor`, `Graph Preview`.
- Одновременно показывается только активная зона; независимые сценарии не конкурируют на одном экране.
- Advanced topology JSON (`node metadata`, `edge document policy`, `edge metadata`) скрыты по умолчанию в `Collapse`.

### /pools/runs
- Введён stage-based workflow через tabs: `Create`, `Inspect`, `Safe Actions`, `Retry Failed`.
- Общий контекст (`pool`, `date`, `refresh`) вынесен в отдельный `Run Context` блок.
- Heavy diagnostics (`Run Input`, `Validation Summary`, `Publication Summary`, `Step Diagnostics`) скрыты в `Collapse` и открываются по требованию.
- Diagnostics observability aligned с финальным контрактом: `root_operation_id`, `execution_consumer`, `lane`.
- Удалены временные diagnostics alias-ветки parsing на frontend; используется каноническая структура diagnostics payload.

### /pools/templates
- Baseline edit-flow сохранён без деградации: `Edit` action, modal prefill, submit/update.
- Контракт `PUT /api/v2/pools/schema-templates/{template_id}/` подтверждён тестами.

## 2. Smoke-проход операторских сценариев

Проверка выполнена автоматизированно через целевые тесты и backend API проверки.

### Frontend
- `cd frontend && npx vitest run src/pages/Pools/__tests__/PoolCatalogPage.test.tsx src/pages/Pools/__tests__/PoolSchemaTemplatesPage.test.tsx`
  - Result: `21 passed`
- `cd frontend && npx vitest run src/pages/Pools/__tests__/PoolRunsPage.test.tsx`
  - Result: `14 passed`

### Backend
- `cd orchestrator && ./venv/bin/pytest apps/api_v2/tests/test_intercompany_pool_runs.py`
  - Result: `69 passed`

## 3. Подтверждение снижения визуального шума

- До change ключевые controls `/pools/catalog` и `/pools/runs` одновременно отображались на одном длинном полотне.
- После change страницы разнесены на task/stage tabs, из-за чего количество одновременно видимых controls уменьшено до контекста активной задачи.
- Advanced JSON/diagnostics не мешают базовому операторскому пути и остаются доступны в один клик через disclosure.
