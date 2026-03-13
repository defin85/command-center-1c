## ADDED Requirements
### Requirement: Workflow modeling MUST разделять decision evaluation и branching orchestration
Система ДОЛЖНА (SHALL) вводить analyst-facing `Decision Task` как отдельный workflow node type, который вычисляет pinned `decision_ref`, публикует typed outputs в execution context и НЕ ДОЛЖЕН (SHALL NOT) выбирать outgoing branch напрямую.

Branching ДОЛЖЕН (SHALL) выполняться отдельными analyst-facing gateway node types, использующими explicit `branch edge contract`.

`Decision Task` ДОЛЖЕН (SHALL):
- всегда ссылаться на pinned decision revision;
- поддерживать explicit input/output mapping;
- сохранять auditable decision outputs в runtime context/read-model;
- отделять business outcome от выбора process route.

#### Scenario: Analyst строит route через `Decision Task -> Exclusive Gateway`
- **GIVEN** аналитику нужно выбрать один из нескольких downstream path по результату business rule
- **WHEN** он моделирует workflow на default surface
- **THEN** decision evaluation задаётся отдельным `Decision Task`
- **AND** routing выполняется через отдельный `Exclusive Gateway`
- **AND** workflow definition не кодирует primary branching semantics внутри самого decision task

### Requirement: Legacy `condition` constructs MUST стать compatibility-only после branching-upgrade
Система ДОЛЖНА (SHALL) сохранять исполнимость и inspectability для уже сохранённых workflow, которые используют legacy `condition`-node или raw `edge.condition`, но НЕ ДОЛЖНА (SHALL NOT) оставлять эти конструкции каноническим authoring path на default workflow surface.

Default analyst-facing `/workflows` ДОЛЖЕН (SHALL):
- создавать новые branching-модели через `Decision Task`, `Exclusive Gateway`, `Inclusive Gateway`;
- показывать legacy `condition` и raw `edge.condition` как compatibility-only/read-only construct;
- давать явный migration handoff вместо поощрения дальнейшего редактирования legacy branching logic как primary UX.

#### Scenario: Legacy condition workflow остаётся читаемым, но новый authoring flow использует gateways
- **GIVEN** в системе уже существует workflow с legacy `condition`-node
- **WHEN** аналитик открывает его на default workflow surface
- **THEN** экран показывает узел как compatibility-only construct
- **AND** новый branching authoring предлагается через `Decision Task` и gateway nodes
- **AND** пользователь получает явный migration path вместо продолжения raw-expression authoring как primary mode
