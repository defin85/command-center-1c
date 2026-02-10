# Change: Templates-first для extensions + contract-driven manual actions в `/operations`

## Why
Текущая модель управления расширениями и флагами использует две конкурирующие плоскости:
- `action_catalog` как runtime-источник для ручных запусков,
- `template`/workflow как источник для orchestration.

Это размывает роли экранов (`/extensions`, `/operations`, `/templates`), усложняет контракты и приводит к конфликтам source of truth.

Целевая модель:
- атомарные операции — из `templates`,
- `workflows` — запуск цепочек атомарных операций,
- `operations` — ручной запуск атомарных операций по явному UI-контракту,
- ручные действия описаны как hardcoded contracts в UI, а binding заполняет оператор.

## What Changes
- Зафиксировать `templates` (`surface=template`) как единственный runtime source of truth атомарных операций для домена extensions.
- Для ручного запуска в `/operations` ввести hardcoded manual contracts (например, `extensions.set_flags.v1`) с явной схемой:
  - required runtime input,
  - required binding slots,
  - правила preview/execute.
- Перевести `extensions.plan/apply` для `extensions.set_flags` на template-based резолв (через `template_id` + `bindings`), а не через `action_id` из action catalog.
- Переформулировать `/extensions` как workflow-first экран массового rollout; ручной targeted fallback выполнять через `/operations`.
- Деприоритизировать `action_catalog` для `extensions.*` (не использовать как runtime-контур для `/extensions` и `/databases`).
- Подготовить миграционный путь с диагностикой существующих `action_catalog` exposure для `extensions.*`.

## Breaking Changes
- Контракт `POST /api/v2/extensions/plan/` для `capability=extensions.set_flags` меняется: primary contract становится template-based (`template_id` + `bindings`), зависимость от `action_id` как runtime source снимается.
- `/extensions` больше не является местом ручного targeted запуска атомарной операции set_flags.
- `extensions.*` действия из `/api/v2/ui/action-catalog/` перестают быть исполняемым источником для `/extensions` и `/databases`.

## Impact
- Affected specs:
  - `operation-templates`
  - `extensions-plan-apply`
  - `extensions-overview`
  - `extensions-action-catalog`
  - `ui-action-catalog-editor`
  - `operations-manual-contracts` (new)
- Affected code:
  - Backend: `orchestrator/apps/api_v2/views/extensions_plan_apply.py`
  - Backend: runtime resolution for extensions executions
  - Frontend: `frontend/src/pages/Extensions/**`
  - Frontend: `frontend/src/pages/Operations/**`
  - Frontend: `frontend/src/pages/Databases/**`
  - Contracts: `contracts/orchestrator/openapi.yaml`

## Dependencies
- Этот change supersedes intent из `add-operations-manual-extensions-set-flags-run` (manual fallback остаётся, но источник атомарной операции переводится на templates-first контракт).
- Должен быть согласован с `refactor-extensions-set-flags-workflow-source-of-truth`.

## Non-Goals
- Удаление action catalog как механизма для всех других доменов в рамках этого change.
- Полный перенос всех extension UX-сценариев в `/operations`.
- Редизайн workflow engine или DAG-модели.
