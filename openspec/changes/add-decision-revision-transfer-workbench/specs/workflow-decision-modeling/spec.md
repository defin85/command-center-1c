## ADDED Requirements
### Requirement: `/decisions` MUST provide transfer workbench for concrete decision revisions
Система ДОЛЖНА (SHALL) предоставлять в `/decisions` analyst-facing transfer workbench для создания новой concrete `decision_revision` из существующей source revision под target metadata context, резолвимый из выбранной ИБ.

Transfer workbench ДОЛЖЕН (SHALL):
- использовать source revision только как immutable authoring seed;
- явно показывать `source revision`, `target database`, resolved `configuration profile` и resolved target `metadata snapshot`;
- строить явный transfer report со статусами `matched`, `ambiguous`, `missing` и `incompatible`;
- использовать stable metadata design identifiers из `ConfigDumpInfo.xml`/`ibcmd`-enriched snapshot как primary signal для automatic matches там, где они доступны;
- использовать canonical metadata path/name + type/shape fallback только для items без доступного design-time identifier и НЕ ДОЛЖЕН (SHALL NOT) помечать uncertain fallback matches как `matched`;
- позволять аналитику исправлять unresolved mappings до публикации;
- разрешать использовать revision вне default compatible selection как source template без превращения её в default ready-to-pin candidate;
- публиковать только новую concrete revision и НЕ ДОЛЖЕН (SHALL NOT) вводить abstract revision как runtime/binding artifact;
- НЕ ДОЛЖЕН (SHALL NOT) автоматически перепривязывать существующие workflow definitions, workflow bindings или runtime projections.

#### Scenario: Аналитик выбирает revision вне compatible set как source template
- **GIVEN** source revision не входит в default compatible selection target database
- **WHEN** аналитик открывает transfer workbench из `/decisions`
- **THEN** система позволяет выбрать эту revision как source template
- **AND** UI явно показывает, что revision используется только как источник переноса, а не как ready-to-pin candidate

#### Scenario: Transfer workbench показывает source/target context и report до publish
- **GIVEN** аналитик выбрал source revision и target database
- **WHEN** `/decisions` открывает transfer workbench
- **THEN** экран показывает source revision provenance, target database, resolved configuration profile и target metadata snapshot
- **AND** UI отображает transfer report со статусами `matched`, `ambiguous`, `missing` и `incompatible`

#### Scenario: Transfer workbench использует enriched metadata identity раньше name-based fallback
- **GIVEN** source и target metadata context содержат stable metadata design identifiers для части document-policy references
- **WHEN** backend строит transfer report
- **THEN** automatic matches определяются по этим identifiers в первую очередь
- **AND** canonical path/name + type/shape fallback используется только для items без доступного design-time identifier

#### Scenario: Успешный transfer публикует новую concrete revision без auto-rebind
- **GIVEN** аналитик разрешил все unresolved items в transfer workbench
- **WHEN** он публикует результат переноса
- **THEN** система создаёт новую concrete `decision_revision` с `parent_version_id`, указывающим на source revision
- **AND** existing workflow definitions, workflow bindings и runtime projections остаются pinned на прежние revisions, пока пользователь не обновит их явно
