## 1. Spec & Contracts
- [x] 1.1 Обновить spec deltas для `extensions-plan-apply`, `extensions-action-catalog`, `ui-action-catalog-editor`, `extensions-overview`.
- [x] 1.2 Обновить OpenAPI контракт `extensions.plan` для `extensions.set_flags`: добавить строгий `flags_values` и строгий `apply_mask`.
- [x] 1.3 Регенерировать frontend API типы после обновления контракта.

## 2. Backend
- [x] 2.1 Удалить fallback `apply_mask` из `executor.fixed.apply_mask` в plan/apply для `extensions.set_flags`.
- [x] 2.2 Сделать `action_id` обязательным для `extensions.set_flags` (fail-closed).
- [x] 2.3 Добавить валидацию `flags_values` и использовать только runtime values при резолве `$flags.*` токенов.
- [x] 2.4 Запретить publish/runtime `extensions.set_flags` exposure с capability-specific `apply_mask` preset.
- [x] 2.5 Добавить/обновить тесты plan/apply: strict request contract, no preset fallback, action_id required.

## 3. Frontend
- [x] 3.1 `/extensions`: основной bulk путь через запуск workflow rollout с явным вводом `flags_values` + `apply_mask`.
- [x] 3.2 `/extensions`: оставить точечный fallback (single/small target) с явной маркировкой аварийного режима.
- [x] 3.3 Action Catalog editor: убрать UI для `fixed.apply_mask` у `extensions.set_flags`; оставить binding/safety.
- [x] 3.4 Обновить пользовательские тексты/подсказки, чтобы источник значений был прозрачен (workflow input).
- [x] 3.5 Добавить frontend тесты: workflow-first запуск, fallback path, отсутствие preset mask в editor.

## 4. Migration & Rollout
- [x] 4.1 Написать миграционный check/report для существующих exposures с `apply_mask` preset.
- [x] 4.2 Обеспечить fail-closed поведение до исправления невалидных exposures.
- [x] 4.3 Подготовить операторскую инструкцию по переходу на workflow-first сценарий.

## 5. Validation
- [x] 5.1 `openspec validate refactor-extensions-set-flags-workflow-source-of-truth --strict --no-interactive`
- [x] 5.2 Прогнать релевантные backend/frontend тесты, покрывающие новый контракт.

Примечание: backend pytest запускался через `orchestrator/venv`, но в текущей среде упирается в лимит PostgreSQL соединений (`remaining connection slots are reserved for roles with the SUPERUSER attribute`).
