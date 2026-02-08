## 1. Spec Alignment
- [x] 1.1 Обновить `operation-templates`: зафиксировать `/templates` как один список exposure с фильтром `surface`, без tabs/pages.
- [x] 1.2 Обновить `ui-action-catalog-editor`: staff-only action editing выполняется в том же list+editor flow, что и templates.

## 2. Frontend Refactor (`/templates`)
- [x] 2.1 Убрать page-level Tabs (`Templates` / `Action Catalog`) и заменить на единый `surface` filter control.
- [x] 2.2 Оставить единый table/list shell, переключающий dataset и колонки в зависимости от `surface`.
- [x] 2.3 Сохранить единый `OperationExposureEditorModal` для create/edit в обоих surfaces.
- [x] 2.4 Синхронизировать `surface` с URL query (`?surface=...`) и обеспечить fallback на `template` для non-staff.
- [x] 2.5 Убедиться, что non-staff не триггерит action-catalog management запросы.

## 3. Tests
- [x] 3.1 Обновить browser тесты `/templates`: вместо tabs проверить filter-based UX.
- [x] 3.2 Добавить/обновить сценарии deep-link (`/templates?surface=action_catalog`) для staff/non-staff.
- [x] 3.3 Проверить, что единый editor shell используется в обоих surfaces.

## 4. Validation
- [x] 4.1 `openspec validate refactor-unify-exposure-list-ui --strict --no-interactive`
- [x] 4.2 Прогнать релевантные frontend тесты на routing/permissions/editor flow.
