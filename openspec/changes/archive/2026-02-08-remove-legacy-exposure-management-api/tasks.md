## 1. Spec & Contract Alignment
- [x] 1.1 Обновить `operation-definitions-catalog`: operation-catalog API становится primary management API для surfaces `template` и `action_catalog` с surface-aware RBAC.
- [x] 1.2 Обновить `operation-templates`: template management выполняется через unified exposure API, legacy template CRUD/list endpoint'ы де-комиссены.
- [x] 1.3 Обновить `ui-action-catalog-editor`: editor hints доступны через generic endpoint `/ui/operation-exposures/editor-hints/`.
- [x] 1.4 Обновить OpenAPI и сгенерированные клиенты под новые/удалённые пути.

## 2. Backend API Unification
- [x] 2.1 Расширить `operation_catalog` view: surface-aware authorization для list/upsert/publish (`template` по template permissions, `action_catalog` staff-only).
- [x] 2.2 Добавить generic hints endpoint `GET /api/v2/ui/operation-exposures/editor-hints/` (staff-only).
- [x] 2.3 Удалить из URL/router и backend реализации legacy endpoint `/api/v2/ui/action-catalog/editor-hints/`.
- [x] 2.4 Де-комиссить legacy template CRUD/list endpoints в `/api/v2/templates/*` (list/create/update/delete).
- [x] 2.5 Сохранить runtime endpoint `/api/v2/ui/action-catalog/` без изменений.

## 3. Frontend Migration & Cleanup
- [x] 3.1 Перевести `/templates` list/create/update/delete на operation-catalog API (surface=`template`).
- [x] 3.2 Переименовать/обновить hook для hints на generic (`useOperationExposureEditorHints`) и убрать action-specific binding.
- [x] 3.3 Удалить legacy template API query hooks, которые дублируют unified management path.
- [x] 3.4 Обновить browser/unit тесты и mock routes под новые endpoint paths.

## 4. Verification
- [x] 4.1 Backend тесты: RBAC по surfaces, отказ на deprecated/удалённых endpoint’ах, hints endpoint.
- [x] 4.2 Frontend тесты: templates CRUD через unified API + editor hints через generic path.
- [x] 4.3 `openspec validate remove-legacy-exposure-management-api --strict --no-interactive`
