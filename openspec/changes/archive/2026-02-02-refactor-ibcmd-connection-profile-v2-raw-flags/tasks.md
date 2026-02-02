## 1. Проектирование и контракты
- [x] 1.1 Обновить OpenAPI `contracts/orchestrator/openapi.yaml`: заменить профиль на v2 raw flags (`remote`, `pid`, `offline`), удалить `mode` и `remote_url` (**BREAKING**).
- [x] 1.2 Обновить generated clients/types (frontend + другие потребители), зафиксировать breaking изменения и места компиляции.

## 2. Orchestrator
- [x] 2.1 Обновить serializers/валидаторы `update-ibcmd-connection-profile` под v2:
  - `remote` строго `ssh://...` (400 `VALIDATION_ERROR`),
  - `pid` integer,
  - `offline` как dict с произвольными ключами, но запрещены секреты (`db_user`, `db_pwd`, `db_password`, и эквиваленты).
- [x] 2.2 Реализовать/обновить миграцию существующих `Database.metadata.ibcmd_connection` v1 → v2 (one-time migration или on-read normalize + write-back, решение в design).
- [x] 2.3 Обновить derived validation в `execute-ibcmd-cli`:
  - критерий “профиль пустой/отсутствует” для v2,
  - поведение fail-closed сохранить: 400 `IBCMD_CONNECTION_PROFILE_INVALID` с `details.missing[]`.
- [x] 2.3a Убрать использование DBMS metadata (`Database.dbms/db_server/db_name`) как fallback для `ibcmd` v2 (включая preflight/preview/provenance, если затрагивается).
- [x] 2.4 Обновить staff preview provenance (если зависит от полей профиля) так, чтобы отражать v2 источники (`remote`, `offline.*`) без `mode/remote_url`.

## 3. Worker
- [x] 3.1 Обновить сборку argv/resolution per target под v2 профиль (использовать `remote`/`pid`/`offline.*` как есть).

## 4. Frontend
- [x] 4.1 `/databases`: обновить модалку IBCMD profile под v2 (remote ssh url, pid, offline key/value).
- [x] 4.2 Operations/DriverCommandBuilder: обновить derived summary+diff и тексты под v2 (без `mode/remote_url`), в т.ч. отображение `remote` как SSH URL.
- [x] 4.3 Обновить UI error handling, если backend ошибки/детали поменяются из-за v2.

## 5. Тесты и quality gates
- [x] 5.1 Django tests: обновить/добавить тесты `update-ibcmd-connection-profile` для v2 (ssh validation, pid, offline arbitrary keys, секреты запрещены, reset).
- [x] 5.2 Django tests: обновить derived-mode тесты `execute-ibcmd-cli` (пустой профиль → `IBCMD_CONNECTION_PROFILE_INVALID`).
- [x] 5.3 Frontend tests: обновить тесты модалки `/databases` и derived summary+diff под v2.
- [x] 5.4 Quality gates: `./scripts/dev/lint.sh`, `cd orchestrator && ./../scripts/dev/pytest.sh -q`, `cd frontend && npm run test:run`.

## 6. Ручная проверка (минимум)
- [ ] 6.1 `/databases`: задать профили для пары баз (remote ssh url, pid, offline.*) и убедиться, что payload сохраняется и отображается корректно.
- [ ] 6.2 Operations: derived запуск `ibcmd_cli`:
  - при пустом профиле у части баз → fail-closed 400 с деталями,
  - при валидном профиле → enqueue работает.
