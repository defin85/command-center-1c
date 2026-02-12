## MODIFIED Requirements
### Requirement: Persisted plan/provenance доступен в details
Система ДОЛЖНА (SHALL) сохранять provenance с привязкой к templates/manual operations контракту, где template reference основан на `OperationExposure` идентичности.

Для backward compatibility persisted metadata ДОЛЖЕН (SHALL) сохранять `template_id` как alias exposure и НЕ ДОЛЖЕН (SHALL NOT) зависеть от `OperationTemplate` FK.

Для post-cutover новых template-based операций persisted metadata ДОЛЖЕН (SHALL) включать оба поля:
- `template_id` (alias exposure),
- `template_exposure_id` (UUID exposure).

#### Scenario: Persisted metadata содержит exposure-based template reference
- **WHEN** staff открывает details выполнения manual operation
- **THEN** metadata включает `manual_operation` и `template_id=<operation_exposure.alias>`
- **AND** metadata включает `template_exposure_id=<operation_exposure.id>` для post-cutover записей
- **AND** чтение details не требует `OperationTemplate` записи

#### Scenario: Details остаются читаемыми после удаления operation_templates
- **GIVEN** Big-bang cutover завершён и legacy template projection удалён
- **WHEN** staff открывает historical details операции
- **THEN** persisted plan/provenance успешно возвращаются
- **AND** template provenance резолвится по exposure-based ссылке
- **AND** historical записи без `template_exposure_id` остаются читаемыми через `template_id` alias

## ADDED Requirements
### Requirement: Enqueue metadata MUST быть совместима с exposure-only template моделью
Система ДОЛЖНА (SHALL) при постановке операций в очередь формировать metadata так, чтобы worker/details pipeline однозначно идентифицировал template без зависимости от `OperationTemplate`.

Для post-cutover новых template-based операций message metadata ДОЛЖЕН (SHALL) включать оба поля:
- `template_id` (alias exposure),
- `template_exposure_id` (UUID exposure).

#### Scenario: Worker получает template reference без legacy FK
- **WHEN** orchestrator enqueue'ит операцию, созданную из template
- **THEN** message metadata содержит `template_id` (alias) и `template_exposure_id` (UUID)
- **AND** в message metadata отсутствует зависимость от `OperationTemplate` FK
