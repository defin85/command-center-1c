# Change: update-action-runner-operation-mapping

## Why
Сейчас UI и backend во многих местах выбирают extensions action по `capability` как по уникальному ключу. Это ограничивает нас схемой 1→1 (capability → action), но реальный кейс требует 1→N: нужно 3 пресета для `extensions.set_flags`, каждый применяет ровно один флаг (`active` / `safe_mode` / `unsafe_action_protection`).

Дополнительно:
- Валидация уникальности reserved capability сейчас либо блокирует конфигурацию, либо приводит к UX “Save disabled без понятного сообщения”.
- Логика запуска действий в UI уже частично работает по `action.id` (например, `/databases`), но extensions plan/apply всё ещё завязаны на `capability`.

## What Changes
- Разрешить несколько actions с одинаковым `capability` (включая reserved capability), сохранив уникальность только по `action.id`.
- Ввести детерминированный выбор action через `action_id` в `POST /api/v2/extensions/plan/` (и связанный apply-flow).
  - Если `action_id` не задан, а по `capability` найдено несколько candidates — fail-closed с явной ошибкой `AMBIGUOUS_ACTION`.
- Добавить “presets” для `extensions.set_flags` без изменения внешних API для обычных пользователей:
  - хранить default mask в action catalog как `executor.fixed.apply_mask`,
  - при планировании использовать request `apply_mask`, а если его нет — брать `executor.fixed.apply_mask`, иначе дефолт (все флаги).
- Обновить UI Action Catalog editor: убрать клиентскую блокировку дубликатов reserved capability и показывать понятные ошибки (backend остаётся источником истины).

## Impact
- Backend:
  - `orchestrator/apps/api_v2/views/extensions_plan_apply.py` (action resolution, новые поля запроса, ошибки ambiguity),
  - `orchestrator/apps/runtime_settings/action_catalog.py` (schema/validation для `executor.fixed.apply_mask`, снятие reserved uniqueness-валидации),
  - тесты (например `orchestrator/apps/api_v2/tests/test_ui_action_catalog.py`).
- Frontend:
  - `frontend/src/pages/Settings/actionCatalog/actionCatalogValidation.ts` и `frontend/src/pages/Settings/ActionCatalogPage.tsx` (валидация/UX),
  - `frontend/src/pages/Extensions/Extensions.tsx` (выбор и запуск set_flags по `action_id` / presets),
  - возможно вынос общего `ActionRunner`/hooks для reuse.

## Non-goals (MVP)
- Полный отказ от `capability` в data model.
- Переезд на “driver schema → operations UI” без action catalog (можно как дальнейшее развитие в отдельном change).

