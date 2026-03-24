# workflow-decision-modeling Specification

## Purpose
TBD - created by archiving change refactor-12-workflow-centric-analyst-modeling. Update Purpose after archive.
## Requirements
### Requirement: Workflow definitions MUST быть analyst-facing библиотекой схем распределения
Система ДОЛЖНА (SHALL) использовать versioned `workflow definition` как primary analyst-facing артефакт для описания схем распределения и публикации, переиспользуемых между несколькими `pool`.

Workflow definition ДОЛЖЕН (SHALL) поддерживать:
- доменные стадии и task types;
- pinned references на templates, decisions и subworkflows;
- role-aware orchestration без прямой привязки ко всем concrete organization id в самом definition;
- reusable versioned authoring независимо от конкретного `pool`.

#### Scenario: Один workflow definition переиспользуется несколькими pool bindings
- **GIVEN** аналитик создал workflow definition `services_publication_v3`
- **AND** два разных `pool` используют этот workflow через собственные bindings
- **WHEN** оператор просматривает доступные схемы для обоих pool
- **THEN** система показывает одну и ту же workflow revision как общий analyst-authored source
- **AND** runtime bindings и параметры для каждого pool остаются независимыми

### Requirement: Workflow modeling MUST разделять orchestration и decisions
Система ДОЛЖНА (SHALL) поддерживать явный decision layer для business rules, который вызывается из workflow definition как first-class reference, а не кодируется преимущественно через произвольные inline `condition` выражения.

Decision resource ДОЛЖЕН (SHALL) быть versioned, иметь explicit input/output contract и поддерживать pinned binding из workflow.

#### Scenario: Decision node выбирает вариант документной цепочки без inline business logic
- **GIVEN** workflow содержит шаг выбора варианта публикации документов
- **WHEN** аналитик настраивает этот шаг
- **THEN** шаг ссылается на versioned decision resource
- **AND** major business rules не хранятся как неструктурированная строка в edge condition

### Requirement: Workflow modeling MUST поддерживать reusable subworkflows с pinned binding
Система ДОЛЖНА (SHALL) поддерживать reusable subworkflow/call-activity semantics для повторного использования общих process fragments без копирования полного graph.

Binding subworkflow ДОЛЖЕН (SHALL) поддерживать pinned revision и explicit input/output mapping.

Runtime ДОЛЖЕН (SHALL) исполнять reusable subworkflow по pinned revision metadata из `subworkflow_ref(binding_mode="pinned_revision")` для analyst-authored workflow surfaces.

Runtime НЕ ДОЛЖЕН (SHALL NOT) silently использовать compatibility field `subworkflow_id` вместо pinned revision, если `subworkflow_ref` уже задан.

При missing/drifted/conflicting pinned metadata система ДОЛЖНА (SHALL) завершать subworkflow resolution fail-closed и возвращать lineage/diagnostics, указывающие на проблемный pinned binding.

Pinned subworkflow provenance ДОЛЖЕН (SHALL) фиксироваться в run lineage/diagnostics на момент исполнения и НЕ ДОЛЖЕН (SHALL NOT) реконструироваться постфактум из mutable latest revision.

#### Scenario: Workflow вызывает pinned subworkflow revision
- **GIVEN** analyst workflow использует reusable subprocess `approval_gate`
- **WHEN** definition сохраняется с pinned binding на revision `7`
- **THEN** runtime lineage фиксирует именно revision `7`
- **AND** последующие изменения latest revision не меняют уже сохранённый binding молча

#### Scenario: Конфликт между subworkflow_id и pinned subworkflow_ref отклоняется fail-closed
- **GIVEN** workflow node содержит `subworkflow_ref(binding_mode="pinned_revision")`
- **AND** compatibility field `subworkflow_id` указывает на другую revision или другой workflow
- **WHEN** runtime пытается исполнить subworkflow
- **THEN** система отклоняет выполнение fail-closed
- **AND** не подменяет pinned binding compatibility-полем молча

#### Scenario: Run lineage фиксирует исполненную pinned subworkflow revision
- **GIVEN** analyst-authored workflow содержит reusable subworkflow с pinned revision
- **WHEN** runtime успешно исполняет этот subworkflow
- **THEN** run lineage/diagnostics сохраняет исполненную subworkflow revision как provenance snapshot
- **AND** последующее изменение latest revision не меняет уже сохранённую диагностику

### Requirement: Workflow catalog MUST разделять user-authored definitions и system-managed runtime projections
Система ДОЛЖНА (SHALL) визуально и контрактно разделять:
- user-authored workflow definitions;
- system-managed/generated runtime workflow projections.

Generated runtime workflows НЕ ДОЛЖНЫ (SHALL NOT) отображаться в analyst-facing workflow catalog как обычные редактируемые definitions.

#### Scenario: Analyst-facing `/workflows` не смешивает authored definitions и generated runtime graphs
- **GIVEN** в системе существуют analyst-authored workflows и system-managed runtime projections
- **WHEN** пользователь открывает analyst-facing workflow catalog
- **THEN** список по умолчанию показывает только authored definitions
- **AND** generated runtime projections доступны только в отдельном read-only diagnostic surface

### Requirement: Decision resources MUST быть first-class authoring surface для workflow-centric document rules
Система ДОЛЖНА (SHALL) предоставлять first-class authoring/read-model surface для versioned decision resources, используемых workflow-centric `document_policy`.

Frontend surface ДОЛЖЕН (SHALL):
- использовать отдельный route `/decisions` как canonical decision lifecycle surface;
- поддерживать lifecycle `list/detail/create/clone/revise/archive-deactivate` без ручного API-клиента;
- создавать, клонировать и ревизировать decision resources без ручного API-клиента;
- импортировать legacy `edge.metadata.document_policy` в decision resource revision;
- использовать shared configuration-scoped metadata snapshots для document-policy builder/preview;
- сохранять и показывать resolved metadata snapshot provenance/compatibility markers для `document_policy` revisions;
- показывать produced `document_policy` output и pinned provenance;
- позволять workflow/binding editor'ам выбирать resulting decision revision из first-class списка, а не требовать manual raw ids как primary UX;
- предоставлять guided rollover flow для создания новой `decision_revision` из существующей revision под metadata context выбранной ИБ;
- позволять аналитику использовать revision вне default compatible selection как explicit source для rollover flow без превращения этой revision в default candidate для новых pins;
- явно показывать `source revision`, `target database` и resolved target metadata context до публикации новой revision;
- предоставлять отдельный clone flow для публикации нового independent decision resource из существующей revision без reuse `parent_version_id`.

`/workflows` ДОЛЖЕН (SHALL) использовать `/decisions` как reference catalog для выбора pinned decision revisions внутри workflow composition и НЕ ДОЛЖЕН (SHALL NOT) быть единственным decision CRUD surface.

#### Scenario: Аналитик клонирует revision в новый independent decision resource
- **GIVEN** аналитик выбрал существующую `document_policy` revision в `/decisions`
- **WHEN** он запускает `Clone selected revision`
- **THEN** UI открывает editor с policy из source revision как editable seed
- **AND** `decision_table_id` доступен для редактирования как новый identity cloned resource
- **AND** publish отправляет новый create payload без `parent_version_id`
- **AND** resulting revision публикуется как independent decision resource, а не как новая revision исходного `decision_table_id`

#### Scenario: Clone flow не подменяет rollover semantics
- **GIVEN** аналитик сравнивает actions `Rollover selected revision` и `Clone selected revision`
- **WHEN** он открывает соответствующие editor flows
- **THEN** rollover явно создаёт новую revision существующего resource с `parent_version_id`
- **AND** clone явно создаёт новый independent resource без `parent_version_id`
- **AND** UI copy не допускает двусмысленности между этими режимами

#### Scenario: Clone flow не перепривязывает existing consumers автоматически
- **GIVEN** source revision уже pinned в workflow definitions или bindings
- **WHEN** аналитик успешно публикует cloned decision resource
- **THEN** существующие workflow definitions, workflow bindings и runtime projections не обновляются автоматически
- **AND** clone появляется как отдельный pin candidate только после явного выбора пользователем

### Requirement: `/decisions` MUST hand off metadata management to `/databases`
Система ДОЛЖНА (SHALL) сохранять `/decisions` как metadata-aware decision lifecycle surface, но НЕ ДОЛЖНА (SHALL NOT) превращать его в primary operator surface для configuration profile или metadata snapshot maintenance.

`/decisions` ДОЛЖЕН (SHALL):
- показывать resolved target metadata context в read-only виде;
- различать проблемы business identity/profile и проблемы current snapshot;
- при отсутствии или устаревании metadata context давать явный CTA/handoff в `/databases`.

Система НЕ ДОЛЖНА (SHALL NOT) ограничиваться generic сообщением о необходимости "reload database-specific metadata" без указания canonical management surface.

#### Scenario: Metadata context unavailable -> UI направляет в `/databases`
- **GIVEN** аналитик открыл `/decisions` для базы, у которой отсутствует current metadata context
- **WHEN** UI блокирует edit/deactivate/rollover fail-closed
- **THEN** сообщение объясняет, что metadata management выполняется через `/databases`
- **AND** аналитик получает явный CTA/handoff вместо неадресного reload-сообщения

#### Scenario: `/decisions` остаётся consumer surface, а не mutate hub
- **GIVEN** аналитик просматривает metadata context выбранной ИБ в `/decisions`
- **WHEN** ему требуется metadata maintenance action
- **THEN** экран использует `/databases` как canonical handoff
- **AND** `/decisions` не становится primary местом для refresh/re-verify controls

### Requirement: Workflow definitions MUST оркестрировать publication stages без per-edge document typing
Система ДОЛЖНА (SHALL) использовать workflow definitions для orchestration стадий run-а, а не как primary место хранения per-edge/per-organization matrix document types.

Exact document typing для конкретного target edge ДОЛЖЕН (SHALL) определяться topology selector'ом `edge.metadata.document_policy_key` и selected binding decision slot'ом.

Workflow definition МОЖЕТ (MAY) ссылаться на decisions как на business-rule layer, но НЕ ДОЛЖЕН (SHALL NOT) становиться единственным source-of-truth для того, какой тип документа создавать на конкретном topology edge.

#### Scenario: Один workflow переиспользуется на пулах с разными topology slots
- **GIVEN** один workflow definition используется двумя разными pool bindings
- **AND** эти пулы имеют разные topology edges и разные `document_policy_key`
- **WHEN** runtime выполняет оба run-а
- **THEN** orchestration stages workflow остаются одинаковыми
- **AND** точный выбор document chains определяется topology selectors и binding slots, а не самим workflow definition

#### Scenario: Workflow decision layer не подменяет topology slot mapping
- **GIVEN** workflow содержит decision node для run-wide business rule
- **WHEN** аналитик настраивает publication semantics для конкретных topology edges
- **THEN** workflow не хранит per-edge document matrix внутри definition
- **AND** slot mapping выполняется через topology + binding, а не через workflow graph

### Requirement: Decision authoring surfaces MUST использовать structured reference catalogs как default path
Система ДОЛЖНА (SHALL) предоставлять для analyst-facing decision authoring общий structured reference catalog для workflow revisions и decision revisions, переиспользуемый между `/decisions`, `/workflows` и связанными authoring surfaces.

Default authoring path НЕ ДОЛЖЕН (SHALL NOT) требовать от пользователя ручного copy-paste opaque ids между страницами как primary UX.

Raw/manual reference entry МОЖЕТ (MAY) существовать только как explicit advanced или compatibility path и НЕ ДОЛЖЕН (SHALL NOT) быть единственным или основным способом выбора reusable references.

Pinned inactive или вне default selection revisions ДОЛЖНЫ (SHALL) оставаться читаемыми и различимыми в selectors/detail surfaces, чтобы пользователь не терял lineage context при revise/rollover сценариях.

#### Scenario: Аналитик выбирает reusable references без копирования opaque ids
- **GIVEN** аналитик работает с versioned workflow и decision resources
- **WHEN** он открывает `/decisions` или связанную authoring surface
- **THEN** UI предлагает structured selectors/search surface для выбора revisions
- **AND** пользователю не требуется вручную переносить `decision_table_id`, `decision_revision` или другие opaque ids между страницами как primary path

#### Scenario: Inactive revision остаётся видимой вне default candidate set
- **GIVEN** ранее pinned decision revision больше не входит в default active selection
- **WHEN** аналитик открывает revise или rollover flow
- **THEN** UI продолжает показывать эту revision как текущий lineage context
- **AND** отличает её от default ready-to-pin candidates

### Requirement: `/decisions` MUST быть task-first workspace с shareable route context
Система ДОЛЖНА (SHALL) поддерживать `/decisions` как stateful analyst workspace, где primary authoring context остаётся адресуемым, а основной путь считывается без знания всей внутренней модели платформы.

Default route path ДОЛЖЕН (SHALL):
- синхронизировать selected database, selected decision revision и snapshot filter mode с URL;
- иметь устойчиво подписанный database selector;
- выделять один primary authoring CTA;
- уводить secondary import/diagnostic controls в более слабую визуальную иерархию;
- показывать metadata/provenance/raw diagnostics через explicit progressive disclosure, а не как доминирующий default content.

#### Scenario: Deep link восстанавливает decision workspace context
- **GIVEN** аналитик открыл `/decisions` с query params выбранной базы, revision и snapshot mode
- **WHEN** страница инициализируется или пользователь возвращается через back/forward
- **THEN** UI восстанавливает тот же рабочий контекст
- **AND** не сбрасывает пользователя на произвольную базу или revision

#### Scenario: Основной authoring path не конкурирует с import и diagnostics
- **GIVEN** аналитик впервые открывает `/decisions`
- **WHEN** страница показывает основной workspace
- **THEN** один primary CTA для создания новой policy считывается как главный путь
- **AND** import/legacy/raw flows остаются доступными как secondary actions
- **AND** metadata-heavy diagnostics не доминируют над первым экраном по умолчанию

