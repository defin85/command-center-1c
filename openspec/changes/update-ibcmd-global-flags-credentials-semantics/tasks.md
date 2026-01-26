# Tasks: update-ibcmd-global-flags-credentials-semantics

## 1. Схема и каталог
- [x] 1.1. Расширить генерацию `ibcmd.driver_schema` из ITS так, чтобы включать все флаги из 4.10.2 (включая алиасы).
- [x] 1.2. Добавить семантику credential-флагов (db_user/db_password/ib_user/ib_password) + `sensitive` в schema.
- [x] 1.3. Зафиксировать политику: `--request-db-pwd (-W)` не поддерживается в guided (валидация fail-closed).

## 2. API / сборка argv
- [x] 2.1. Обновить builder `execute-ibcmd-cli` так, чтобы умел собирать полный набор driver-level флагов из schema.
- [x] 2.2. Добавить поле запроса `ib_auth.strategy` (`actor|service|none`) и валидацию RBAC/allowlist.
- [x] 2.3. Обеспечить корректное `argv_masked` и `bindings[]` для всех credential-флагов.

## 3. Worker / инъекция creds
- [x] 3.1. Реализовать резолвинг IB creds по стратегии:
  - actor: per-user mapping по `created_by`
  - service: mapping `is_service=true` (user=NULL)
- [x] 3.2. Инжектить IB creds через `--user/--password` и DB creds через `--db-user/--db-pwd` (argv-only).
- [x] 3.3. Обеспечить fail-closed поведение: service запрещён вне allowlist/permission; secrets не попадают в result/logs.

## 4. UI
- [x] 4.1. Обновить `DriverCommandBuilder` для рендера полного набора driver options `ibcmd` (группировка/поиск).
- [x] 4.2. Добавить UI-контрол `ib_auth.strategy`, доступный только при allowlist/permission и только для safe команд.

## 5. Тесты и документация
- [x] 5.1. Добавить/обновить unit tests: schema generation, argv builder, RBAC allowlist, worker injection.
- [x] 5.2. Обновить docs: описание новых driver options и стратегии `ib_auth` + ограничения.
