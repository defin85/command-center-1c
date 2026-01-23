## 1. Implementation
- [ ] Обновить/добавить OpenSpec requirements для унификации UI `DriverCommandBuilder` (операции + templates).
- [ ] Расширить контракт `driver_schema` для драйверов `ibcmd` и `cli` (driver-level options, groups/sections, типы полей).
- [ ] Уточнить контракт `auth_database_id` как auth context (RBAC + маппинг пользователя CC ↔ infobase user), включая server-side validation.
- [ ] Обновить frontend `DriverCommandBuilder` так, чтобы:
  - [ ] рендерить driver options из `driver_schema` (включая `ibcmd` connection/offline/timeout/stdin/auth context),
  - [ ] иметь единый layout и порядок секций для `cli` и `ibcmd`,
  - [ ] использовать единый dangerous confirm‑модал по общим правилам.
- [ ] Обновить места использования `DriverCommandBuilder` (например `/operations`, `/templates`) так, чтобы они передавали нужный контекст (список доступных DB IDs/labels) одинаково.
- [ ] Обновить Review‑экран(ы) так, чтобы summary для `designer_cli` и `ibcmd_cli` был унифицирован (названия полей, порядок, risk/confirm).

## 2. Validation
- [ ] Добавить/обновить unit tests (vitest) на `DriverCommandBuilder`:
  - [ ] `cli` driver: layout, preview, cli options, отсутствие ibcmd‑секций.
  - [ ] `ibcmd` driver: execution context из схемы, auth context requirement для global scope, dangerous flow.
- [ ] Прогнать `scripts/dev/lint.sh`.
- [ ] Прогнать `frontend` тесты (`vitest`) для затронутых компонентов.

