## ADDED Requirements

### Requirement: Locale-boundary governance coverage MUST be inventory-backed for all governed route and shell modules

Система ДОЛЖНА (SHALL) выводить locale-boundary governance coverage из checked-in `routeGovernanceInventory` и `shellSurfaceGovernanceInventory` для всех `platform-governed` route families и shell-backed surfaces.

Validation gate НЕ ДОЛЖЕН (SHALL NOT) зависеть от вручную поддерживаемого pilot-only file set, если repo заявляет full migration coverage шире этой pilot wave.

#### Scenario: Inventory drift blocks repo-wide locale governance completion

- **GIVEN** в checked-in governance inventory появляется новый `platform-governed` route или shell module
- **WHEN** locale-boundary governance checks не покрывают этот module
- **THEN** frontend validation gate сообщает явную inventory/coverage drift причину
- **AND** change не может заявлять repo-wide locale governance coverage до устранения drift

#### Scenario: Raw locale formatting on a governed non-pilot route is still blocked

- **GIVEN** разработчик меняет governed route family вне исходной pilot wave, например `/users` или `/templates`
- **WHEN** route-level module использует raw `toLocaleString()`, `toLocaleDateString()` или `toLocaleTimeString()`
- **THEN** locale-boundary governance check сообщает явное нарушение canonical formatter boundary
- **AND** нарушение ловится тем же blocking gate, что и для pilot routes
