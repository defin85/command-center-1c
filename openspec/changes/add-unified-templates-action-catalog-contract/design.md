## Context
В проекте есть два независимых persistent-контракта для схожих сущностей:
- `OperationTemplate` (`/templates`);
- RuntimeSetting `ui.action_catalog` (`/settings/action-catalog`).

Это создаёт архитектурный дрейф:
- дублируются executor-поля и валидации;
- разные точки ошибок (config-time vs runtime);
- сложно обеспечивать детерминизм для reserved capability (`extensions.set_flags`).

Дополнительно, change `add-set-flags-target-binding-contract` уже требует строгий target-binding контракт, который должен жить в единой модели, а не в “ветке” только одного экрана.

## Goals / Non-Goals
- Goals:
  - Единый source of truth для исполняемых определений templates/actions.
  - Явное разделение “что выполняем” и “как/где показываем”.
  - Fail-closed валидация и детерминизм для `extensions.set_flags`.
  - Прямой cutover без сохранения обратной совместимости старых payload/endpoint flow.
- Non-Goals:
  - Полный редизайн UX страниц `/templates` и `/settings/action-catalog`.
  - Унификация всех исторических operation types в один executor DSL за один релиз.

## Target Architecture
### 1) Persistent Domain Model
#### `operation_definition` (canonical execution contract)
- `id` (UUID)
- `tenant_scope` (`global` | `tenant:<id>`)
- `executor_kind` (`ibcmd_cli` | `designer_cli` | `workflow`)
- `executor_payload` (JSON)
- `contract_version` (int)
- `fingerprint` (sha256 canonical JSON)
- `status` (`active` | `archived`)
- timestamps/audit fields

#### `operation_exposure` (surface-specific projection)
- `id` (UUID)
- `definition_id` (FK)
- `surface` (`template` | `action_catalog`)
- `alias` (старый внешний идентификатор: `template_id` или `action.id`)
- `tenant_id` (nullable, для override/per-tenant)
- `label`, `description`, `is_active`
- `capability`, `contexts`, `display_order`
- `capability_config` (JSON, включая `target_binding`, `apply_mask` preset, и т.д.)
- `status` (`draft` | `published` | `invalid`)
- timestamps/audit fields

#### `operation_migration_issue`
- хранит проблемы backfill/validation с привязкой к исходному объекту и `operation_exposure`.

### 2) Service Layer
Единый backend service `operation_contract_service`:
- `resolve_definition(...)`
- `resolve_exposure(surface, alias, tenant)`
- `list_exposures(surface, filters...)`
- `validate_exposure(...)`

Все текущие endpoints (`templates`, `ui/action-catalog`, `extensions/plan|apply`) используют этот слой, а не прямой доступ к старым хранилищам.

### 2.1) Unified API Surface (explicit)
Новые endpoints (staff/admin), через которые frontend и внутренние инструменты работают с unified моделью напрямую:

- `GET /api/v2/operation-catalog/definitions/`
  - фильтры: `tenant_scope`, `executor_kind`, `status`, `q`, `limit`, `offset`.
- `GET /api/v2/operation-catalog/definitions/{definition_id}/`
  - возвращает canonical execution payload + usage references.
- `GET /api/v2/operation-catalog/exposures/`
  - фильтры: `surface`, `tenant_id`, `capability`, `status`, `alias`.
- `POST /api/v2/operation-catalog/exposures/`
  - upsert exposure + bind definition (по `definition_id` или `definition_payload`).
- `POST /api/v2/operation-catalog/exposures/{exposure_id}/publish/`
  - публикация после validate.
- `POST /api/v2/operation-catalog/validate/`
  - dry-run валидация definition/exposure с детальными path errors.
- `GET /api/v2/operation-catalog/migration-issues/`
  - список невалидных объектов после backfill.

### 3) `extensions.set_flags` + target binding
- В unified persistence binding хранится в `operation_exposure.capability_config.target_binding.extension_name_param`.
- UI/Backend используют поле binding напрямую из unified exposure.
- Fail-closed: exposure `extensions.set_flags` без валидного binding получает `status=invalid` и не участвует в effective catalog/plan.

## Migration Plan
### Phase A: Prepare
- Создать новые таблицы и сервисный слой.
- Подготовить maintenance window и запретить mutation на старых endpoints перед backfill.

### Phase B: Backfill
- Загрузить `OperationTemplate` и `ui.action_catalog` в unified store.
- Выполнить дедупликацию definitions по `fingerprint` в рамках одинакового tenant scope.
- Проблемные записи (`invalid`) зафиксировать в `operation_migration_issue`.

### Phase C: Cutover
- Переключить `/templates`, `/settings/action-catalog`, `extensions/plan|apply` на unified read/write path.
- Отключить legacy write-path `ui.action_catalog` и прямое использование `OperationTemplate` как primary persistence.

### Phase D: Cleanup
- Удалить legacy persistence/use-path для `ui.action_catalog` и связанные адаптеры.
- Обновить OpenAPI и frontend client только на unified contracts.

## Security / RBAC
- Сохраняется текущая модель прав:
  - templates permissions (`templates.view/manage_*`);
  - action-catalog staff/tenant-admin правила.
- RBAC применяется на уровне exposure (`surface`, `tenant`, `is_active`), затем на уровне definition (валидность executor).

## Observability
- Метрики:
  - `unified_contract_invalid_exposure_total`
  - `unified_contract_backfill_processed_total`
- Structured logs с correlation id и `source_object` (`template:<id>`, `action:<tenant>:<id>`).

## Open Questions
- Нужно ли в первом релизе сразу добавить отдельный admin UI для просмотра `operation_migration_issue`, или достаточно отчёта в логах/CLI.
