## MODIFIED Requirements

### Requirement: Reusable execution packs MUST быть tenant-scoped reusable versioned resources
Система ДОЛЖНА (SHALL) трактовать текущую capability reusable `binding_profile` / `binding_profile_revision` как reusable execution-pack catalog.

Primary operator/domain термином для этой capability ДОЛЖЕН (SHALL) быть `Execution Pack`.

Execution-pack revision ДОЛЖНА (SHALL) хранить reusable executable contract:
- pinned workflow revision;
- decision refs, реализующие named slot implementations;
- default parameters;
- role mapping;
- revision metadata/provenance.

Execution-pack revision НЕ ДОЛЖНА (SHALL NOT) считаться owner-ом topology shape или structural slot namespace.

Immutable opaque revision id ДОЛЖЕН (SHALL) оставаться authoritative runtime pin, даже если storage/model alias временно продолжает использовать `binding_profile_revision_id`.

#### Scenario: Один execution pack используется несколькими pool attachment-ами
- **GIVEN** аналитик создал reusable execution pack revision
- **WHEN** оператор attach'ит эту revision к нескольким pool
- **THEN** все attachment-ы используют одну и ту же reusable execution-pack revision
- **AND** pool-local activation state остаётся независимым

#### Scenario: Operator-facing catalog использует термин Execution Pack
- **GIVEN** аналитик или оператор открывает reusable catalog surface
- **WHEN** UI рендерит list/detail/create/revise flows
- **THEN** основная operator-facing терминология использует `Execution Pack`
- **AND** legacy термин `Binding Profile` может оставаться только как transitional compatibility alias

### Requirement: Execution pack catalog MUST использовать dedicated catalog surface и staged route migration
Система ДОЛЖНА (SHALL) предоставлять dedicated catalog surface для list/detail/create/revise/deactivate reusable execution packs.

Primary operator-facing route для этого catalog ДОЛЖЕН (SHALL) быть `/pools/execution-packs`.

Legacy route `/pools/binding-profiles` МОЖЕТ (MAY) временно существовать как redirect или compatibility alias, но НЕ ДОЛЖЕН (SHALL NOT) оставаться единственным primary operator-facing route после rollout этого change.

#### Scenario: Оператор открывает reusable execution logic catalog по новому route
- **WHEN** пользователь открывает `/pools/execution-packs`
- **THEN** UI показывает catalog reusable execution packs
- **AND** create/revise/deactivate flows доступны на этом route как primary path

#### Scenario: Legacy route остаётся только compatibility path
- **GIVEN** в системе ещё существуют ссылки на `/pools/binding-profiles`
- **WHEN** оператор открывает legacy route
- **THEN** система перенаправляет его или отображает совместимый alias surface
- **AND** primary navigation и operator-facing copy указывают на `/pools/execution-packs`

### Requirement: Execution pack authoring MUST реализовывать external structural slots, а не определять их
Execution-pack authoring ДОЛЖЕН (SHALL) использовать `slot_key` как ключ executable implementation для external structural slot contract.

Structural slot namespace ДОЛЖЕН (SHALL) считаться внешним по отношению к execution pack catalog и приходить из topology-template layer или materialized concrete topology contract.

Execution pack НЕ ДОЛЖЕН (SHALL NOT) быть доменным owner-ом structural slot namespace.

#### Scenario: Execution pack реализует topology-defined slots
- **GIVEN** topology-template contract определяет structural slots `sale`, `multi`, `receipt`
- **WHEN** аналитик author'ит execution pack
- **THEN** он pin-ит decision revisions для этих `slot_key`
- **AND** resulting execution pack описывает executable implementations, а не topology shape

#### Scenario: Execution pack не вводит новый structural slot молча
- **GIVEN** execution pack содержит implementation для slot `custom_slot`
- **AND** selected topology contract не содержит такого structural slot
- **WHEN** система выполняет compatibility validation
- **THEN** execution pack не считается автоматически совместимым
- **AND** требуется явная remediation или другая topology/template contract
