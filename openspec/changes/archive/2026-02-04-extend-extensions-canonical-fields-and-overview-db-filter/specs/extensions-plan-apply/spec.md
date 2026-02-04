## MODIFIED Requirements

### Requirement: Tenant-scoped mapping для extensions inventory
Система ДОЛЖНА (SHALL) позволять tenant-admin настроить mapping нормализованного extensions snapshot в канонический `extensions_inventory`.

#### Scenario: Mapping применяется в preview
- **GIVEN** tenant A настроил mapping для `extensions_inventory`
- **WHEN** пользователь делает preview snapshot
- **THEN** результат отображается в каноническом формате и валидируется по schema, где `extensions[]` поддерживает поля:
  - `name` (обязательно)
  - `purpose` (опционально)
  - `is_active` (опционально)
  - `safe_mode` (опционально)
  - `unsafe_action_protection` (опционально)

