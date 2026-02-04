## 1. Spec & Contracts
- [x] 1.1 Обновить spec deltas: `extensions-overview`, `extensions-plan-apply`, `extensions-action-catalog`.
- [x] 1.2 Обновить OpenAPI контракты: `ExtensionsPlanRequest.apply_mask` + regen клиентов (TS/Go).

## 2. Backend (Orchestrator)
- [x] 2.1 Расширить `POST /api/v2/extensions/plan/` для `extensions.set_flags`: принять `apply_mask` и fail-closed валидацию (минимум: хотя бы один флаг выбран).
- [x] 2.2 Plan: selective apply — удалить невыбранные флаги из `executor.params` и fail-closed, если executor не поддерживает params-based режим.
- [x] 2.3 Apply: использовать сохранённый `apply_mask` из plan и гарантировать, что невыбранные флаги не попадают в executor params.
- [x] 2.4 Update-time validation `ui.action_catalog` не добавляли: fail-closed реализован на plan/apply для selective apply.

## 3. Frontend
- [x] 3.1 Drawer `/extensions`: добавить форму apply (checkbox + switch для 3 флагов), disable switch при unchecked.
- [x] 3.2 Apply flow: upsert policy выбранных флагов, затем plan/apply с `apply_mask`.
- [x] 3.3 Тесты (Playwright/Vitest): selective apply (например, применяем только `active`, остальные не отправляем/не затрагиваем).

## 4. Validation
- [x] 4.1 `./scripts/dev/lint.sh --python` + `./scripts/dev/lint.sh --ts`
- [x] 4.2 Backend pytest (релевантные тесты)
- [x] 4.3 Frontend Playwright: `frontend: npm run test:browser:extensions`
