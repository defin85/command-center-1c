# Spec Delta: ui-action-catalog-editor

## MODIFIED Requirements
### Requirement: Staff-only endpoint для Action Catalog editor hints
Система ДОЛЖНА (SHALL) предоставлять capability-driven editor hints через generic endpoint:
- `GET /api/v2/ui/operation-exposures/editor-hints/` (staff-only).

Endpoint `/api/v2/ui/action-catalog/editor-hints/` НЕ ДОЛЖЕН (SHALL NOT) оставаться поддерживаемым контрактом.

#### Scenario: Generic hints endpoint доступен только staff
- **WHEN** non-staff вызывает `/api/v2/ui/operation-exposures/editor-hints/`
- **THEN** API возвращает `403 Forbidden`
- **AND** hints не раскрываются

#### Scenario: Staff получает capability hints через generic endpoint
- **WHEN** staff вызывает `/api/v2/ui/operation-exposures/editor-hints/`
- **THEN** API возвращает `capabilities` (включая `extensions.set_flags`)
- **AND** структура hints пригодна для unified editor в surfaces `template` и `action_catalog`
