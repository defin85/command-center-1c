# Change: Templates-only manual operations и полный decommission Action Catalog

## Why
Текущая архитектура смешивает два разных execution source of truth (`templates` и `action_catalog`), из-за чего:
- контракты API/UX расходятся,
- появляются неявные runtime-resolve пути,
- поддержка и аудит поведения усложняются.

Нужен единый platform-level контракт:
- атомарные операции исполняются только из `templates`,
- ручные операции запускаются через жёстко заданный (hardcoded) слой manual operations,
- пользователь подставляет конкретные templates и вручную настраивает mapping raw driver output -> canonical contract,
- `action_catalog` удаляется как capability платформы.

## What Changes
- Полностью удалить `action_catalog` как platform capability (runtime + management + UI editor).
- Удалить `GET /api/v2/ui/action-catalog/` из поддерживаемого API (стабильный decommission-код: `404`).
- Удалить `surface=action_catalog` из `operation-catalog` контрактов и из domain model (`OperationExposure`).
- Выполнить hard delete legacy `action_catalog` exposure-данных в миграции.
- Ввести единый hardcoded слой manual operations (первый домен: `extensions`):
  - поддерживаемые manual operations: `extensions.sync`, `extensions.set_flags`,
  - legacy `extensions.list` удалить из runtime-контуров.
- Перевести `extensions.plan/apply` на единый manual-operations контракт:
  - request содержит `manual_operation`,
  - template резолвится через `template_id` (explicit override) или tenant-level preferred binding,
  - `action_id` полностью удаляется.
- Добавить tenant-scoped persist bindings: preferred `template_id` на каждую manual operation.
- Зафиксировать единый result contract слой:
  - manual operation объявляет canonical `result_contract`,
  - raw ответ драйвера маппится пользователем через mapping spec,
  - в execution metadata фиксируются contract/mapping версии.
- Перевести `/templates`, `/extensions`, `/databases` на templates-only manual execution UX.

## Breaking Changes
- `GET /api/v2/ui/action-catalog/` возвращает `404`.
- `operation-catalog/exposures` больше не принимает `surface=action_catalog`.
- `POST /api/v2/extensions/plan/`:
  - удаляется `action_id`,
  - вводится `manual_operation` + template-based resolve.
- `extensions.list` удаляется как runtime operation.
- Legacy планы/запросы action-catalog формата отклоняются fail-closed.

## Impact
- Affected specs:
  - `operation-definitions-catalog`
  - `operation-templates`
  - `extensions-plan-apply`
  - `extensions-overview`
  - `extensions-action-catalog`
  - `ui-action-catalog-editor`
  - `execution-plan-binding-provenance`
  - `command-result-snapshots`
- Affected code:
  - Backend: `orchestrator/apps/api_v2/views/extensions_plan_apply.py`
  - Backend: `orchestrator/apps/api_v2/views/ui/actions.py`
  - Backend: `orchestrator/apps/api_v2/views/operation_catalog.py`
  - Backend: `orchestrator/apps/templates/operation_catalog_service.py`
  - Backend model/migrations: `orchestrator/apps/templates/models.py` + миграции удаления `action_catalog`
  - Frontend: `frontend/src/pages/Templates/**`, `frontend/src/pages/Extensions/**`, `frontend/src/pages/Databases/**`
  - Frontend API/query: `frontend/src/api/queries/ui.ts`, generated client/types
  - Contracts/docs/tests: `contracts/orchestrator/openapi.yaml`, `docs/**`, `frontend/tests/**`, `orchestrator/apps/**/tests/**`

## Non-Goals
- MVP/fallback/dual-path rollout.
- Backward compatibility для action-catalog execution flows.
- Временные adapter-слои `action_id -> template_id`.
