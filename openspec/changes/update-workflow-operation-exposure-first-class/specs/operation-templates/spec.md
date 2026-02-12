## MODIFIED Requirements
### Requirement: Workflow operation runtime MUST резолвить template через OperationExposure alias
Система ДОЛЖНА (SHALL) в operation-node execution path резолвить template через `OperationExposure` и связанный `OperationDefinition`.

Runtime ДОЛЖЕН (SHALL) поддерживать два режима binding:
- `alias_latest`: resolve по `OperationExposure(surface="template", alias=<template_alias>)`;
- `pinned_exposure`: resolve по `template_exposure_id` c проверкой `template_exposure_revision`.

Runtime ДОЛЖЕН (SHALL) работать fail-closed: при неуспешном resolve exposure или drift-check fallback к `OperationTemplate` НЕ ДОЛЖЕН (SHALL NOT) выполняться.

#### Scenario: Legacy workflow с template_id продолжает исполняться
- **GIVEN** operation node содержит только `template_id="tpl-odata-create"` без `operation_ref`
- **WHEN** workflow engine запускает operation node
- **THEN** runtime выполняет resolve как `alias_latest` через `operation_exposure.alias`
- **AND** шаблон и execution payload берутся из exposure/definition модели

#### Scenario: Pinned exposure выполняется только при совпадении revision
- **GIVEN** operation node содержит `operation_ref(binding_mode="pinned_exposure", template_exposure_id=<uuid>, template_exposure_revision=12)`
- **WHEN** workflow engine запускает operation node
- **THEN** runtime резолвит template по `template_exposure_id`
- **AND** выполнение продолжается только если `exposure_revision==12`

#### Scenario: Drift pinned exposure отклоняется fail-closed
- **GIVEN** operation node содержит `operation_ref(binding_mode="pinned_exposure", template_exposure_id=<uuid>, template_exposure_revision=12)`
- **AND** актуальный `exposure_revision` равен `13`
- **WHEN** workflow engine запускает operation node
- **THEN** выполнение завершается ошибкой `TEMPLATE_DRIFT` (или эквивалентным fail-closed кодом)
- **AND** enqueue операции не выполняется
- **AND** fallback на alias/legacy projection не выполняется

### Requirement: Internal template endpoints MUST работать через exposure-only read path
Система ДОЛЖНА (SHALL) обслуживать internal template read/render endpoint'ы через `OperationExposure + OperationDefinition`.

Система ДОЛЖНА (SHALL) поддерживать resolve как по `template_id` (alias), так и по `template_exposure_id` для deterministic pinned execution path.

#### Scenario: Internal get-template поддерживает resolve по template_exposure_id
- **GIVEN** internal сервис передаёт `template_exposure_id=<uuid>`
- **WHEN** вызывается internal `get-template`/`render-template`
- **THEN** endpoint резолвит template через `OperationExposure.id`
- **AND** возвращает payload из связанного `OperationDefinition`

#### Scenario: Legacy internal запрос по template_id остаётся совместимым
- **GIVEN** internal сервис передаёт только `template_id=<alias>`
- **WHEN** вызывается internal `get-template`/`render-template`
- **THEN** endpoint резолвит template через `OperationExposure.alias`
- **AND** статус ответа остаётся совместимым с текущим internal API контрактом

## ADDED Requirements
### Requirement: Workflow node contract MUST поддерживать operation_ref
Система ДОЛЖНА (SHALL) поддерживать в operation-node явный объект `operation_ref` для binding `OperationExposure`:
- `alias` (обязательный),
- `binding_mode` (`alias_latest|pinned_exposure`, обязательный),
- `template_exposure_id` (обязательный для `pinned_exposure`),
- `template_exposure_revision` (обязательный для `pinned_exposure`).

Поле `template_id` ДОЛЖНО (SHALL) сохраняться для backward compatibility на переходный период и рассматриваться как legacy alias-only representation.

#### Scenario: Валидация operation_ref отклоняет неполный pinned binding
- **GIVEN** operation node содержит `operation_ref(binding_mode="pinned_exposure")` без `template_exposure_id` или `template_exposure_revision`
- **WHEN** workflow template проходит schema validation
- **THEN** template отклоняется с ошибкой валидации по обязательным полям pinned режима

#### Scenario: UI сохраняет operation_ref при выборе template
- **GIVEN** пользователь выбирает template в workflow designer
- **WHEN** workflow сохраняется
- **THEN** operation node содержит `operation_ref` с alias и выбранным binding mode
- **AND** при `pinned_exposure` сохраняются `template_exposure_id` и `template_exposure_revision`

### Requirement: Operation node MUST поддерживать явный data-flow contract
Система ДОЛЖНА (SHALL) поддерживать для operation-node явный контракт передачи данных `io`:
- `input_mapping: { target_path -> source_path }`,
- `output_mapping: { target_path -> source_path }`,
- `mode: "implicit_legacy" | "explicit_strict"`.

При `mode="explicit_strict"` runtime ДОЛЖЕН (SHALL) использовать только явно заданные `input_mapping` для подготовки context перед рендерингом шаблона и отклонять выполнение fail-closed при отсутствии обязательных source-path.

При `mode="implicit_legacy"` (по умолчанию для backward compatibility) сохраняется текущая implicit context-передача.

#### Scenario: Operation node с explicit mapping передаёт данные по цепочке детерминированно
- **GIVEN** operation node настроен с `io.mode="explicit_strict"` и `input_mapping/output_mapping`
- **WHEN** workflow engine исполняет node
- **THEN** `TemplateRenderer` получает context, собранный из declared `input_mapping`
- **AND** после успешного выполнения output записывается в context согласно `output_mapping`
- **AND** следующие node могут читать эти значения через указанные target-path

#### Scenario: Missing source path в explicit_strict отклоняется fail-closed
- **GIVEN** operation node использует `io.mode="explicit_strict"` и `input_mapping` с отсутствующим `source_path`
- **WHEN** workflow engine запускает node
- **THEN** выполнение завершается ошибкой `OPERATION_INPUT_MAPPING_ERROR` (или эквивалентным fail-closed кодом)
- **AND** enqueue operation не выполняется

#### Scenario: Legacy operation node без io остаётся совместимым
- **GIVEN** operation node не содержит `io`
- **WHEN** workflow запускается после релиза change
- **THEN** node исполняется в `implicit_legacy` режиме
- **AND** поведение передачи данных остаётся совместимым с текущим contract

### Requirement: Deterministic pinned режим MUST поддерживать поэтапное включение через runtime setting
Система ДОЛЖНА (SHALL) поддерживать runtime setting `workflows.operation_binding.enforce_pinned` для поэтапного включения обязательного `pinned_exposure` режима.

При `enforce_pinned=false` система ДОЛЖНА (SHALL) допускать оба режима (`alias_latest`, `pinned_exposure`).
При `enforce_pinned=true` create/update workflow operation-node ДОЛЖНЫ (SHALL) требовать `binding_mode="pinned_exposure"`.

#### Scenario: enforce_pinned=true отклоняет alias-only operation node
- **GIVEN** runtime setting `workflows.operation_binding.enforce_pinned=true`
- **WHEN** клиент сохраняет workflow с operation node в режиме `alias_latest` или только с `template_id`
- **THEN** запрос отклоняется ошибкой валидации политики binding mode

#### Scenario: Поэтапное включение не ломает существующие workflow до enforcement
- **GIVEN** runtime setting `workflows.operation_binding.enforce_pinned=false`
- **AND** в системе есть legacy workflow с `template_id` без `operation_ref`
- **WHEN** выполняется запуск workflow
- **THEN** workflow исполняется в backward-compatible режиме `alias_latest`

### Requirement: Migration с template_id MUST использовать lazy upgrade и optional backfill tool
Система ДОЛЖНА (SHALL) поддерживать migration strategy для legacy workflow DAG:
- lazy upgrade при сохранении workflow (`template_id -> operation_ref`);
- read-path совместимость для не мигрированных записей;
- optional idempotent management command для массового backfill с `--dry-run`.

Система НЕ ДОЛЖНА (SHALL NOT) требовать обязательный one-time rewrite всех workflow DAG как precondition релиза.

#### Scenario: Legacy workflow автоматически получает operation_ref при сохранении
- **GIVEN** workflow содержит operation node только с `template_id`
- **WHEN** пользователь сохраняет workflow через актуальный API
- **THEN** workflow сохраняется с заполненным `operation_ref`
- **AND** legacy `template_id` сохраняется только как backward-compatible representation

#### Scenario: Backfill command в dry-run режиме не меняет данные
- **GIVEN** в БД есть legacy workflow DAG без `operation_ref`
- **WHEN** оператор запускает backfill command с `--dry-run`
- **THEN** команда возвращает перечень планируемых изменений
- **AND** workflow записи в БД не изменяются

### Requirement: `/templates` list MUST прозрачно показывать provenance template binding
Система ДОЛЖНА (SHALL) в таблице `/templates` показывать ключевые поля provenance для связи `OperationExposure -> OperationDefinition`, чтобы оператор видел, что именно будет исполняться и в каком состоянии публикации находится template.

Минимально обязательные поля list-представления:
- `template_id` (alias exposure),
- `executor.kind`,
- `executor.command_id`,
- `template_exposure_id`,
- `template_exposure_revision`,
- publish/active status.

#### Scenario: Оператор видит runtime provenance прямо в list без открытия raw JSON
- **GIVEN** template exposure опубликован и связан с operation definition
- **WHEN** пользователь открывает `/templates`
- **THEN** строка template показывает alias, executor kind, command_id, exposure id и revision
- **AND** статус publish/active виден без перехода в debug/raw режим

### Requirement: Template modal MUST обеспечивать guided usability и прозрачность «что будет выполнено»
Система ДОЛЖНА (SHALL) предоставлять modal editor шаблона как guided flow с явным source-of-truth для `OperationDefinition` и понятным объяснением итогового execution payload.

Modal ДОЛЖНА (SHALL):
- показывать источник binding (`OperationExposure` alias/id/revision и `OperationDefinition` поля),
- показывать блок preview «что будет выполнено» до сохранения/публикации,
- отображать backend `validation_errors` в привязке к полям формы с понятными причинами блокировки publish/validate.

#### Scenario: Выбор command_id сразу обновляет прозрачный preview исполнения
- **GIVEN** пользователь редактирует template в modal editor
- **WHEN** меняется `executor.command_id`
- **THEN** UI обновляет preview итогового payload из связанного `OperationDefinition`
- **AND** пользователь видит, какие поля заданы вручную, а какие резолвятся из definition

#### Scenario: Ошибки publish validation показываются на уровне полей модалки
- **GIVEN** backend возвращает `validation_errors` при `validate` или `publish`
- **WHEN** modal получает ответ с ошибками
- **THEN** соответствующие поля формы подсвечиваются и получают понятные сообщения
- **AND** UI явно объясняет, почему publish/save заблокирован
