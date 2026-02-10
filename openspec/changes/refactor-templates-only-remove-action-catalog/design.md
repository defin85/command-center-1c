## Context
Нужен один platform-level execution контракт без конкурирующих источников. Action Catalog должен быть полностью удалён. Ручные операции должны оставаться явными и детерминированными, но исполняться только через templates.

## Goals
- Полный decommission `action_catalog` как capability платформы.
- Единый слой manual operations с жёстко заданными operation keys.
- Templates-only execution path для `/templates`, `/extensions`, `/databases`.
- Единый result contract: raw driver output + user-managed mapping в canonical формат.
- One-shot cutover без fallback и без обратной совместимости.

## Non-Goals
- Поддержка legacy `action_id`/`surface=action_catalog` после релиза.
- Переходный dual-read path.
- Отдельный action editor UI.

## Decisions
### 1. Platform Decommission
- Удаляем capability `action_catalog` целиком.
- `GET /api/v2/ui/action-catalog/` -> `HTTP 404` с `error.code="NOT_FOUND"` (стабильный decommission response).
- `surface=action_catalog` в `operation-catalog` считается невалидным параметром.
- `SURFACE_ACTION_CATALOG` удаляется из `OperationExposure` модели.
- Legacy `surface=action_catalog` данные удаляются hard delete миграцией.

### 2. Hardcoded Manual Operations Layer
Вводится platform registry (кодовый, не пользовательский) со стабильными operation keys.

Начальный набор для extensions:
- `extensions.sync`
- `extensions.set_flags`

`extensions.list` удаляется из runtime модели.

Каждый operation descriptor содержит:
- `operation_key`
- target policy (single/multi database)
- runtime input schema
- required template executor constraints
- result contract id (если есть output mapping)

### 3. Template Compatibility Contract
`template_id` = `operation_exposure.alias` (stable string ID шаблона).

Lifecycle `template_id`:
- preferred bindings хранят alias как строковый идентификатор без surrogate ID,
- rename/delete alias НЕ обновляет preferred bindings автоматически,
- stale binding после rename/delete трактуется как отсутствующий binding и резолвится в `MISSING_TEMPLATE_BINDING`.

Совместимость template с manual operation:
- задаётся явным маркером в template exposure contract (`capability` на template exposure должен совпадать с `manual_operation`),
- валидируется fail-closed на plan этапе.

Для `extensions.set_flags` binding хранится в template payload:
- `template_data.target_binding.extension_name_param`.

### 4. Plan/Apply Request Contract
`POST /api/v2/extensions/plan/` принимает:
- `manual_operation` (required, enum из hardcoded registry),
- `template_id` (optional override),
- operation-specific runtime fields.

Resolve order template:
1. request `template_id` (если передан),
2. tenant preferred template binding для `manual_operation`,
3. иначе fail-closed (`MISSING_TEMPLATE_BINDING`).

Если request `template_id` не существует, возвращается `HTTP 400` + `INVALID_PARAMETER`.

Operation-specific requirements:
- `extensions.sync`: template compatibility + таргеты.
- `extensions.set_flags`: дополнительно `extension_name`, `flags_values`, `apply_mask`.

Legacy `action_id` path всегда отклоняется (`400`).
Ошибки конфигурации/совместимости в `plan/apply` возвращаются как `HTTP 400` + `error.code="CONFIGURATION_ERROR"`.

### 5. Preferred Template Bindings (Persist)
Добавляется tenant-scoped store preferred template per manual operation.

Предлагаемый контракт хранения:
- `tenant_id`
- `manual_operation`
- `template_id`
- `updated_by`
- `updated_at`

Поведение:
- UI показывает текущий preferred template,
- пользователь может переопределить template per launch,
- explicit launch override не изменяет persisted binding автоматически.

API контракт preferred bindings:
- `GET /api/v2/extensions/manual-operation-bindings/` -> список bindings текущего tenant,
- `PUT /api/v2/extensions/manual-operation-bindings/{manual_operation}/` с `template_id` -> upsert binding,
- `DELETE /api/v2/extensions/manual-operation-bindings/{manual_operation}/` -> удалить binding.

Контракт ответа write-операций:
- успех: `200` + актуальный `binding`,
- несовместимый template/manual_operation: `400` + `CONFIGURATION_ERROR`,
- неизвестный `manual_operation`: `400` + `INVALID_PARAMETER`.

### 6. Result Contract + User Mapping
Система задаёт единый canonical result contract через operation descriptor, например:
- для `extensions.sync`: `result_contract = extensions.inventory.v1`.

Пользователь вручную управляет mapping raw driver output -> canonical через mapping specs.

В metadata плана фиксируются:
- `manual_operation`
- `template_id`
- `result_contract`
- `mapping_spec_id`
- `mapping_spec_version`

Completion/snapshot processing использует зафиксированный mapping reference (pinned на момент plan), а не произвольное текущее состояние настроек.

### 7. Metadata & Provenance Semantics
Из execution metadata удаляются action-catalog поля (`action_id`, `action_capability`).

Новый единый набор:
- `execution_source = template_manual_operation`
- `manual_operation`
- `template_id`
- `result_contract`
- `mapping_spec_ref`

Preview/persisted provenance строится на template executor + manual operation context.

### 8. UI Model
- `/templates`: templates-only registry, универсальный editor (`ibcmd_cli`, `designer_cli`, `workflow`) в одной модели.
- `/extensions`: manual operations UI без action-catalog controls.
- `/databases`: запуск manual operations прямо с экрана, тот же backend pipeline.

### 9. Cutover Handling
- Все legacy API контракты action-catalog недоступны сразу после релиза.
- In-flight legacy plans (старого формата) помечаются как `PLAN_INVALID_LEGACY` и не исполняются.
- Критерий legacy plan: отсутствует `metadata.execution_source=template_manual_operation`, либо отсутствуют `manual_operation`/`template_id`, либо присутствуют legacy-поля (`action_id`, `action_capability`).
- Data migration выполняется в том же релизе (hard delete action-catalog rows).
- Hard delete касается только configuration rows; historical plans/executions/snapshots не удаляются.

## Trade-offs
Плюсы:
- один source of truth,
- прозрачный и проверяемый runtime-контракт,
- меньше скрытых зависимостей UI/backend.

Минусы:
- большой breaking change,
- обязательные миграции и обновление большого числа тестов/документации.

## Risks & Mitigations
- Риск несовместимых templates для manual operation.
  - Митигировать compatibility validation + matrix tests.
- Риск неочевидного поведения при отсутствии preferred binding.
  - Митигировать явной ошибкой `MISSING_TEMPLATE_BINDING` и UI CTA на настройку binding.
- Риск поломки snapshots после смены mapping.
  - Митигировать pinned mapping reference в metadata.

## Migration Plan (Single Step)
1. Обновить контракты (OpenAPI/specs) на manual-operations + templates-only.
2. Удалить backend capability `action_catalog` и endpoint `ui/action-catalog`.
3. Применить миграцию hard delete action-catalog exposures + model cleanup.
4. Внедрить manual operations registry + preferred bindings + plan/apply contract.
5. Перевести frontend `/templates`, `/extensions`, `/databases` на новый контракт.
6. Обновить provenance/snapshot pipeline на `manual_operation` metadata + mapping pinning.
7. Обновить docs/tests и выпустить один релиз cutover.

## Open Questions
- Отсутствуют.
