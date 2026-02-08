# Change: Удалить `ui.action_catalog` и объединить Templates/Actions в один UI

## Why
После перехода на unified persistent контракт (`operation_definition` + `operation_exposure`) в системе остались:
- legacy runtime setting key `ui.action_catalog`;
- отдельный UI `/settings/action-catalog`, дублирующий управление теми же action exposures.

Это увеличивает стоимость поддержки, путает операторов и оставляет технический долг, хотя source of truth уже единый.

## What Changes
- Полностью вывести из эксплуатации runtime setting key `ui.action_catalog` (registry/API override/read/write paths).
- Зафиксировать `operation_exposure(surface="action_catalog")` как единственный источник конфигурации действий.
- Удалить отдельный операторский UI `/settings/action-catalog`.
- Сделать `/templates` единым UI управления operation exposures для двух surfaces:
  - `template`
  - `action_catalog`
- Удалить frontend/backend код, тесты и контрактные ожидания, завязанные на управление actions через runtime settings.
- Обновить документацию и OpenSpec-требования под single-UI и отсутствие legacy key.

## Impact
- Affected specs:
  - `operation-templates`
  - `ui-action-catalog-editor`
  - `extensions-action-catalog`
  - `extensions-plan-apply`
  - `runtime-settings-overrides`
- Affected code:
  - Frontend: `frontend/src/App.tsx`, `frontend/src/components/layout/MainLayout.tsx`, `frontend/src/pages/Templates/**`, `frontend/src/pages/Settings/actionCatalog/**`
  - Backend: `orchestrator/apps/runtime_settings/**`, `orchestrator/apps/api_v2/views/runtime_settings.py`, `orchestrator/apps/api_v2/views/ui/actions.py`, `orchestrator/apps/templates/operation_catalog_backfill.py`
  - Contracts/tests: `contracts/**`, `orchestrator/apps/**/tests/**`, `frontend/tests/**`

## Breaking Notes
- Обратная совместимость не сохраняется.
- Route `/settings/action-catalog` удаляется как поддерживаемый entrypoint.
- Runtime setting key `ui.action_catalog` удаляется из поддерживаемых настроек.
