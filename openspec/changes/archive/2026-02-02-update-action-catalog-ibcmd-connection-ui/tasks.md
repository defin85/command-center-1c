## 1. Реализация (Implementation)
- [x] 1.1 UI Action Catalog: расширить `ActionFormValues`/derive/build, чтобы поддерживать `executor.connection` (round-trip без потерь).
- [x] 1.2 UI Action Catalog: обновить локальную валидацию `validateActionCatalogDraft` — разрешить ключ `extensions.actions[i].executor.connection` (объект).
- [x] 1.3 UI Action Catalog: в guided editor modal добавить UI для настройки `executor.connection` для `executor.kind=ibcmd_cli` (remote/pid/offline.*) и запретить ввод DBMS секретов.
- [x] 1.4 UI Action Catalog Preview: перед `POST /api/v2/ui/execution-plan/preview/` применять единое правило defaulting для `ibcmd_cli` (`connection.offline = {}` когда нужно) и показывать ошибки `ibcmd_cli` в user-friendly виде (как в Operations).
- [x] 1.5 UI Extensions Run Action (`/databases`): при `error.code=OFFLINE_DB_METADATA_NOT_CONFIGURED` показывать ту же actionable подсказку, что в `NewOperationWizard` (включая указание `/databases` и `connection.offline.*`).
- [x] 1.6 Refactor: вынести общий обработчик ошибок `ibcmd_cli` (preflight/enqueue) в переиспользуемый helper/hook, чтобы исключить дублирование между Operations и Extensions/Action Catalog.

## 2. Тесты и quality gates
- [x] 2.1 Frontend tests: покрыть round-trip `executor.connection` (form↔JSON) и локальную валидацию (ключ не помечается как unknown).
- [x] 2.2 Frontend tests: покрыть показ user-friendly модалки/сообщения для `OFFLINE_DB_METADATA_NOT_CONFIGURED` в месте запуска действий расширений.
- [x] 2.3 Quality gates: `./scripts/dev/lint.sh` и минимальные тесты frontend (`cd frontend && npm test` или эквивалент в репо).

## 3. Ручная проверка (Manual)
- [ ] 3.1 `/settings/action-catalog`: открыть `ListExtension` → Edit → задать `connection.remote` или `connection.pid` → Save → убедиться, что draft валиден и сохраняется.
- [ ] 3.2 `/databases`: запустить действие расширений с `connection.offline` для базы без DBMS metadata → убедиться, что ошибка до enqueue и содержит понятные инструкции (как в Operations).
