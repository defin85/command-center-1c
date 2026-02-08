# Change: Унифицировать Templates и Action Catalog в единый persistent контракт

## Why
Мы дублируем одну и ту же исполняемую конфигурацию в двух хранилищах:
- `OperationTemplate` (страница `/templates`);
- `ui.action_catalog` (страница `/settings/action-catalog`).

Из-за этого появляются расхождения между реальной командой и UI-привязкой, разный lifecycle валидации, и повторяющиеся правки в двух местах.

## What Changes
- Вводится единая persistent модель для исполняемых определений:
  - `operation_definition` (что выполнять),
  - `operation_exposure` (где и как показывать/вызывать: template vs action).
- Добавляется явный unified API-контур (staff/admin) для работы с новой моделью:
  - `GET /api/v2/operation-catalog/definitions/`
  - `GET /api/v2/operation-catalog/definitions/{definition_id}/`
  - `GET /api/v2/operation-catalog/exposures/`
  - `POST /api/v2/operation-catalog/exposures/` (create/update exposure + binding с definition)
  - `POST /api/v2/operation-catalog/exposures/{exposure_id}/publish/`
  - `POST /api/v2/operation-catalog/validate/`
  - `GET /api/v2/operation-catalog/migration-issues/`
- `/templates` и `/settings/action-catalog` переходят на unified API без compatibility-адаптеров старых payload.
- Для `extensions.set_flags` сохраняется strict fail-closed контракт target binding из change `add-set-flags-target-binding-contract`; binding хранится в unified модели и используется напрямую.
- Добавляется миграция данных из:
  - `OperationTemplate`,
  - RuntimeSetting `ui.action_catalog` (global + tenant override),
  с дедупликацией определений по fingerprint и журналом проблем миграции.
- Внедряется прямой cutover: freeze legacy writes → backfill → switch reads/writes to unified → удаление legacy persistence.

## Impact
- Affected specs:
  - `extensions-action-catalog`
  - `extensions-plan-apply`
  - `ui-action-catalog-editor`
  - `operation-templates` (новая capability)
  - `operation-definitions-catalog` (новая capability)
- Affected code (ожидаемо):
  - Backend: `orchestrator/apps/templates/**`, `orchestrator/apps/runtime_settings/action_catalog.py`, `orchestrator/apps/api_v2/views/templates.py`, `orchestrator/apps/api_v2/views/ui/actions.py`, `orchestrator/apps/api_v2/views/extensions_plan_apply.py`
  - Frontend: `/templates`, `/settings/action-catalog`, shared command editor/adapters
  - Contracts: `contracts/orchestrator/openapi.yaml` + generated client types

## Dependencies
- Полностью включает требования change `add-set-flags-target-binding-contract` и заменяет его как единый путь реализации.

## Breaking Notes
- Внутренний source of truth меняется: primary persistence больше не `ui.action_catalog`.
- Legacy write/read-path для `ui.action_catalog` удаляется из активного использования.
- Контракты старых payload для action catalog и templates не поддерживаются.
- Конфигурации `extensions.set_flags` без валидного target binding не публикуются (fail-closed).
