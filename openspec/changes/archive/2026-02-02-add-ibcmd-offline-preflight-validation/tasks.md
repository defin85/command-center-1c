## 1. Реализация (Implementation)
- [x] 1.1 Orchestrator: добавить preflight-валидацию offline DBMS metadata (`dbms/db_server/db_name`) для `execute_ibcmd_cli` (`scope=per_database`) до enqueue.
- [x] 1.2 Orchestrator: унифицировать error contract:
  - новые `error.code` (например `OFFLINE_DB_METADATA_NOT_CONFIGURED`) и `error.details` (список проблемных таргетов + missing keys),
  - без утечек секретов.
- [x] 1.3 Orchestrator API v2: добавить endpoint для управления DBMS metadata базы:
  - `POST /api/v2/databases/update-dbms-metadata/` (set/reset),
  - RBAC: `databases.manage_database`,
  - tenant scoped.
- [x] 1.4 Frontend: добавить UI-форму редактирования DBMS metadata для базы на `/databases` (например модалка из карточки базы) + mutation hook.
- [x] 1.5 Frontend: обработать новые `error.code` в UI запуска `ibcmd` (DriverCommandBuilder/Execute flow) и показать actionable подсказку (включая “где исправить”).
- [x] 1.6 Tests (Django): кейсы preflight
  - offline без `db_path`, без `remote/pid`, при пустых `Database.metadata.dbms/db_server/db_name` → 400 + детали,
  - offline при наличии request-level `connection.offline.dbms/db_server` и наличии per-target `db_name` → ok,
  - offline при request-level `connection.offline.db_name` (общий override) → ok.
- [x] 1.7 Tests (Django): endpoint update-dbms-metadata
  - без прав MANAGE → 403,
  - set/update → поля записаны в `Database.metadata`,
  - reset → поля очищены,
  - validation: запрет пустых значений при set (или корректно документированный reset).
- [x] 1.8 Contracts: обновить `contracts/orchestrator/openapi.yaml` (описать новые ошибки + новый endpoint) + регенерировать клиентов.
- [x] 1.9 Quality gates: `./scripts/dev/lint.sh`, `cd orchestrator && pytest -q` (минимум затронутые тесты), `cd frontend && npm test` (если есть изменения).

## 2. Валидация поведения (ручная)
- [ ] 2.1 В UI выбрать `connection.offline` для базы без DBMS metadata → убедиться, что ошибка приходит до enqueue и содержит понятные инструкции.
- [ ] 2.2 На `/databases` заполнить `dbms/db_server/db_name` через UI → повторить и убедиться, что операция уходит в очередь.
