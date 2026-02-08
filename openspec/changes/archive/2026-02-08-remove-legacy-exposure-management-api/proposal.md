# Change: Удалить legacy management API и оставить единый backend-контур для exposure

## Why
После UI-консолидации остаётся backend-дублирование:
- template management живёт в `/api/v2/templates/*`,
- action management живёт в `/api/v2/operation-catalog/*`,
- editor hints остаются под action-specific path `/api/v2/ui/action-catalog/editor-hints/`.

Это поддерживает лишнюю сложность в API и коде, хотя доменная сущность уже единая (`operation_definition` + `operation_exposure`).

## What Changes
- Сделать `/api/v2/operation-catalog/*` основным management API для обеих surfaces (`template`, `action_catalog`) с surface-aware RBAC.
- Добавить generic endpoint для editor hints:
  - `GET /api/v2/ui/operation-exposures/editor-hints/` (staff-only),
  - убрать зависимость frontend от action-specific hints path.
- Перевести `/templates` UI CRUD/list на unified operation-catalog management API.
- Де-комиссить legacy template CRUD/list endpoints:
  - `/api/v2/templates/list-templates/`
  - `/api/v2/templates/create-template/`
  - `/api/v2/templates/update-template/`
  - `/api/v2/templates/delete-template/`
- Удалить старый action-specific hints endpoint:
  - `/api/v2/ui/action-catalog/editor-hints/`

## Impact
- Affected specs:
  - `operation-definitions-catalog`
  - `operation-templates`
  - `ui-action-catalog-editor`
- Affected code:
  - Backend: `orchestrator/apps/api_v2/views/operation_catalog.py`
  - Backend: `orchestrator/apps/api_v2/views/templates.py`
  - Backend: `orchestrator/apps/api_v2/views/ui/actions.py`, `orchestrator/apps/api_v2/urls.py`
  - Frontend: `frontend/src/api/queries/templates.ts`, `frontend/src/api/queries/ui.ts`, `frontend/src/pages/Templates/**`
  - Contracts: `contracts/orchestrator/openapi.yaml`, generated clients
- Breaking notes:
  - template CRUD/list через `/api/v2/templates/*` удаляются;
  - action-specific hints path удаляется.

## Non-Goals
- Удаление runtime read-model endpoint `/api/v2/ui/action-catalog/` (используется runtime UX `/databases`).
- Изменение бизнес-логики effective action catalog и execution plan/apply.
