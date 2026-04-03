## ADDED Requirements

### Requirement: Master-data sync and bootstrap routing MUST поддерживать additive reusable-data entity types
Система ДОЛЖНА (SHALL) поддерживать additive routing новых reusable-data entity types через existing sync/bootstrap execution path, если для типа объявлены sync/bootstrapping capabilities в reusable-data registry.

Система НЕ ДОЛЖНА (SHALL NOT) вводить отдельный ad hoc async lifecycle только ради `GLAccount` или последующих reusable entity types.
Система НЕ ДОЛЖНА (SHALL NOT) выводить sync/bootstrap eligibility только из наличия entity type в enum, API namespace или binding table.
Bootstrap dependency order, runtime enqueue eligibility и outbox fan-out ДОЛЖНЫ (SHALL) читаться из executable reusable-data registry/type handlers, а не из независимых hardcoded списков, которые команда должна синхронно поддерживать вручную.

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

Runtime enqueue/outbox path ДОЛЖЕН (SHALL) читать это решение из executable reusable-data registry capability contract.
Operator-facing sync availability/read-model ДОЛЖНЫ (SHALL) читать то же capability решение и НЕ ДОЛЖНЫ (SHALL NOT) показывать generic mutating controls для unsupported directions.

#### Scenario: Сохранение GLAccount не порождает automatic outbound sync intent
- **GIVEN** оператор редактирует canonical `GLAccount` в CC
- **WHEN** система анализирует sync ownership для этого entity type через executable reusable-data registry
- **THEN** automatic outbound sync intent в target ИБ не формируется
- **AND** дальнейшая mutation plan-of-accounts не происходит без отдельного одобренного change

#### Scenario: GLAccountSet не появляется как mutating sync entity
- **GIVEN** оператор открывает sync-oriented surface для reusable-data entities
- **WHEN** система строит доступные sync actions из executable reusable-data registry
- **THEN** `GLAccountSet` отсутствует среди mutating sync actions или показывается только как non-actionable profile state
- **AND** UI и backend read одну и ту же capability policy без расхождения
