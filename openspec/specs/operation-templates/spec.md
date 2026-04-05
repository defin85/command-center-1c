# operation-templates Specification

## Purpose
TBD - created by archiving change add-unified-templates-action-catalog-contract. Update Purpose after archive.
## Requirements
### Requirement: Templates API MUST использовать unified persistent store
Система ДОЛЖНА (SHALL) управлять templates через unified management API `operation-catalog` (`surface="template"`), а не через persistent projection `OperationTemplate`.

При этом внешний контракт ДОЛЖЕН (SHALL) оставаться backward-compatible по identifier naming (`template_id`, `operation_templates` в API-полях/ответах, где это уже зафиксировано клиентами).

#### Scenario: Management API возвращает template по alias с прежним template_id
- **GIVEN** template опубликован как `operation_exposure(surface="template", alias="tpl-sync-default")`
- **WHEN** клиент запрашивает список/детали templates
- **THEN** в ответе используется `template_id="tpl-sync-default"` (или эквивалентный id поля в текущем контракте)
- **AND** данные шаблона читаются из `operation_exposure + operation_definition`

### Requirement: Templates write-path MUST поддерживать dedup execution definitions
Система ДОЛЖНА (SHALL) при create/update template переиспользовать существующий `operation_definition`, если execution payload идентичен (fingerprint match).

#### Scenario: Создание template с уже существующим execution payload
- **GIVEN** в unified store уже есть `operation_definition` с тем же fingerprint
- **WHEN** создаётся новый template exposure
- **THEN** система создаёт только новый exposure
- **AND** existing definition переиспользуется

### Requirement: Templates RBAC MUST сохраниться при переходе на unified persistence
Система ДОЛЖНА (SHALL) сохранить текущие ограничения доступа templates API (view/manage) после перехода на exposure-only модель.

Template RBAC НЕ ДОЛЖЕН (SHALL NOT) зависеть от FK на `OperationTemplate` после cutover.
Template RBAC ДОЛЖЕН (SHALL) храниться в exposure-ориентированных permission-структурах (`user/group -> exposure`) и использоваться в `rbac`/`effective-access` endpoint'ах.

#### Scenario: Проверка прав работает без OperationTemplate rows
- **GIVEN** legacy `operation_templates` projection удалён
- **WHEN** пользователь запрашивает templates list или выполняет template upsert/delete
- **THEN** система вычисляет доступ через exposure-ориентированные шаблонные права
- **AND** решение по доступу совпадает с ожидаемым view/manage уровнем

#### Scenario: Effective access резолвится через exposure permissions
- **GIVEN** у пользователя заданы прямые и групповые template права
- **WHEN** вызывается endpoint effective access
- **THEN** итоговый уровень доступа рассчитывается без чтения `OperationTemplate*Permission`
- **AND** результат соответствует прежней семантике max(view/manage/admin)

### Requirement: `/templates` MUST быть единым UI управления template и action exposures
Система ДОЛЖНА (SHALL) использовать `/templates` как templates-only реестр `operation_exposure(surface="template")`.

#### Scenario: `/templates` не показывает action-catalog controls
- **WHEN** пользователь открывает `/templates`
- **THEN** UI показывает только templates
- **AND** controls `Action Catalog`/`New Action` отсутствуют

#### Scenario: Legacy deep-link `surface=action_catalog` нормализуется
- **WHEN** пользователь открывает `/templates?surface=action_catalog`
- **THEN** UI нормализует состояние к templates-only
- **AND** action-catalog запросы не отправляются

### Requirement: `/templates` list MUST использовать server-driven unified exposures contract
Система ДОЛЖНА (SHALL) использовать server-driven list контракт `operation-catalog/exposures` для template-only выборки.

#### Scenario: Table state обрабатывается backend-ом
- **GIVEN** пользователь применил search/filters/sort/pagination
- **WHEN** UI выполняет list запрос
- **THEN** backend возвращает paged template-only результат
- **AND** UI не делает client-side merge разных surfaces

### Requirement: Template editor MUST быть универсальным по executor kinds
Система ДОЛЖНА (SHALL) поддерживать в templates editor executor kinds `ibcmd_cli`, `designer_cli`, `workflow` в едином editor shell.

#### Scenario: Один editor shell конфигурирует разные executor kinds
- **WHEN** пользователь переключает executor kind в template editor
- **THEN** UI остаётся в одном modal flow
- **AND** shape payload валидируется как template contract

### Requirement: Template MUST быть явно совместим с manual operation
Система ДОЛЖНА (SHALL) явно маркировать template exposure для manual operation совместимости через `capability` template exposure.

#### Scenario: Template помечен как compatible с manual operation
- **GIVEN** template предназначен для `extensions.set_flags`
- **WHEN** template сохраняется
- **THEN** `exposure.capability` фиксируется как `extensions.set_flags`
- **AND** template может использоваться только этим manual operation key

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

### Requirement: Big-bang switch MUST завершать dual-read/dual-write режим
Система ДОЛЖНА (SHALL) после switch-фазы отключить dual-read/dual-write на `OperationTemplate` в templates контуре.

#### Scenario: Post-switch запись template не создаёт legacy projection
- **WHEN** пользователь создаёт или обновляет template после cutover
- **THEN** изменяются только `operation_definition` и `operation_exposure`
- **AND** попытка читать/писать `OperationTemplate` не выполняется

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

### Requirement: Pool runtime templates MUST быть system-managed и недоступны для пользовательского write-path
Система ДОЛЖНА (SHALL) помечать runtime templates с alias `pool.*` как system-managed в domain `pool_runtime`.

Система НЕ ДОЛЖНА (SHALL NOT) позволять create/update/delete этих templates через публичный templates management API.

Система ДОЛЖНА (SHALL) показывать system-managed `pool.*` templates в `/templates` list для пользователей с правом просмотра templates, как read-only сущности с явным индикатором system-managed/domain.

#### Scenario: Попытка изменить system-managed pool template через `/templates` отклоняется
- **GIVEN** существует system-managed template alias `pool.prepare_input`
- **WHEN** пользователь отправляет update/delete через templates write endpoint
- **THEN** система возвращает отказ доступа или business conflict
- **AND** definition/exposure не изменяются

#### Scenario: `/templates` list показывает system-managed pool templates как read-only
- **GIVEN** в registry присутствуют alias `pool.prepare_input` и `pool.publication_odata`
- **WHEN** пользователь с правом template view открывает `/templates`
- **THEN** список содержит эти alias
- **AND** строки помечены как `system-managed` в domain `pool_runtime`
- **AND** UI не предлагает edit/delete action для этих строк

### Requirement: System-managed pool runtime registry MUST поддерживать bootstrap и introspection
Система ДОЛЖНА (SHALL) поддерживать bootstrap/sync процесс, который поддерживает полный набор required pool runtime aliases в согласованном состоянии.

Система ДОЛЖНА (SHALL) предоставлять read-only introspection registry статуса (configured/missing/drift) для диагностики.

Канонический список required aliases в `contract_version="pool_runtime.v1"`:
- `pool.prepare_input`
- `pool.distribution_calculation.top_down`
- `pool.distribution_calculation.bottom_up`
- `pool.reconciliation_report`
- `pool.approval_gate`
- `pool.publication_odata`

#### Scenario: Bootstrap восстанавливает отсутствующий системный alias
- **GIVEN** один из required alias `pool.publication_odata` отсутствует в registry
- **WHEN** выполняется bootstrap/sync системных pool runtime templates
- **THEN** alias создаётся или восстанавливается в активном состоянии
- **AND** introspection показывает статус `configured`

#### Scenario: Introspection возвращает contract version и полный набор required aliases
- **GIVEN** системный pool runtime registry синхронизирован
- **WHEN** staff/system клиент читает introspection состояние registry
- **THEN** ответ содержит `contract_version="pool_runtime.v1"`
- **AND** ответ содержит все required aliases из контракта

### Requirement: Pool runtime templates MUST использовать выделенный executor kind для доменного backend
Система ДОЛЖНА (SHALL) сохранять системные pool runtime templates с executor kind, маршрутизируемым в `PoolDomainBackend`.

#### Scenario: Runtime resolve system-managed pool template выбирает PoolDomainBackend
- **GIVEN** operation node резолвится в system-managed pool runtime template
- **WHEN** handler выбирает backend по executor kind template
- **THEN** routing указывает на `PoolDomainBackend`
- **AND** generic CLI backend не используется

### Requirement: Templates MUST оставаться каталогом атомарных операций
Система ДОЛЖНА (SHALL) использовать `/templates` как catalog of atomic execution building blocks и НЕ ДОЛЖНА (SHALL NOT) использовать templates как primary analyst-facing surface для моделирования схем распределения или публикации.

Если система сохраняет `workflow` как executor kind template, этот режим ДОЛЖЕН (SHALL) быть явно помечен как compatibility/integration path, а не как рекомендуемый путь для analyst-authored process composition.

Shipped `/templates` surface ДОЛЖЕН (SHALL) показывать для workflow executor templates явный compatibility marker/warning и направлять analyst authoring в `/workflows` как primary composition surface.

Default `/templates` path НЕ ДОЛЖЕН (SHALL NOT) представлять workflow executor templates как рекомендуемый или основной путь для новых analyst-authored схем.

#### Scenario: Analyst создает схему в `/workflows`, а не в `/templates`
- **GIVEN** аналитик хочет описать новую схему распределения
- **WHEN** он использует analyst-facing surfaces системы
- **THEN** схема создаётся как workflow definition
- **AND** `/templates` используется только для выбора атомарных операций, из которых workflow собирает шаги

#### Scenario: Workflow executor template в `/templates` помечен как compatibility-only
- **GIVEN** оператор открывает `/templates` и видит template с `executor_kind="workflow"`
- **WHEN** UI рендерит список или editor для такого template
- **THEN** интерфейс показывает явную compatibility/integration маркировку
- **AND** `/workflows` обозначается как primary analyst-facing surface для process composition

### Requirement: Templates MUST публиковать явный execution contract для workflow nodes
Система ДОЛЖНА (SHALL) публиковать для templates explicit execution contract, пригодный для analyst-friendly workflow authoring:
- capability;
- input/output contract;
- side-effect profile;
- binding provenance.

Workflow editor ДОЛЖЕН (SHALL) использовать этот contract при выборе template для operation node.

#### Scenario: Workflow editor показывает contract выбранного template
- **GIVEN** аналитик выбирает template для operation node
- **WHEN** editor загружает metadata template
- **THEN** пользователь видит capability, input/output contract и side-effect summary
- **AND** editor использует эти данные для валидации настройки шага

### Requirement: `/templates` MUST использовать canonical template management workspace
Система ДОЛЖНА (SHALL) представлять `/templates` как template management workspace с route-addressable selected template/filter context и canonical authoring surfaces для create/edit/inspect flows.

#### Scenario: Template workspace восстанавливает selected template context из URL
- **GIVEN** оператор открывает `/templates` с query state, указывающим фильтры и выбранный template
- **WHEN** страница перезагружается или открывается по deep-link
- **THEN** workspace восстанавливает тот же template context
- **AND** primary create/edit flow использует canonical secondary surface внутри platform workspace

