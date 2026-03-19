## ADDED Requirements
### Requirement: Binding profile detail MUST оставаться summary-first и убирать technical lineage в advanced disclosure
Система ДОЛЖНА (SHALL) показывать на default detail path `/pools/binding-profiles` operator-facing summary как primary content:
- code/name/status/latest revision number;
- workflow summary;
- usage summary и next actions (`publish new revision`, `deactivate`, handoff to pool attachments).

Opaque immutable identifiers (`binding_profile_revision_id`) и raw technical payload НЕ ДОЛЖНЫ (SHALL NOT) оставаться primary default content в revision history или detail summary. Они ДОЛЖНЫ (SHALL) быть доступны только через explicit advanced disclosure path.

Это НЕ ДОЛЖНО (SHALL NOT) менять runtime lineage contract: immutable opaque id остаётся authoritative identity, но default operator path не обязан показывать его раньше human-readable summary.

#### Scenario: Default revision history не показывает opaque pin как primary column
- **GIVEN** оператор открыл detail reusable binding profile на `/pools/binding-profiles`
- **WHEN** он просматривает default revision history
- **THEN** экран показывает human-readable revision number и workflow summary как основной контекст
- **AND** immutable opaque pin hidden behind explicit advanced disclosure

#### Scenario: Support visibility остаётся доступной через advanced path
- **GIVEN** оператору или support engineer нужен immutable pin выбранной revision
- **WHEN** он явно открывает advanced disclosure
- **THEN** UI показывает `binding_profile_revision_id` и related technical payload
- **AND** runtime/support path не теряет access к authoritative lineage identifier

### Requirement: Binding profile inspect flow MUST оставаться mobile-safe и touch-safe
Система ДОЛЖНА (SHALL) обеспечивать, что inspect/revise/deactivate flow на `/pools/binding-profiles` остаётся usable на narrow viewport и touch devices.

Primary selection control в catalog ДОЛЖЕН (SHALL) оставаться semantic interactive element с touch-safe hit area для выбора profile.

Primary detail actions и summary fields в mobile detail drawer НЕ ДОЛЖНЫ (SHALL NOT) клиповаться, выходить за viewport или требовать horizontal scroll для завершения primary operator actions.

Secondary tabular diagnostics МОГУТ (MAY) использовать controlled internal overflow, если это не мешает primary inspect/revise/deactivate path.

#### Scenario: Mobile drawer остаётся usable без clipping primary actions
- **GIVEN** оператор открыл `/pools/binding-profiles` на narrow viewport
- **WHEN** он открывает detail выбранного profile
- **THEN** primary actions и summary fields полностью доступны внутри viewport
- **AND** inspect/revise/deactivate flow не требует hidden horizontal scrolling для завершения основных действий

#### Scenario: Catalog selection остаётся touch-safe
- **GIVEN** оператор выбирает reusable profile из catalog на touch device
- **WHEN** он нажимает primary selection control
- **THEN** control остаётся semantic button с достаточно крупной hit area для уверенного выбора
- **AND** выбор profile не зависит только от узкой текстовой зоны внутри строки
