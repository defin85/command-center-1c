## ADDED Requirements

### Requirement: Binding decision evaluation MUST materialize publication slot map once per preview or run
Система ДОЛЖНА (SHALL) materialize'ить publication slot map `decision_key -> compiled document_policy` один раз на binding preview/create-run path до compile `document_plan_artifact`.

Система НЕ ДОЛЖНА (SHALL NOT) повторно исполнять decision evaluation для каждого topology edge allocation, если slot map уже materialized для данного preview/run context.

#### Scenario: Slot map materialize'ится один раз и затем используется как lookup source
- **GIVEN** selected binding содержит несколько policy-bearing decisions
- **WHEN** система строит preview или create-run execution context
- **THEN** decisions materialize'ятся в slot map один раз
- **AND** downstream per-edge compile использует этот slot map как lookup source
- **AND** additional decision evaluation per allocation не выполняется

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

### Requirement: Retry and lineage MUST использовать slot-based policy snapshot
Система ДОЛЖНА (SHALL) сохранять в run lineage и execution context slot-based policy snapshot, достаточный для preview/audit/retry semantics.

Snapshot ДОЛЖЕН (SHALL) включать как минимум:
- selected binding provenance;
- materialized publication slot map или эквивалентную pinned slot projection;
- per-edge resolved slot provenance в downstream artifact/read model.

Retry path НЕ ДОЛЖЕН (SHALL NOT) заново реконструировать effective policy из mutable latest binding state или legacy topology metadata, если slot-based snapshot уже сохранён.

#### Scenario: Retry использует persisted slot snapshot вместо legacy reconstruction
- **GIVEN** initial run уже сохранил slot-based policy snapshot и `document_plan_artifact`
- **WHEN** оператор запускает retry
- **THEN** runtime использует persisted slot-based snapshot/artifact
- **AND** не перечитывает legacy topology policy как hidden fallback

#### Scenario: Run lineage показывает slot provenance для edge-aware publication
- **GIVEN** run успешно materialize'ил разные publication slots для разных edges
- **WHEN** оператор открывает lineage или diagnostics
- **THEN** read model показывает selected binding provenance и slot-based resolution summary
- **AND** audit не сводится к одному global compiled policy blob
