## 1. Реализация (Implementation)
- [ ] 1.1 Frontend Operations: добавить derived summary + diff для `ibcmd` `scope=per_database` при `override=false`.
- [ ] 1.2 Frontend Operations: UX деградация для больших выборок (лимит детализации, “+N more”, быстрый рендер).
- [ ] 1.3 Orchestrator UI preview: улучшить provenance bindings для fallback DBMS metadata (`dbms/db_server/db_name`) в derived-mode.

## 2. Тесты и quality gates
- [ ] 2.1 Tests (Django): `update-ibcmd-connection-profile` (RBAC, tenant scope, set/reset, запрет секретов, валидации).
- [ ] 2.2 Tests (Django): `execute-ibcmd-cli` derived-mode (missing profile -> `IBCMD_CONNECTION_PROFILE_INVALID`, mixed mode).
- [ ] 2.3 Tests (Frontend): модалка `/databases` для `IBCMD connection profile` (валидация, payload).
- [ ] 2.4 Tests (Frontend): Operations derived summary+diff (unit), базовые сценарии mixed mode.
- [ ] 2.5 Quality gates: `./scripts/dev/lint.sh`, `cd orchestrator && pytest -q`, `cd frontend && npm test`.

## 3. Ручная проверка (Manual)
- [ ] 3.1 Operations: выбрать базы с разными профилями (remote/offline) и убедиться, что сводка+diff соответствует ожиданиям.
- [ ] 3.2 Extensions/Action Catalog preview (staff): открыть preview и убедиться, что provenance отражает fallback источники DBMS metadata.

