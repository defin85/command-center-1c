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

#### Scenario: Workflow вызывает pinned subworkflow revision
- **GIVEN** analyst workflow использует reusable subprocess `approval_gate`
- **WHEN** definition сохраняется с pinned binding на revision `7`
- **THEN** runtime lineage фиксирует именно revision `7`
- **AND** последующие изменения latest revision не меняют уже сохранённый binding молча

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

