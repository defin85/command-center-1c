# Design: Tenancy + snapshots + plan/apply (MVP: extensions)

## Определения
- **Tenant**: организация/контур; пользователь выбирает активный tenant в UI.
- **Snapshot**: зафиксированный результат выполнения команды (raw + normalized + hashes), используемый для детерминированных планов и UI.
- **Plan**: объект, описывающий что будет выполнено, и содержащий preconditions (drift check).

## Tenant context
### Выбор tenant
- UI хранит `active_tenant_id` (localStorage) и отправляет его в `X-CC1C-Tenant-ID` во все API вызовы.
- Backend проверяет membership (`TenantMember`) и выставляет tenant context на время запроса.

### Fallback для совместимости
- Если заголовок отсутствует: использовать `user.default_tenant_id` (после миграции в `default` tenant).
- Любые операции, создающие/меняющие данные, ДОЛЖНЫ быть tenant-scoped.

## Global settings + per-tenant overrides
- `RuntimeSetting` остаётся глобальным source-of-truth.
- Добавляется `TenantRuntimeSettingOverride(tenant_id, key, value, status)` с возможностью draft/published.
- Effective value: tenant published override → global value → default.

## Command result snapshots
### Зачем append-only
Latest-only (как `DatabaseExtensionsSnapshot`) хорошо для UI, но не достаточно для:
- plan/apply с drift check (нужно ссылаться на конкретный snapshot),
- аудита и воспроизводимости (что именно было применено).

### Модель snapshot (концептуально)
- `tenant_id`
- `operation_id` (source)
- `driver`, `command_id`
- `target_scope` и `target_ref` (например database_id)
- `captured_at`, `raw_payload`, `normalized_payload`
- `normalized_hash` (canonical hash для drift)
- `schema_version/catalog_version`

## Tenant-scoped mapping
### Зачем mapping если уже есть normalize
В проекте уже есть нормализация extensions из raw worker результата. Но per-tenant mapping нужен для:
- вариативности формата/полей (разные окружения/версии),
- управления каноникой без деплоя кода.

### MVP компромисс
MVP допускает двухшаговую схему:
1) “base normalize” (из raw в структурированный normalized),
2) “tenant mapping” (из normalized в canonical extensions_inventory).

Дальше (опционально): перенос парсинга в driver/worker, чтобы raw→JSON был стабильным, и mapping стал полностью JSON→JSON.

## Extensions plan/apply + drift check
### Plan
Plan строится на основе:
- текущего extensions snapshot (или выбранного snapshot_id),
- effective tenant mapping,
- выбранного apply action (MVP: `extensions.sync` из `ui.action_catalog`),
и фиксирует:
- `base_snapshot_hash` (по DB) + `base_snapshot_at`,
- preview `argv_masked[]`/bindings (если применимо),
- список targets.

### Apply
Apply:
1) выполняет drift check,
2) запускает `extensions.sync` для targets,
3) после completion записывает новые snapshot’ы.

### Drift check (default strict)
- **strict**: перед apply выполнить preflight `extensions.list` и сравнить hash с plan base.
- Ошибка: вернуть 409 (conflict) с описанием “state changed; re-plan required”.

