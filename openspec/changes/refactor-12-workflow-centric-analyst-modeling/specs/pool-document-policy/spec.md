## MODIFIED Requirements
### Requirement: Document policy MUST быть декларативным и пользовательски управляемым в tenant scope
Система ДОЛЖНА (SHALL) поддерживать versioned domain contract `document_policy.v1` как concrete compiled runtime contract, используемый downstream publication/runtime слоями.

После workflow-centric cutover analyst-facing source-of-truth для document rules ДОЛЖЕН (SHALL) формироваться через:
- workflow definitions;
- decision resources;
- pool workflow bindings.

Direct authoring `document_policy` на pool topology edges НЕ ДОЛЖЕН (SHALL NOT) оставаться primary путем моделирования для новых analyst-facing схем.

Система МОЖЕТ (MAY) сохранять compiled `document_policy.v1` в runtime projection, включая metadata/read-model структуры, если это нужно для compatibility, preview, audit и downstream compile.

#### Scenario: Workflow binding компилируется в concrete document policy
- **GIVEN** аналитик настроил workflow definition, decisions и pool binding
- **WHEN** система строит effective runtime projection для запуска
- **THEN** формируется concrete `document_policy.v1`
- **AND** downstream runtime использует именно этот compiled contract, а не raw analyst authoring objects

## ADDED Requirements
### Requirement: Workflow-centric authoring MUST материализоваться в deterministic document policy до publication compile
Система ДОЛЖНА (SHALL) материализовать workflow-centric authoring в deterministic concrete `document_policy.v1` до построения `document_plan_artifact.v1` и атомарного workflow compile.

Система НЕ ДОЛЖНА (SHALL NOT) выполнять publication compile напрямую из raw workflow/decision authoring без промежуточного concrete policy contract.

#### Scenario: Одинаковый binding и decisions дают одинаковый compiled document policy
- **GIVEN** одинаковые workflow revision, decision revisions, binding parameters и pool context
- **WHEN** система повторно компилирует effective document policy
- **THEN** структура compiled `document_policy.v1` совпадает
- **AND** downstream `document_plan_artifact` получает один и тот же source contract
