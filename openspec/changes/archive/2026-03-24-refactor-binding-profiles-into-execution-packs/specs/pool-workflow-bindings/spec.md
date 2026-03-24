## MODIFIED Requirements

### Requirement: Pool attachment MUST оставаться pool-local activation layer без local logic overrides в MVP
Система ДОЛЖНА (SHALL) трактовать `pool_workflow_binding` как versioned attachment между конкретным `pool` и pinned reusable execution-pack revision.

Operator-facing и shipped attachment semantics ДОЛЖНЫ (SHALL) описывать attached execution pack и pinned execution-pack revision без обязательного compatibility path для historical `binding_profile*` data.

Attachment НЕ ДОЛЖЕН (SHALL NOT) трактоваться как owner reusable execution logic; он остаётся pool-local activation layer.

#### Scenario: Attachment summary показывает attached execution pack
- **GIVEN** оператор открывает pool binding inspect/preview surface
- **WHEN** UI рендерит reusable execution logic summary
- **THEN** экран показывает attached execution pack и его pinned revision
- **AND** не описывает эту reusable сущность так, будто она владеет structural topology

#### Scenario: Runtime lineage не зависит от legacy binding-profile aliases
- **GIVEN** operator-facing semantics уже используют термин `Execution Pack`
- **WHEN** runtime сохраняет provenance или выполняет preview/create-run
- **THEN** immutable opaque revision id остаётся authoritative pin
- **AND** shipped contract не требует compatibility alias для pre-existing `binding_profile*` attachment refs

### Requirement: Pool workflow binding decisions MUST выступать именованными publication slots
Система ДОЛЖНА (SHALL) валидировать reusable execution-pack coverage относительно structural slot contract выбранного pool topology.

Execution pack МОЖЕТ (MAY) реализовывать named slots через decision refs, но НЕ ДОЛЖЕН (SHALL NOT) silently расширять или переопределять structural slot namespace, пришедший из topology-template layer или concrete topology contract.

#### Scenario: Attachment блокируется при несовместимом execution pack coverage
- **GIVEN** structural topology contract требует slots `sale` и `receipt`
- **AND** выбранная execution-pack revision реализует только `sale`
- **WHEN** оператор attach'ит или preview'ит этот binding
- **THEN** система возвращает missing coverage diagnostics
- **AND** несовместимость не маскируется fallback логикой

#### Scenario: Extra execution slot не становится structural slot автоматически
- **GIVEN** execution-pack revision реализует `sale`, `receipt` и `internal_override`
- **AND** structural topology contract не содержит `internal_override`
- **WHEN** система оценивает compatibility attachment-а
- **THEN** extra slot не materialize'ится как новый structural topology slot
- **AND** оператор получает явный compatibility outcome
