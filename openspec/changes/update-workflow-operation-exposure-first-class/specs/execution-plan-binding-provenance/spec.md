## MODIFIED Requirements
### Requirement: Enqueue metadata MUST быть совместима с exposure-only template моделью
Система ДОЛЖНА (SHALL) при постановке операций в очередь формировать metadata так, чтобы worker/details pipeline однозначно идентифицировал template без зависимости от `OperationTemplate`.

Для post-cutover template-based операций message metadata ДОЛЖЕН (SHALL) включать поля:
- `template_id` (alias exposure),
- `template_exposure_id` (UUID exposure),
- `template_exposure_revision` (monotonic revision exposure).

#### Scenario: Worker получает template reference без legacy FK
- **WHEN** orchestrator enqueue'ит операцию, созданную из template
- **THEN** message metadata содержит `template_id`, `template_exposure_id` и `template_exposure_revision`
- **AND** в message metadata отсутствует зависимость от `OperationTemplate` FK

#### Scenario: Pinned workflow execution сохраняет deterministic provenance
- **GIVEN** workflow node использует `operation_ref(binding_mode="pinned_exposure", template_exposure_id=<uuid>, template_exposure_revision=12)`
- **WHEN** orchestrator enqueue'ит операцию
- **THEN** metadata операции фиксирует те же `template_exposure_id` и `template_exposure_revision`
- **AND** details API позволяет диагностировать drift/mismatch между конфигурацией node и актуальным exposure state
