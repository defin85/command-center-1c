## ADDED Requirements

### Requirement: Reusable account entities MUST иметь explicit sync ownership contract
Система ДОЛЖНА (SHALL) для reusable account entities явно фиксировать поддерживаемые и запрещённые sync directions в executable capability matrix.

Для этого change:
- `GLAccount` МОЖЕТ (MAY) использовать bootstrap import path из ИБ в CC;
- `GLAccount` НЕ ДОЛЖЕН (SHALL NOT) автоматически включаться в `CC -> ИБ` outbound sync или `bidirectional` mutation policy;
- `GLAccountSet` НЕ ДОЛЖЕН (SHALL NOT) участвовать в inbound/outbound sync как target IB entity.

#### Scenario: Сохранение GLAccount не порождает automatic outbound sync intent
- **GIVEN** оператор изменяет canonical `GLAccount` в CC
- **WHEN** runtime оценивает sync ownership для этого entity type
- **THEN** automatic outbound sync intent в target ИБ не формируется
- **AND** plan-of-accounts mutation не происходит без отдельного одобренного change

#### Scenario: GLAccount bootstrap import использует existing staged lifecycle
- **GIVEN** оператор запускает bootstrap import для `GLAccount`
- **WHEN** система создаёт bootstrap job
- **THEN** job использует existing lifecycle `preflight -> dry_run -> execute -> finalize`
- **AND** не появляется отдельный account-only async pipeline
