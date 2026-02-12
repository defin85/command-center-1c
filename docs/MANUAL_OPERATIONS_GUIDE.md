# Manual Operations (templates-only) — инструкция для операторов

Этот гайд описывает актуальную модель запуска ручных операций после decommission Action Catalog.

## Ключевая модель

- Источник исполнения: только `template` exposure.
- Runtime source-of-truth:
  - binding/identity хранится в `OperationExposure` (alias + `template_exposure_id` + `template_exposure_revision`);
  - исполняемый payload хранится в `OperationDefinition`.
- Запуск ручной операции:
  - выбрать `manual_operation` (`extensions.sync` или `extensions.set_flags`);
  - выбрать `template_id` явно, либо использовать tenant preferred binding.
- Если binding отсутствует/устарел, API возвращает fail-closed ошибку `MISSING_TEMPLATE_BINDING`.

## Как читать provenance в `/templates`

В таблице `/templates` оператор видит минимально достаточный provenance-набор:

- `Alias` = `OperationExposure.alias` (backward-compatible `template_id`);
- `Executor Kind` и `Command ID` = ключевые поля из связанного `OperationDefinition.executor_payload`;
- `Exposure ID` = `template_exposure_id` (UUID exposure);
- `Revision` = `template_exposure_revision` (monotonic version exposure);
- `Status` = publish state exposure (`draft`/`published`/`invalid`).

### Что смотреть в modal editor

В modal (`New/Edit Template`) есть два диагностических блока:

- `Source of truth (binding provenance)`:
  - `OperationExposure.alias`,
  - `template_exposure_id`,
  - `template_exposure_revision`,
  - `OperationDefinition.id`,
  - `publish status`.
- `Что будет выполнено`:
  - preview итогового `OperationDefinition.executor_payload`,
  - `Field origins` (что пришло из ручного ввода и что является derived-значением).

Если backend вернул `validation_errors`, modal показывает:

- общий список причин блокировки save/publish;
- field-level подсветку по `path` (например, `definition.executor_payload.command_id`, `capability_config.target_binding.extension_name_param`).

## Диагностика mismatch `OperationExposure/OperationDefinition`

### Типовые симптомы

- workflow/manual запуск падает с `TEMPLATE_DRIFT` (или эквивалентной fail-closed ошибкой);
- template в `/templates` имеет `status=invalid`;
- команда/параметры в preview не совпадают с ожидаемым execution contract.

### Порядок проверки

1. Открой `/templates` и найди alias нужного шаблона.
2. Сверь `Exposure ID` + `Revision` с ожидаемым binding (для pinned сценариев).
3. Открой modal и проверь блок `Source of truth`:
   - совпадает ли `OperationDefinition.id`,
   - не изменился ли `publish status`.
4. Проверь блок `Что будет выполнено`:
   - `executor.kind`,
   - `command_id`/`workflow_id`,
   - `params`/`input_context`,
   - capability-specific binding (`target_binding.extension_name_param`).
5. Если есть ошибки валидации:
   - исправь поля, подсвеченные в modal;
   - повтори save и убедись, что блокирующие ошибки исчезли.

### Частые причины и действия

- `status=invalid` после редактирования:
  - payload не проходит runtime-contract валидацию;
  - открой modal, исправь подсвеченные поля, сохрани.
- Drift по `template_exposure_revision`:
  - pinned workflow ссылается на старую revision;
  - перепривяжи workflow node (обнови `operation_ref`) или откати exposure до совместимого контракта.
- Alias указывает на изменённый definition:
  - `alias_latest` взял новую версию payload;
  - для детерминизма используй `pinned_exposure` в workflow.

Для инцидентов с массовым drift используй runbook:
`docs/observability/TEMPLATE_DRIFT_RUNBOOK.md`

## Preferred Template Bindings

API:
- `GET /api/v2/extensions/manual-operation-bindings/`
- `PUT /api/v2/extensions/manual-operation-bindings/{manual_operation}/`
- `DELETE /api/v2/extensions/manual-operation-bindings/{manual_operation}/`

Правила:
- binding хранит alias шаблона (`template_id`);
- rename/delete alias не обновляет binding автоматически;
- stale binding после rename/delete приводит к `MISSING_TEMPLATE_BINDING`.

## Планирование и запуск

### Планирование
`POST /api/v2/extensions/plan/`

Обязательные поля:
- `database_ids`
- `manual_operation`

Дополнительно:
- `template_id` (override preferred binding)
- для `extensions.set_flags`:
  - `extension_name`
  - `flags_values`
  - `apply_mask`

### Применение
`POST /api/v2/extensions/apply/`

Обязательное поле:
- `plan_id`

Важно:
- legacy планы action-catalog формата отклоняются с `PLAN_INVALID_LEGACY`;
- apply использует metadata из плана (`result_contract`, `mapping_spec_ref`) как pinned-contract.

## Деактивация legacy Action Catalog

- `GET /api/v2/ui/action-catalog/` возвращает `404` (`error.code=NOT_FOUND`).
- Route `/templates?surface=action_catalog` не используется в рабочем сценарии.
- Все новые настройки и тесты должны опираться на templates-only contracts.
