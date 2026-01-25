## 1. Implementation
- [x] Обновить/добавить OpenSpec requirements для унификации UI `DriverCommandBuilder` (операции + templates).
- [x] Расширить контракт `driver_schema` для драйверов `ibcmd` и `cli` (driver-level options, groups/sections, типы полей).
- [x] Уточнить контракт `auth_database_id` как auth context (RBAC + маппинг пользователя CC ↔ infobase user), включая server-side validation.
- [x] Обновить frontend `DriverCommandBuilder` так, чтобы:
  - [x] рендерить driver options из `driver_schema` (включая `ibcmd` connection/offline/timeout/stdin/auth context),
  - [x] иметь единый layout и порядок секций для `cli` и `ibcmd`,
  - [x] использовать единый dangerous confirm‑модал по общим правилам.
- [x] Обновить места использования `DriverCommandBuilder` (например `/operations`, `/templates`) так, чтобы они передавали нужный контекст (список доступных DB IDs/labels) одинаково.
- [x] Обновить Review‑экран(ы) так, чтобы summary для `designer_cli` и `ibcmd_cli` был унифицирован (названия полей, порядок, risk/confirm).

## 2. Validation
- [x] Добавить/обновить unit tests (vitest) на `DriverCommandBuilder`:
  - [x] `cli` driver: layout, preview, cli options, отсутствие ibcmd‑секций.
  - [x] `ibcmd` driver: execution context из схемы, auth context requirement для global scope, dangerous flow.
- [x] Прогнать `scripts/dev/lint.sh`.
- [x] Прогнать `frontend` тесты (`vitest`) для затронутых компонентов.
