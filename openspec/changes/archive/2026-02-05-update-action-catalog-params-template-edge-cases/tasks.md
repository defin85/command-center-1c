## 1. Spec
- [x] 1.1 Обновить spec delta для `ui-action-catalog-editor`: Guided/Raw JSON, preserve unknown keys, fix layout, collapsible schema panel и строгие правила pristine/touched для auto-fill.

## 2. Frontend
- [x] 2.1 Fix layout: `driver`/`command_id` Select не схлопываются; задать понятные пропорции (напр. 1/3 + 2/3) и `width: 100%`.
- [x] 2.2 Добавить переключатель `params` режима **Guided / Raw JSON** (default Guided).
- [x] 2.3 Guided: отрисовать schema‑параметры по `params_by_name` (disabled + connection params filtered), переиспользуя существующие контролы (например `ParamField`).
- [x] 2.4 Guided: при изменениях обновлять канонический `paramsObject` через merge и пересчитывать `paramsJson` (строка).
- [x] 2.5 Preserve unknown keys: Guided меняет только schema‑ключи и не удаляет прочие ключи в `params`.
- [x] 2.6 Raw JSON: при валидном JSON‑object синхронизировать `paramsObject`; при ошибке — показать состояние ошибки и блокировать переход в Guided до исправления.
- [x] 2.7 Уточнить модель “pristine/touched” для auto-fill schema template: исключить сброс user-edited состояния при смене `command_id`.
- [x] 2.8 Auto-fill: только когда поле пустое/`{}` и pristine; один раз на `command_id` в рамках сессии модалки (fail-safe).
- [x] 2.9 Schema panel: сделать collapsible + показывать счётчик параметров; не ломать текущие data-testid.
- [x] 2.10 Confirm overwrite: overwrite только через явное действие пользователя.
- [ ] 2.11 (Опционально) Вынести генерацию template/фильтрацию в нейтральный модуль, если связность с builder-utils начнёт мешать.

## 3. Tests
- [x] 3.1 Playwright: `params` по умолчанию в Guided режиме.
- [x] 3.2 Playwright: неизвестные ключи в `params` сохраняются после Guided‑редактирования schema‑поля и сохранения action.
- [x] 3.3 Playwright: при невалидном Raw JSON переход в Guided блокируется (и данные не теряются).
- [x] 3.4 Playwright: “после ручного ввода и смены command_id авто-вставка не происходит”.
- [x] 3.5 Playwright: “schema panel collapsible по умолчанию свернут”.
- [ ] 3.6 (Опционально) Проверка ширины Select `command_id` (boundingClientRect) не ниже минимального порога.

## 4. Validation
- [x] 4.1 `./scripts/dev/lint.sh --ts`
- [x] 4.2 `frontend: npm run test:browser:action-catalog`
- [x] 4.3 `openspec validate update-action-catalog-params-template-edge-cases --strict --no-interactive`
