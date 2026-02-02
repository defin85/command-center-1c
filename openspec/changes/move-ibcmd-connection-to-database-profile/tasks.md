## 1. Реализация (Implementation)
- [ ] 1.1 Contracts/OpenAPI: описать профиль подключения `ibcmd` на уровне базы и endpoint управления им (set/reset, RBAC, tenant scope).
- [ ] 1.2 Orchestrator: реализовать endpoint управления профилем подключения базы (хранение в `Database.metadata`, аудит, валидация “без секретов”).
- [ ] 1.3 Orchestrator: обновить `execute-ibcmd-cli` (и preview) так, чтобы для `scope=per_database` connection мог резолвиться per target из профилей баз; поддержать mixed mode.
- [ ] 1.4 Orchestrator: fail-closed ошибки для “нет/неполный профиль подключения” с машиночитаемым `error.code` и `details.missing[]` (без секретов).
- [ ] 1.5 Worker: расширить сборку argv так, чтобы driver-level connection флаги могли резолвиться per target из профиля базы (включая `--remote=<url>` и offline пути).
- [ ] 1.6 Frontend `/databases`: добавить UI для редактирования `ibcmd` connection profile (mode, remote_url, offline paths + DBMS metadata, reset) с RBAC.
- [ ] 1.7 Frontend Operations: по умолчанию показывать derived connection из профилей выбранных баз + поддержать per-run override; отобразить mixed mode.
- [ ] 1.8 Frontend Extensions actions: убрать использование `executor.connection` и всегда резолвить connection из профилей баз (или per-run override, если применимо).
- [ ] 1.9 Frontend Action Catalog editor: удалить `executor.connection` из guided UI/валидации/round-trip; обновить preview так, чтобы для `ibcmd_cli` требовались таргеты (или база-пример).

## 2. Тесты и quality gates
- [ ] 2.1 Tests (Django): управление профилем подключения (RBAC, tenant scope, set/reset, валидация).
- [ ] 2.2 Tests (Django): `execute-ibcmd-cli` mixed mode (часть таргетов remote, часть offline) и ошибки при отсутствии профиля у части баз.
- [ ] 2.3 Tests (Go worker): резолв per-target connection флагов из профиля базы при формировании argv.
- [ ] 2.4 Tests (Frontend): `/databases` редактирование профиля (unit), Operations derived/override (unit), удаление `executor.connection` из Action Catalog (unit).
- [ ] 2.5 Quality gates: `./scripts/dev/lint.sh`, `cd orchestrator && pytest -q`, `cd frontend && npm test` (минимум затронутые тесты).

## 3. Ручная проверка (Manual)
- [ ] 3.1 `/databases`: для одной базы задать `mode=remote` + `remote_url`; для другой — `mode=offline` + offline paths + DBMS metadata.
- [ ] 3.2 Operations: выбрать обе базы и запустить `ibcmd_cli` bulk — убедиться, что effective connection берётся per target и операция стартует.
- [ ] 3.3 Extensions: запустить действие расширений для набора баз с разными профилями — убедиться, что connection берётся из базы и ошибки actionable.
- [ ] 3.4 Action Catalog editor: создать/сохранить action `ibcmd_cli` без `executor.connection`; preview требует выбрать базы и корректно показывает plan/provenance.

