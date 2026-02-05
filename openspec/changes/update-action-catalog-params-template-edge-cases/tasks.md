## 1. Spec
- [ ] 1.1 Добавить spec delta для `ui-action-catalog-editor`: collapsible schema panel + строгие правила pristine/touched для auto-fill.

## 2. Frontend
- [ ] 2.1 Уточнить модель “pristine/touched” для `executor.params_json`: исключить сброс user-edited состояния при смене `command_id`.
- [ ] 2.2 Auto-fill: только когда поле пустое/`{}` и pristine; один раз на `command_id` в рамках сессии модалки (fail-safe).
- [ ] 2.3 Schema panel: сделать collapsible + показывать счётчик параметров; не ломать текущие data-testid.
- [ ] 2.4 Confirm overwrite: убедиться, что overwrite всегда только через явное действие пользователя.
- [ ] 2.5 (Опционально) Вынести генерацию template/фильтрацию в нейтральный модуль, если связность с builder-utils начнёт мешать.

## 3. Tests
- [ ] 3.1 Playwright: “после ручного ввода и смены command_id авто-вставка не происходит”.
- [ ] 3.2 Playwright: “schema panel collapsible по умолчанию свернут” (если фиксируем это как требование).

## 4. Validation
- [ ] 4.1 `./scripts/dev/lint.sh --ts`
- [ ] 4.2 `frontend: npm run test:browser:action-catalog`
- [ ] 4.3 `openspec validate update-action-catalog-params-template-edge-cases --strict --no-interactive`

