# Change: Templates-only execution и decommission Action Catalog

## Why
Система сейчас одновременно использует `templates` и `action_catalog` для запуска атомарных операций, что создаёт два конкурирующих runtime source of truth, конфликтующий UX и недетерминированный execution path.

Нужно выполнить полный переход на одну модель:
- атомарные операции исполняются только из `templates`,
- workflow управляет только цепочками (оркестрацией) поверх template-based атомарных шагов,
- Operations/manual execution использует тот же template-based контракт,
- `action_catalog` удаляется как runtime и management сущность.

## What Changes
- Полностью вывести `action_catalog` из runtime и management контрактов.
- Зафиксировать `operation_exposure(surface="template")` как единственный исполняемый источник атомарных операций.
- Перевести `POST /api/v2/extensions/plan/` и `POST /api/v2/extensions/apply/` на template-based контракт (`template_id` + runtime input), без `action_id`.
- Убрать execution path `extensions.*` через `GET /api/v2/ui/action-catalog/` и удалить endpoint из публичного контракта.
- Перевести `/templates` в templates-only экран (без mixed surfaces и без Action Catalog controls), переиспользуя существующий editor shell.
- Перевести `/extensions` и `/databases` на ручные операции по явному контракту manual actions, но с template-based запуском.
- Выполнить одномоментный cutover в одном change без MVP, fallback, dual-path и backward-совместимости для `action_catalog` runtime-контрактов.

## Breaking Changes
- `POST /api/v2/extensions/plan/`:
  - `action_id` удаляется из runtime-контракта,
  - вводится обязательный template-based контракт для `extensions.*`.
- `GET /api/v2/ui/action-catalog/` удаляется из поддерживаемого API-контракта.
- `operation-catalog/exposures` больше не поддерживает `surface=action_catalog`.
- `/templates?surface=action_catalog` и все action-catalog UI flows удаляются.
- Legacy-клиенты, отправляющие `action_id` или использующие action-catalog surface/endpoint, получают fail-closed ошибки (`400/404/410` по конкретному контракту endpoint-а).

## Impact
- Affected specs:
  - `operation-definitions-catalog`
  - `operation-templates`
  - `extensions-plan-apply`
  - `extensions-overview`
  - `extensions-action-catalog`
  - `ui-action-catalog-editor`
- Affected code:
  - Backend: `orchestrator/apps/api_v2/views/extensions_plan_apply.py`
  - Backend: `orchestrator/apps/api_v2/views/ui/actions.py`
  - Backend: `orchestrator/apps/api_v2/views/operation_catalog.py`
  - Backend: `orchestrator/apps/templates/operation_catalog_service.py`
  - Backend model/migrations: `orchestrator/apps/templates/models.py` и связанные миграции
  - Frontend: `frontend/src/pages/Templates/**`, `frontend/src/pages/Extensions/**`, `frontend/src/pages/Databases/**`
  - Frontend API/query: `frontend/src/api/queries/ui.ts`, generated client/types
  - Contracts/docs/tests: `contracts/orchestrator/openapi.yaml`, `docs/**`, `frontend/tests/**`, `orchestrator/apps/**/tests/**`

## Dependencies
- Этот change supersedes незавершённый `refactor-extensions-templates-first-manual-contracts`.
- Реализация выполняется целиком в рамках одного change (single cutover scope).

## Non-Goals
- Поэтапный rollout, canary и dual-read модели.
- Сохранение совместимости с action-catalog runtime flow.
- Введение второго временного контракта manual operations (MVP-слоя).
