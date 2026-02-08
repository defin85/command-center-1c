# Change: Унифицировать editor Templates/Actions и убрать дублирование `executor.kind`/`driver`

## Why
Сейчас `/templates` формально единый экран, но внутри остаются два разных UX:
- `Templates` использует modal на `DriverCommandBuilder`;
- `Action Catalog` использует более современный tabbed editor (`Basics/Executor/Params/Safety/Preview`).

Это создаёт когнитивный разрыв для операторов и дублирование логики в коде.
Дополнительно в редакторах остаётся разночтение `executor.kind` и `driver`, хотя для текущих поддерживаемых executors это фактически жёсткое соответствие.

## What Changes
- Сделать единый modal editor для surfaces `template` и `action_catalog` на базе action-style UX (tabbed editor).
- Перевести редактирование template exposure на тот же editor shell и тот же adapter/serializer pipeline, что и для action exposure.
- Убрать ручной выбор `driver` в editor там, где он однозначно определяется `executor.kind`:
  - `ibcmd_cli -> ibcmd`
  - `designer_cli -> cli`
  - `workflow -> (driver не применяется)`
- Зафиксировать canonical executor contract: `driver` не является отдельным пользовательским измерением для canonical kinds, а derivation/normalization выполняется на backend.
- Добавить миграцию/нормализацию существующих данных unified store и diagnostics для конфликтных legacy записей (`kind/driver mismatch`).
- Обновить e2e/unit/backend тесты и документацию под единый editor UX и новый executor mapping contract.

## Impact
- Affected specs:
  - `operation-templates`
  - `ui-action-catalog-editor`
  - `operation-definitions-catalog`
- Affected code:
  - Frontend: `frontend/src/pages/Templates/TemplatesPage.tsx`, `frontend/src/pages/Settings/ActionCatalogPage.tsx`, `frontend/src/pages/Settings/actionCatalog/**`, `frontend/src/lib/commandConfigAdapter.ts`
  - Backend: `orchestrator/apps/api_v2/views/operation_catalog.py`, `orchestrator/apps/templates/operation_catalog_service.py`, `orchestrator/apps/templates/models.py`, migration path в `orchestrator/apps/templates/migrations/**`
  - Tests/contracts: `frontend/tests/browser/**`, `frontend/src/pages/**/__tests__/**`, `orchestrator/apps/**/tests/**`, `contracts/**` (если изменится wire shape)

## Breaking Notes
- Для editor UX обратная совместимость со старой template-modal (`DriverCommandBuilder` shell) не сохраняется.
- Если в API/постоянном контракте будет убран пользовательский `driver` для canonical kinds, это считается breaking-изменением для клиентов, которые полагались на ручную передачу `driver`.
