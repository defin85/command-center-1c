## 1. Spec & Contracts
- [ ] 1.1 Добавить/обновить spec deltas: `operation-templates`, `extensions-plan-apply`, `extensions-overview`, `extensions-action-catalog`, `ui-action-catalog-editor`.
- [ ] 1.2 Не вводить новый capability spec для manual contracts в рамках этого change.
- [ ] 1.3 Обновить OpenAPI контракт `extensions.plan/apply` под template-based контракт (`template_id`, runtime input).
- [ ] 1.4 Регенерировать frontend API типы после обновления контракта.

## 2. Backend
- [ ] 2.1 Перевести runtime-resolve `extensions.set_flags` в `extensions.plan/apply` на template-first модель (без зависимости от action catalog).
- [ ] 2.2 Добавить fail-closed валидацию `template_id` и template/capability compatibility.
- [ ] 2.3 Обеспечить deterministic mapping runtime input -> template params без action-catalog слоя.
- [ ] 2.4 Для `/extensions` и `/databases` исключить execution path через `extensions.*` из `ui/action-catalog`.
- [ ] 2.5 Отклонять legacy `action_id`-запросы для `extensions.set_flags` без template-based полей.

## 3. Frontend
- [ ] 3.1 `/extensions`: запуск `extensions.*` строить только от templates (без runtime action-catalog).
- [ ] 3.2 `/extensions`: форма запуска использует template-based input и единый `extensions plan/apply` pipeline.
- [ ] 3.3 `/databases`: убрать запуск `extensions.*` через `ui/action-catalog` и использовать template-based path.
- [ ] 3.4 `/templates` и editor UX: блокировать runtime-сценарий `extensions.*` в action-catalog и указывать templates-first модель.

## 4. Cutover
- [ ] 4.1 Выполнить одномоментный cutover на templates-first runtime path для `extensions.*` без dual-path.
- [ ] 4.2 Обновить operator guidance: runtime для `extensions.*` работает только через templates.
- [ ] 4.3 Обновить UI тексты/подсказки, чтобы новая модель была единственной и явной.

## 5. Validation
- [ ] 5.1 `openspec validate refactor-extensions-templates-first-manual-contracts --strict --no-interactive`
- [ ] 5.2 Прогнать релевантные backend тесты `extensions plan/apply` и template/capability validation.
- [ ] 5.3 Прогнать релевантные frontend тесты `/extensions` и `/databases` для templates-first execution path.
