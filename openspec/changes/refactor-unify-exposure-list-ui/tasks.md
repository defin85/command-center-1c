## 1. Spec Alignment
- [ ] 1.1 Обновить `operation-templates`: зафиксировать `/templates` как один список exposure с фильтром `surface`, без tabs/pages.
- [ ] 1.2 Обновить `ui-action-catalog-editor`: staff-only action editing выполняется в том же list+editor flow, что и templates.

## 2. Frontend Refactor (`/templates`)
- [ ] 2.1 Убрать page-level Tabs (`Templates` / `Action Catalog`) и заменить на единый `surface` filter control.
- [ ] 2.2 Оставить единый table/list shell, переключающий dataset и колонки в зависимости от `surface`.
- [ ] 2.3 Сохранить единый `OperationExposureEditorModal` для create/edit в обоих surfaces.
- [ ] 2.4 Синхронизировать `surface` с URL query (`?surface=...`) и обеспечить fallback на `template` для non-staff.
- [ ] 2.5 Убедиться, что non-staff не триггерит action-catalog management запросы.

## 3. Tests
- [ ] 3.1 Обновить browser тесты `/templates`: вместо tabs проверить filter-based UX.
- [ ] 3.2 Добавить/обновить сценарии deep-link (`/templates?surface=action_catalog`) для staff/non-staff.
- [ ] 3.3 Проверить, что единый editor shell используется в обоих surfaces.

## 4. Validation
- [ ] 4.1 `openspec validate refactor-unify-exposure-list-ui --strict --no-interactive`
- [ ] 4.2 Прогнать релевантные frontend тесты на routing/permissions/editor flow.
