## ADDED Requirements
### Requirement: Public API contract MUST быть очищен от legacy Action Catalog schemas
Система НЕ ДОЛЖНА (SHALL NOT) публиковать в OpenAPI legacy response-схемы Action Catalog, не используемые в templates-only модели.

#### Scenario: OpenAPI не содержит legacy Action Catalog response schemas
- **WHEN** публикуется актуальный `contracts/orchestrator/openapi.yaml`
- **THEN** в `components/schemas` отсутствуют `ActionCatalogResponse` и `ActionCatalogExtensions`
- **AND** отсутствуют path-операции, которые ссылаются на эти схемы

#### Scenario: Generated frontend API не экспортирует legacy Action Catalog models
- **WHEN** выполняется codegen frontend API клиента
- **THEN** generated models не содержат `actionCatalogResponse`/`actionCatalogExtensions`
- **AND** templates-only flow использует только актуальные manual-operations контракты
