## ADDED Requirements

### Requirement: Document plan compile MUST резолвить document policy per topology edge
Система ДОЛЖНА (SHALL) во время compile `document_plan_artifact` резолвить `document_policy` отдельно для каждого topology edge allocation через:
- `edge.metadata.document_policy_key`;
- selected `pool_workflow_binding.decisions[].decision_key`;
- concrete `document_policy` output matching decision revision.

Система НЕ ДОЛЖНА (SHALL NOT) выбирать один общий `compiled_document_policy` на весь binding/run, если run содержит несколько edges с разными slot selectors.

Missing selector, missing matching slot, invalid policy output или duplicate slot mapping ДОЛЖНЫ (SHALL) завершать compile fail-closed до `pool.publication_odata`.

#### Scenario: Runtime компилирует разные document policies для разных edges одного run
- **GIVEN** distribution artifact содержит allocations по двум разным edges
- **AND** у этих edges указаны разные `document_policy_key`
- **AND** selected binding pin-ит matching decisions для обоих slot'ов
- **WHEN** runtime выполняет compile `document_plan_artifact`
- **THEN** execution context получает artifact, где policies/chains резолвятся per edge
- **AND** downstream publication шаги строятся из этого per-edge artifact, а не из single global policy

#### Scenario: Missing slot selector блокирует publication до side effects
- **GIVEN** distribution artifact содержит allocation по edge без `document_policy_key`
- **WHEN** runtime выполняет compile `document_plan_artifact`
- **THEN** compile завершается fail-closed
- **AND** transition к `pool.publication_odata` не происходит
- **AND** execution diagnostics содержит machine-readable ошибку slot resolution

#### Scenario: Legacy topology policy больше не используется как runtime fallback
- **GIVEN** topology edge содержит legacy `edge.metadata.document_policy`
- **AND** selected binding не предоставляет matching slot-based policy resolution
- **WHEN** runtime выполняет compile `document_plan_artifact`
- **THEN** execution завершается fail-closed
- **AND** система не materialize'ит policy из legacy topology metadata молча
