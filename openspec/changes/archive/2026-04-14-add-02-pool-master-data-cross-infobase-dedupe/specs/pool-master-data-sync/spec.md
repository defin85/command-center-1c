## ADDED Requirements

### Requirement: Outbound source-of-truth consumption MUST gate on dedupe resolution state
Система ДОЛЖНА (SHALL) перед automatic outbound fan-out, operator-initiated manual rollout и другими outbound source-of-truth side effects проверять resolution state dedupe-enabled canonical entities.

Если affected canonical scope связан с dedupe cluster в unresolved состоянии, система НЕ ДОЛЖНА (SHALL NOT):
- публиковать outbound side effect в target ИБ;
- считать launch item успешно запущенным;
- silently пропускать ambiguity как будто canonical source-of-truth уже стабилен.

Вместо этого система ДОЛЖНА (SHALL):
- сохранять machine-readable failed/skipped/blocking outcome;
- возвращать code `MASTER_DATA_DEDUPE_REVIEW_REQUIRED` или эквивалентный canonical code этого семейства;
- направлять оператора к remediation surface dedupe review.

Это требование распространяется как на automatic outbox-driven rollout, так и на operator manual launch surfaces.

#### Scenario: Manual outbound launch item блокируется unresolved dedupe cluster
- **GIVEN** оператор создаёт outbound/manual sync launch для canonical `Party`
- **AND** связанный dedupe cluster находится в `pending_review`
- **WHEN** runtime оценивает child scope перед фактическим outbound side effect
- **THEN** launch item получает machine-readable blocked outcome
- **AND** child outbound side effect в target ИБ не выполняется
- **AND** оператор получает ссылку на dedupe remediation

#### Scenario: Automatic outbox fan-out не публикует unresolved canonical ambiguity
- **GIVEN** canonical `Item` был изменён в CC, но его source-of-truth dedupe cluster ещё не разрешён
- **WHEN** outbound outbox pipeline пытается создать или доставить target side effect
- **THEN** система не публикует ambiguous canonical состояние в ИБ
- **AND** read-model фиксирует blocker reason вместо silent success
