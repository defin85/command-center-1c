## 1. Spec & Contracts
- [ ] 1.1 Обновить spec deltas: `extensions-overview`, `extensions-action-catalog`, `extensions-plan-apply`, добавить `extensions-flags-policy`.
- [ ] 1.2 Обновить OpenAPI контракты (новые поля overview + policy endpoints + action apply endpoints) и regen клиентов.

## 2. Backend (Orchestrator)
- [ ] 2.1 Добавить tenant-scoped storage для ExtensionFlagsPolicy (name -> 3 флага + audit fields).
- [ ] 2.2 Реализовать `GET/PUT/PATCH` API для policy с fail-closed guard: staff mutating требует `X-CC1C-Tenant-ID`.
- [ ] 2.3 Расширить `/api/v2/extensions/overview/`: возвращать унифицированные агрегаты флагов (policy + observed + drift).
- [ ] 2.4 Расширить drill-down `/api/v2/extensions/overview/databases/`: возвращать observed значения флагов per database (best-effort).
- [ ] 2.5 Добавить plan/apply для capability `extensions.set_flags` (bulk), с drift check и per-db tasks.
- [ ] 2.6 Snapshot update после apply: использовать marker snapshot-producing и гарантировать refresh/обновление snapshots.
- [ ] 2.7 Тесты: агрегация флагов (включая mixed/unknown), tenant/staff guard для mutating, план/apply happy-path и partial failures.

## 3. Frontend
- [ ] 3.1 Обновить `/extensions` UI: policy-колонки, индикаторы mixed/unknown/drift.
- [ ] 3.2 Добавить запуск actions для “Apply flags policy” и “Adopt from database” (preview + confirmation + запуск).
- [ ] 3.3 UX для staff cross-tenant: без выбранного tenant disable mutating actions + понятная подсказка.
- [ ] 3.4 Тесты (Playwright/Vitest): отображение policy, корректная передача tenant header при mutating, запуск apply action.

## 4. Validation
- [ ] 4.1 `./scripts/dev/pytest.sh` (релевантные тесты)
- [ ] 4.2 `./scripts/dev/lint.sh --python` + `./scripts/dev/lint.sh --ts`
- [ ] 4.3 Frontend Playwright: `frontend: npm run test:browser:extensions`

