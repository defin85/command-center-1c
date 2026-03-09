## MODIFIED Requirements
### Requirement: Workflow modeling MUST поддерживать reusable subworkflows с pinned binding
Система ДОЛЖНА (SHALL) поддерживать reusable subworkflow/call-activity semantics для повторного использования общих process fragments без копирования полного graph.

Binding subworkflow ДОЛЖЕН (SHALL) поддерживать pinned revision и explicit input/output mapping.

Runtime ДОЛЖЕН (SHALL) исполнять reusable subworkflow по pinned revision metadata из `subworkflow_ref(binding_mode="pinned_revision")` для analyst-authored workflow surfaces.

Runtime НЕ ДОЛЖЕН (SHALL NOT) silently использовать compatibility field `subworkflow_id` вместо pinned revision, если `subworkflow_ref` уже задан.

При missing/drifted/conflicting pinned metadata система ДОЛЖНА (SHALL) завершать subworkflow resolution fail-closed и возвращать lineage/diagnostics, указывающие на проблемный pinned binding.

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
