## MODIFIED Requirements

### Requirement: Document policy MUST быть декларативным и пользовательски управляемым в tenant scope
Система ДОЛЖНА (SHALL) поддерживать versioned domain contract `document_policy.v1` как concrete compiled runtime contract, используемый downstream publication/runtime слоями.

После topology-slot cutover analyst-facing source-of-truth для document rules ДОЛЖЕН (SHALL) формироваться через:
- decision resources;
- pool workflow bindings;
- topology edge selectors `edge.metadata.document_policy_key`.

Direct authoring `document_policy` на pool topology edges НЕ ДОЛЖЕН (SHALL NOT) оставаться primary путем моделирования для новых analyst-facing схем.

Система МОЖЕТ (MAY) сохранять compiled `document_policy.v1` в runtime projection, включая metadata/read-model структуры, если это нужно для compatibility, preview, audit и downstream compile.

#### Scenario: Один binding materialize'ит несколько concrete policy slots
- **GIVEN** аналитик настроил несколько decision resources и pool binding с разными `decision_key`
- **AND** topology использует разные `edge.metadata.document_policy_key` на разных рёбрах
- **WHEN** система строит effective runtime projection для запуска
- **THEN** document rules materialize'ятся через pinned binding decisions и topology selectors
- **AND** downstream runtime использует concrete `document_policy.v1` per edge, а не raw topology authoring payload

### Requirement: Runtime MUST строить детерминированный document plan artifact из policy
Система ДОЛЖНА (SHALL) компилировать `document_plan_artifact` детерминированно из active topology version за период run, distribution artifact run и per-edge `document_policy`, резолвимого через `edge.metadata.document_policy_key` и selected binding decisions.

Система ДОЛЖНА (SHALL) использовать этот artifact как source-of-truth для create-run publication и retry semantics.

Минимальный обязательный набор полей `document_plan_artifact.v1`:
- `version`;
- `run_id`;
- `distribution_artifact_ref`;
- `topology_version_ref`;
- `policy_refs[]`;
- `targets[].chains[].documents[]` с `entity_name`, `document_role`, `field_mapping`, `table_parts_mapping`, `link_rules`, `invoice_mode`, `idempotency_key`;
- `compile_summary`.

Система НЕ ДОЛЖНА (SHALL NOT) формировать create-run publication chain напрямую из raw `run_input`, если `document_plan_artifact.v1` успешно построен и сохранён.

#### Scenario: Разные edges одного run получают разные document chains
- **GIVEN** один run содержит два allocation на разных topology edges
- **AND** у edges указаны разные `document_policy_key`
- **AND** selected binding pin-ит matching decisions для обоих slot'ов
- **WHEN** runtime выполняет compile document plan
- **THEN** artifact содержит разные document chains для этих targets/edges
- **AND** каждая chain materialize'ится из matching slot policy

#### Scenario: Отсутствующий slot блокирует document plan compile
- **GIVEN** topology edge участвует в allocation
- **AND** у edge отсутствует `document_policy_key` или binding не содержит matching `decision_key`
- **WHEN** runtime выполняет compile document plan
- **THEN** compile завершается fail-closed до OData side effects
- **AND** diagnostics содержит machine-readable код missing slot resolution

### Requirement: Workflow-centric authoring MUST материализоваться в deterministic document policy до publication compile
Система ДОЛЖНА (SHALL) материализовать workflow-centric authoring в deterministic concrete `document_policy.v1` до построения `document_plan_artifact.v1` и атомарного workflow compile.

Система НЕ ДОЛЖНА (SHALL NOT) выполнять publication compile напрямую из raw workflow/decision authoring без промежуточного concrete policy contract.

Для topology-slot scheme concrete policy resolution ДОЛЖЕН (SHALL) выполняться per edge через `document_policy_key -> binding decision`.

#### Scenario: Один и тот же binding дает одинаковый per-edge policy map
- **GIVEN** одинаковые workflow revision, decision revisions, binding parameters, topology version и pool context
- **WHEN** система повторно компилирует effective per-edge document policy map
- **THEN** структура compiled `document_policy.v1` для каждого slot совпадает
- **AND** downstream `document_plan_artifact` получает один и тот же source contract

### Requirement: Legacy edge document policy MUST мигрировать в decision resources и binding refs
Система ДОЛЖНА (SHALL) предоставлять deterministic migration path `edge.metadata.document_policy -> decision resource + pool_workflow_binding.decisions + edge.metadata.document_policy_key`.

Migration path ДОЛЖЕН (SHALL):
- materialize versioned decision resource revision, который возвращает совместимый `document_policy.v1`;
- сохранять provenance от legacy topology edge к resulting decision revision, slot key и affected binding refs;
- позволять backend backfill/import и operator-driven remediation использовать один и тот же deterministic contract;
- не требовать ручного внешнего API-клиента как обязательного шага migration для штатного remediation flow.

#### Scenario: Backend remediation materializes legacy edge policy в decision resource и topology slot
- **GIVEN** topology edge содержит валидный `edge.metadata.document_policy`
- **AND** для пула уже существуют workflow-centric bindings
- **WHEN** backend migration/backfill запускается для этого pool
- **THEN** система создаёт или резолвит versioned decision resource revision с эквивалентным `document_policy.v1`
- **AND** affected bindings получают pinned decision refs с явным `decision_key`
- **AND** topology edge получает matching `document_policy_key`
- **AND** migration report фиксирует source edge и target decision/binding provenance

## REMOVED Requirements

### Requirement: Migration path MUST быть backward-compatible для run-ов без document policy
**Reason**: shipped preview/run path больше не должен silently продолжать legacy publication semantics без explicit slot-based policy resolution после cutover.

**Migration**: до cutover выполнить remediation legacy topology policy в decision revisions + binding slots + topology keys и только после этого включать новый runtime path.
