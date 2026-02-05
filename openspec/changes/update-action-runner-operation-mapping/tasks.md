## 1. Backend
- [x] Обновить schema `ui.action_catalog` (v1): разрешить `executor.fixed.apply_mask` (object с ключами `active|safe_mode|unsafe_action_protection`, boolean) для actions с `capability="extensions.set_flags"`.
- [x] Убрать fail-closed update-time валидацию “duplicate reserved capability” (оставить детерминизм через runtime ambiguity errors).
- [x] `POST /api/v2/extensions/plan/`: добавить `action_id` (string) и правило резолва:
  - `action_id` → точный match по `extensions.actions[].id`,
  - иначе `capability` → если 0 → `MISSING_ACTION`, если 1 → OK, если >1 → `AMBIGUOUS_ACTION` (+ candidates ids).
- [x] Поддержать presets: если request `apply_mask` отсутствует, а выбранный action содержит `executor.fixed.apply_mask` — использовать его.
- [x] Обновить apply-flow (если нужен) так, чтобы plan сохранял `action_id`/маску и apply был детерминирован.
- [x] Обновить/добавить тесты:
  - обновить тест на “reject duplicate reserved capability”,
  - добавить тест на `AMBIGUOUS_ACTION` при нескольких actions для `extensions.set_flags` и отсутствии `action_id`,
  - добавить тест на `executor.fixed.apply_mask` default.

## 2. Frontend
- [x] Убрать клиентскую валидацию duplicate reserved capability в `frontend/src/pages/Settings/actionCatalog/actionCatalogValidation.ts`.
- [x] Убрать проверку reserved duplicate в modal Add/Edit action (если она есть) и полагаться на backend validation.
- [x] В `Extensions` UI: выбирать `extensions.set_flags` action по `action_id` (dropdown или 3 кнопки пресетов) и вызывать plan/apply детерминированно.
- [ ] (Опционально) Выделить общий `ActionRunner` hook из `frontend/src/pages/Databases/components/useExtensionsActions.tsx` для reuse в `Extensions`.

## 3. Spec & Validation
- [x] Добавить delta-specs для `extensions-action-catalog`, `extensions-plan-apply`, `ui-action-catalog-editor`.
- [x] Прогнать `openspec validate update-action-runner-operation-mapping --strict --no-interactive`.
