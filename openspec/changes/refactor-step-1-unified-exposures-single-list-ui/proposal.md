# Change: Шаг 1 — единый UI-реестр exposures в `/templates`

## Why
Текущая реализация формально объединяет Templates и Action Catalog, но UX по-прежнему воспринимается как “переключение режимов страницы” (`template` vs `action_catalog`).
Это не даёт эффекта единого реестра и оставляет ощущение, что мы “просто перенесли переключатель выше”.

## What Changes
- Перевести `/templates` в модель одного реестра `operation_exposure` с единой таблицей и единым toolbar.
- Сделать `surface` фасетным фильтром списка, а не page-level режимом:
  - staff: `all | template | action_catalog`,
  - non-staff: только `template`.
- Добавить явное отображение `surface` в строках списка (badge/column), чтобы mixed-list был читаемым.
- Сохранить единый `OperationExposureEditorModal` как единственный create/edit flow для обеих surfaces.
- Сохранить deep-link через query (`?surface=...`) и корректный fallback на `template` для non-staff.

## Impact
- Affected specs:
  - `operation-templates`
  - `ui-action-catalog-editor`
- Affected code:
  - `frontend/src/pages/Templates/TemplatesPage.tsx`
  - `frontend/tests/browser/action-catalog-ui.spec.ts`
  - (при необходимости) вспомогательные адаптеры `frontend/src/pages/Templates/**`

## Non-Goals
- Изменение backend API-контрактов `operation-catalog`.
- Оптимизация server-side сортировки/поиска/пагинации для mixed-surface списка.
- Удаление runtime read-model endpoints для `/databases`.
