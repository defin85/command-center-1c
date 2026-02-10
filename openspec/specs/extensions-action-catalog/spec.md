# extensions-action-catalog Specification

## Purpose
TBD - created by archiving change add-extensions-action-catalog-runtime-setting. Update Purpose after archive.
## Requirements
### Requirement: Action Catalog capability MUST быть полностью decommissioned
Система НЕ ДОЛЖНА (SHALL NOT) предоставлять runtime и management контракты Action Catalog как platform capability.

#### Scenario: Legacy endpoint недоступен
- **WHEN** клиент вызывает `GET /api/v2/ui/action-catalog/`
- **THEN** API возвращает `HTTP 404`
- **AND** тело ошибки содержит `error.code="NOT_FOUND"`
- **AND** runtime execution через action catalog недоступен

#### Scenario: Action-catalog surface недоступен в operation-catalog
- **WHEN** клиент вызывает operation-catalog c `surface=action_catalog`
- **THEN** API возвращает `HTTP 400` (`VALIDATION_ERROR`)
- **AND** action-catalog management path не активируется

#### Scenario: Legacy action-catalog данные удалены
- **WHEN** завершён cutover migration
- **THEN** `surface=action_catalog` exposure rows отсутствуют в БД
- **AND** capability не может быть реактивирована конфигурацией

