## 1. Spec & Contracts
- [ ] 1.1 Добавить/обновить spec deltas: `operation-templates`, `extensions-plan-apply`, `extensions-overview`, `extensions-action-catalog`, `ui-action-catalog-editor`.
- [ ] 1.2 Добавить новый capability spec: `operations-manual-contracts`.
- [ ] 1.3 Обновить OpenAPI контракт `extensions.plan/apply` под template-based manual contract (`template_id`, `bindings`, runtime input).
- [ ] 1.4 Регенерировать frontend API типы после обновления контракта.

## 2. Backend
- [ ] 2.1 Перевести runtime-resolve `extensions.set_flags` в `extensions.plan/apply` на template-first модель (без зависимости от action catalog).
- [ ] 2.2 Добавить fail-closed валидацию `template_id` и `bindings` для manual contract запуска.
- [ ] 2.3 Обеспечить deterministic mapping runtime input -> template params через user-provided binding slots.
- [ ] 2.4 Для `/extensions` и `/databases` исключить execution path через `extensions.*` из `ui/action-catalog`.
- [ ] 2.5 Добавить миграционный report для действующих `action_catalog` exposure с `capability` префикса `extensions.`.

## 3. Frontend
- [ ] 3.1 `/extensions`: оставить workflow-first bulk запуск и удалить ручной targeted atomic apply UX.
- [ ] 3.2 `/operations`: добавить hardcoded manual contracts registry для extensions manual операций.
- [ ] 3.3 `/operations`: реализовать форму выбора `template`, ввода runtime input и user-defined bindings по выбранному contract.
- [ ] 3.4 `/operations`: сохранить preview + подтверждение + запуск через единый `extensions plan/apply` pipeline.
- [ ] 3.5 `/databases`: убрать запуск `extensions.*` через `ui/action-catalog` меню и направлять в contract-driven flow.
- [ ] 3.6 `/templates` и editor UX: явно маркировать депрекацию `extensions.*` action-catalog сценария.

## 4. Migration & Rollout
- [ ] 4.1 Выполнить read-only диагностику существующих `extensions.*` action exposures и зафиксировать список для cleanup.
- [ ] 4.2 Включить этапный rollout: сначала dual-read warning, затем hard switch на templates-first runtime path.
- [ ] 4.3 Подготовить операторскую инструкцию: где workflow bulk, где manual fallback, как заполнять binding.

## 5. Validation
- [ ] 5.1 `openspec validate refactor-extensions-templates-first-manual-contracts --strict --no-interactive`
- [ ] 5.2 Прогнать релевантные backend тесты `extensions plan/apply` и template-binding validation.
- [ ] 5.3 Прогнать релевантные frontend тесты `/extensions`, `/operations`, `/databases` для нового contract-driven manual flow.
