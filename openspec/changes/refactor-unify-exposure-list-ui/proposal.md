# Change: Убрать дублирование Templates/Action Catalog в один список exposure

## Why
Сейчас `/templates` использует разделение через tabs и отдельный `ActionCatalogPage`, хотя обе поверхности управляют одной сущностью `operation_exposure`.
Это поддерживает дублирование page-level состояния, усложняет сопровождение и делает UX менее предсказуемым.

## What Changes
- Перевести `/templates` на один список exposure с фильтром `surface` (`template` / `action_catalog`), вместо отдельных tabs/pages.
- Оставить единый modal editor (`OperationExposureEditorModal`) как единственную форму create/edit для обеих поверхностей.
- Синхронизировать выбранный `surface` с URL query (`?surface=...`) для deep-link и предсказуемой навигации.
- Сохранить RBAC-семантику:
  - non-staff видит только `template`,
  - `action_catalog` доступен только staff.
- На этой фазе не менять backend-контракты (миграция API и cleanup legacy paths выносятся в отдельный change).

## Impact
- Affected specs:
  - `operation-templates`
  - `ui-action-catalog-editor`
- Affected code:
  - Frontend: `frontend/src/pages/Templates/TemplatesPage.tsx`
  - Frontend: `frontend/src/pages/Settings/ActionCatalogPage.tsx` (перестаёт быть отдельным page-level flow)
  - Frontend tests: `frontend/tests/browser/action-catalog-ui.spec.ts` и связанные сценарии `/templates`
- Contracts:
  - Без breaking API изменений в этой фазе.

## Non-Goals
- Удаление/де-прекация backend legacy management endpoints.
- Переименование UI API `action-catalog` endpoint’ов.
- Изменение runtime read-model endpoint `/api/v2/ui/action-catalog/` для `/databases`.
