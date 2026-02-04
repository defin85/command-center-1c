## 1. Spec & Contracts
- [ ] 1.1 Добавить spec deltas: `kb1ci-doc-ingestion`, `driver-catalog-kb1ci-import`, `cluster-platform-versioning`.
- [ ] 1.2 Обновить OpenAPI контракты: KB endpoints (tree/sync/docsets/parse), platform-version endpoints, driver catalog activate/resolve.
- [ ] 1.3 Регенерация клиентов/типов (Go/Python/TS) по обновлённым контрактам.

## 2. Backend (Orchestrator)
- [ ] 2.1 Модели: `Kb1ciSnapshot`, `Kb1ciPage` (и/или версии), `Kb1ciDocSet`, `Kb1ciParseRun`.
- [ ] 2.2 Sync job: загрузка дерева KB через REST (`Accept: application/json`), инкрементальные обновления, rate limiting, ошибки в отчёте.
- [ ] 2.3 API: tree listing (lazy/full), CRUD DocSets, запуск parse-run (dry-run по умолчанию).
- [ ] 2.4 Парсер: `kb1ci` → промежуточная модель → base catalog v2 для `cli` и `ibcmd`.
- [ ] 2.5 Строгая schema-валидация результата (запрет неожиданных полей/типов), fail-closed publish.
- [ ] 2.6 Driver catalogs: хранение/листинг base catalogs по `platform_version`, активация “active base” per (driver, platform_version).
- [ ] 2.7 Cluster platform versioner: хранение effective версии, `ok|unknown|mixed`, manual override API.
- [ ] 2.8 Resolve: API для “какой каталог применяется к кластеру” (debug/UX), интеграция выбора active catalog по версии.
- [ ] 2.9 Тесты: sync tree, DocSets, parse-run (happy/error), strict validation, activation/resolve, RBAC + tenant-context guards.

## 3. Frontend
- [ ] 3.1 UI KB1CI: дерево разделов (полный список), создание DocSet (выбор корней/поддеревьев), запуск parse-run и просмотр отчёта.
- [ ] 3.2 UI Driver Catalogs: переключатель active base catalog по версиям платформы (8.3.23/8.3.24/…).
- [ ] 3.3 UI Clusters: отображение effective platform version + статус (`unknown/mixed`) и ручной override (staff/admin).
- [ ] 3.4 UX для staff cross-tenant: mutating операции требуют выбранный tenant (явный tenant context).
- [ ] 3.5 Тесты (Vitest/Playwright): дерево/DocSets/parse-report, activate catalog, override версии кластера.

## 4. Validation
- [ ] 4.1 `./scripts/dev/pytest.sh` (релевантные тесты)
- [ ] 4.2 `./scripts/dev/lint.sh --python` + `./scripts/dev/lint.sh --ts`
- [ ] 4.3 OpenAPI checks + codegen hooks (если включены)

