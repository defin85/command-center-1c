## 1. Spec
- [ ] 1.1 Delta spec для `ui-action-catalog-editor`: Guided/Raw JSON params editor + сохранение кастомных ключей + ширина Select.

## 2. Frontend
- [ ] 2.1 Исправить layout `driver` / `command_id`: стабильные пропорции и `width: 100%` (без схлопывания).
- [ ] 2.2 Добавить переключатель `Guided / Raw JSON` для `executor.params` (default Guided).
- [ ] 2.3 Реализовать Guided‑редактор: поля по `params_by_name` (с фильтрацией disabled + ibcmd connection params), ввод значений.
- [ ] 2.4 Двунаправленная синхронизация:
  - Guided → обновляет `params_json` (pretty JSON);
  - Raw JSON → влияет на Guided (парсинг) или показывает ошибку, если JSON невалиден.
- [ ] 2.5 Preserve unknown keys: Guided‑изменения не удаляют ключи вне schema (merge поверх текущего объекта).

## 3. Tests
- [ ] 3.1 Playwright: Guided по умолчанию; ввод значения поля из schema → оно попадает в JSON.
- [ ] 3.2 Playwright: Raw JSON добавляет кастомный ключ → после возврата в Guided ключ не теряется при редактировании schema‑поля.
- [ ] 3.3 (Опционально) Unit-тест merge‑логики (preserve unknown keys).

## 4. Validation
- [ ] 4.1 `./scripts/dev/lint.sh --ts`
- [ ] 4.2 `frontend: npm run test:browser:action-catalog`
- [ ] 4.3 `openspec validate add-action-catalog-guided-params-editor --strict --no-interactive`

