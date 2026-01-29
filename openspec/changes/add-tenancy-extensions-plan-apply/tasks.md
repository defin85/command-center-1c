## 1. Tenancy foundation
- [ ] Добавить модели `Tenant` и `TenantMember` (user membership + роль).
- [ ] Добавить `tenant_id` (FK) в `Cluster` и `Database` и обеспечить, что база/кластер принадлежат ровно одному tenant.
- [ ] Миграция: создать `default` tenant и привязать к нему существующие данные + пользователей (по правилам, согласованным в design).
- [ ] API: `GET /api/v2/tenants/list-my-tenants/`, `POST /api/v2/tenants/set-active/` (или эквивалент).
- [ ] Frontend: UI-переключатель tenant + прокидывание `X-CC1C-Tenant-ID` во все запросы.
- [ ] Middleware/guard: backend валидирует membership и tenant context (403 если нет доступа).

## 2. Global settings + per-tenant overrides
- [ ] Добавить хранение override для runtime settings per-tenant.
- [ ] Ввести “effective resolution”: `tenant override` → `global value` → default.
- [ ] Расширить staff-only редакторы (как минимум `ui.action_catalog`) на выбор tenant + preview effective.

## 3. Command result snapshots (platform)
- [ ] Добавить append-only хранилище `CommandResultSnapshot` (raw + normalized + hashes + references).
- [ ] Добавить API для preview и выборки snapshot’ов (RBAC+tenant scoped).
- [ ] Интеграция с event-subscriber: сохранять snapshot’ы для команд, помеченных как snapshot-producing (MVP: extensions.list/sync через action catalog).

## 4. Tenant-scoped mapping (MVP: extensions)
- [ ] Добавить `MappingSpec` per-tenant для `entity_kind=extensions_inventory` (draft/published).
- [ ] Реализовать Preview: применить mapping к сохранённому snapshot и валидировать по canonical schema.
- [ ] Включить mapping в pipeline сохранения/выдачи extensions snapshot (по согласованным правилам).

## 5. Extensions plan/apply + drift check
- [ ] API: `POST /api/v2/extensions/plan/` (строит plan, фиксирует preconditions: hash/at, returns plan_id + preview).
- [ ] API: `POST /api/v2/extensions/apply/` (проверяет drift, исполняет `extensions.sync`, обновляет snapshots).
- [ ] Реализовать drift check (default strict, параметризуемо).

## 6. Tests & validation
- [ ] Django tests: tenancy scoping, membership checks, override resolution.
- [ ] Django tests: snapshot ingestion + mapping preview validation.
- [ ] Django tests: plan/apply drift conflict (409/validation error) и success path.
- [ ] `./scripts/dev/lint.sh`
- [ ] `cd orchestrator && pytest -q` (минимум затронутые apps).

