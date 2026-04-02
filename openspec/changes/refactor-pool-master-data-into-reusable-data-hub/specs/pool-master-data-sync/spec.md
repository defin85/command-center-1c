## ADDED Requirements

### Requirement: Master-data sync and bootstrap routing MUST поддерживать additive reusable-data entity types
Система ДОЛЖНА (SHALL) поддерживать additive routing новых reusable-data entity types через existing sync/bootstrap execution path, если для типа объявлены sync/bootstrapping capabilities в reusable-data registry.

Система НЕ ДОЛЖНА (SHALL NOT) вводить отдельный ad hoc async lifecycle только ради `GLAccount` или последующих reusable entity types.

#### Scenario: GLAccount bootstrap import использует existing staged async lifecycle
- **GIVEN** оператор запускает bootstrap import для `GLAccount`
- **WHEN** система создаёт bootstrap job
- **THEN** job использует existing lifecycle `preflight -> dry_run -> execute -> finalize`
- **AND** не появляется отдельный account-only background pipeline вне existing master-data sync runtime

### Requirement: Reusable account entities MUST иметь explicit sync ownership contract
Система ДОЛЖНА (SHALL) для reusable account entities явно фиксировать, какие sync directions поддерживаются shipped runtime, а какие запрещены fail-closed.

Для этого change:
- `GLAccount` МОЖЕТ (MAY) использовать existing bootstrap import path из ИБ в CC;
- `GLAccount` НЕ ДОЛЖЕН (SHALL NOT) автоматически включаться в generic `CC -> ИБ` outbound sync или `bidirectional` policy;
- `GLAccountSet` НЕ ДОЛЖЕН (SHALL NOT) участвовать в inbound/outbound sync как target IB entity.

#### Scenario: Сохранение GLAccount не порождает automatic outbound sync intent
- **GIVEN** оператор редактирует canonical `GLAccount` в CC
- **WHEN** система анализирует sync ownership для этого entity type
- **THEN** automatic outbound sync intent в target ИБ не формируется
- **AND** дальнейшая mutation plan-of-accounts не происходит без отдельного одобренного change
