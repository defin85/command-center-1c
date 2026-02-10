# Change: Templates-first для extensions и удаление runtime actions

## Why
Текущая модель управления расширениями и флагами использует две конкурирующие плоскости:
- `action_catalog` как runtime-источник для ручных запусков,
- `template`/workflow как источник для orchestration.

Это создаёт конфликт source of truth и приводит к недетерминированному runtime-поведению.

Целевая модель:
- атомарные операции — из `templates`,
- `action_catalog` не участвует в runtime для `extensions.*`,
- `/extensions` и `/databases` используют единый template-based execution path.

## What Changes
- Зафиксировать `templates` (`surface=template`) как единственный runtime source of truth атомарных операций для домена extensions.
- Перевести `extensions.plan/apply` для `extensions.set_flags` на template-based резолв (через `template_id` + runtime input), а не через `action_id` из action catalog.
- Удалить runtime execution path через `ui/action-catalog` для `extensions.*`.
- Полностью отключить `action_catalog` для runtime execution `extensions.*` (в `/extensions` и `/databases`).
- Выполнить одномоментный cutover: без compatibility adapters, dual-read, fallback path и MVP-режима.

## Breaking Changes
- Контракт `POST /api/v2/extensions/plan/` для `capability=extensions.set_flags` меняется: primary contract становится template-based (`template_id` + runtime input), зависимость от `action_id` как runtime source снимается.
- `extensions.*` действия из `/api/v2/ui/action-catalog/` перестают быть исполняемым источником для `/extensions` и `/databases`.
- Запросы `extensions.set_flags` по старому `action_id`-контракту (без template-based полей) отклоняются fail-closed.

## Impact
- Affected specs:
  - `operation-templates`
  - `extensions-plan-apply`
  - `extensions-overview`
  - `extensions-action-catalog`
  - `ui-action-catalog-editor`
- Affected code:
  - Backend: `orchestrator/apps/api_v2/views/extensions_plan_apply.py`
  - Backend: runtime resolution for extensions executions
  - Frontend: `frontend/src/pages/Extensions/**`
  - Frontend: `frontend/src/pages/Databases/**`
  - Contracts: `contracts/orchestrator/openapi.yaml`

## Dependencies
- Этот change supersedes intent из `add-operations-manual-extensions-set-flags-run`.
- Должен быть согласован с `refactor-extensions-set-flags-workflow-source-of-truth`.

## Non-Goals
- Удаление action catalog как механизма для всех других доменов в рамках этого change.
- Проектирование универсального слоя manual contracts для всех capability.
- Редизайн workflow engine или DAG-модели.
