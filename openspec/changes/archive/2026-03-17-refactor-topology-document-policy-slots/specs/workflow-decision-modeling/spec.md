## ADDED Requirements

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
