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
- использовать `/decisions` как canonical decision lifecycle surface;
- использовать business configuration identity `config_name + config_version` как primary compatibility contract для metadata-aware `document_policy` revisions;
- сохранять и показывать resolved metadata provenance/diagnostics markers для `document_policy` revisions;
- показывать `config_generation_id` как отдельный technical marker, если он доступен;
- не скрывать compatible decision revisions только из-за другого имени ИБ, `metadata_hash`, `extensions_fingerprint` или `config_generation_id`.

`/decisions` ДОЛЖЕН (SHALL) показывать publication drift как diagnostics/warning, если selected database diverges по published metadata surface от canonical business-scoped snapshot, но такой drift НЕ ДОЛЖЕН (SHALL NOT) сам по себе переводить revision в incompatible.

`/workflows` и binding editor'ы ДОЛЖНЫ (SHALL) получать decision compatibility по business configuration identity и выбирать compatible revision из `/decisions` без требования manual raw ids.

#### Scenario: `/decisions` показывает compatible revision для другой ИБ той же конфигурации
- **GIVEN** decision revision сохранена для `config_name + config_version`
- **AND** аналитик выбирает другую ИБ с той же business configuration identity, но другим именем ИБ
- **WHEN** UI загружает список compatible revisions
- **THEN** revision видна в default compatible selection
- **AND** имя ИБ не ломает compatibility filtering

#### Scenario: `/decisions` не скрывает compatible revision из-за publication drift
- **GIVEN** selected database совпадает со stored revision по `config_name + config_version`
- **AND** selected database имеет другой `metadata_hash`
- **WHEN** UI вычисляет compatibility и отображает provenance
- **THEN** revision остаётся selectable
- **AND** экран показывает warning/diagnostics о publication drift
- **AND** `metadata_hash` divergence не переводит revision в hidden incompatible state

#### Scenario: `/decisions` показывает technical provenance markers отдельно от business compatibility
- **GIVEN** аналитик открыл `document_policy` revision на `/decisions`
- **WHEN** UI показывает metadata-aware provenance этой revision
- **THEN** экран отдельно показывает business identity `config_name + config_version`
- **AND** отдельно показывает technical markers вроде `config_generation_id` и `metadata_hash`
- **AND** user-visible compatibility определяется business identity, а не technical markers

