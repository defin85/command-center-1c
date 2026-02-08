## 1. Spec & Contract Alignment
- [ ] 1.1 Обновить `operation-definitions-catalog`: operation-catalog API становится primary management API для surfaces `template` и `action_catalog` с surface-aware RBAC.
- [ ] 1.2 Обновить `operation-templates`: template management выполняется через unified exposure API, legacy template CRUD/list endpoint'ы де-комиссены.
- [ ] 1.3 Обновить `ui-action-catalog-editor`: editor hints доступны через generic endpoint `/ui/operation-exposures/editor-hints/`.
- [ ] 1.4 Обновить OpenAPI и сгенерированные клиенты под новые/удалённые пути.

## 2. Backend API Unification
- [ ] 2.1 Расширить `operation_catalog` view: surface-aware authorization для list/upsert/publish (`template` по template permissions, `action_catalog` staff-only).
- [ ] 2.2 Добавить generic hints endpoint `GET /api/v2/ui/operation-exposures/editor-hints/` (staff-only).
- [ ] 2.3 Удалить из URL/router и backend реализации legacy endpoint `/api/v2/ui/action-catalog/editor-hints/`.
- [ ] 2.4 Де-комиссить legacy template CRUD/list endpoints в `/api/v2/templates/*` (list/create/update/delete).
- [ ] 2.5 Сохранить runtime endpoint `/api/v2/ui/action-catalog/` без изменений.

## 3. Frontend Migration & Cleanup
- [ ] 3.1 Перевести `/templates` list/create/update/delete на operation-catalog API (surface=`template`).
- [ ] 3.2 Переименовать/обновить hook для hints на generic (`useOperationExposureEditorHints`) и убрать action-specific binding.
- [ ] 3.3 Удалить legacy template API query hooks, которые дублируют unified management path.
- [ ] 3.4 Обновить browser/unit тесты и mock routes под новые endpoint paths.

## 4. Verification
- [ ] 4.1 Backend тесты: RBAC по surfaces, отказ на deprecated/удалённых endpoint’ах, hints endpoint.
- [ ] 4.2 Frontend тесты: templates CRUD через unified API + editor hints через generic path.
- [ ] 4.3 `openspec validate remove-legacy-exposure-management-api --strict --no-interactive`
