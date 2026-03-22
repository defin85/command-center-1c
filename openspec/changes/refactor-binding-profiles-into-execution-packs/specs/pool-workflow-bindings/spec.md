## MODIFIED Requirements

### Requirement: Pool workflow binding MUST attach reusable execution-pack revisions as pool-local activation layer
Система ДОЛЖНА (SHALL) трактовать `pool_workflow_binding` как versioned attachment между конкретным `pool` и pinned reusable execution-pack revision.

Storage/runtime compatibility layer МОЖЕТ (MAY) временно сохранять identifiers `binding_profile_id`, `binding_profile_revision_id`, но operator-facing semantics attachment-а ДОЛЖНЫ (SHALL) описывать attached execution pack и pinned execution-pack revision.

Attachment НЕ ДОЛЖЕН (SHALL NOT) трактоваться как owner reusable execution logic; он остаётся pool-local activation layer.

#### Scenario: Attachment summary показывает attached execution pack
- **GIVEN** оператор открывает pool binding inspect/preview surface
- **WHEN** UI рендерит reusable execution logic summary
- **THEN** экран показывает attached execution pack и его pinned revision
- **AND** не описывает эту reusable сущность так, будто она владеет structural topology

#### Scenario: Immutable revision pin остаётся runtime identity после rename
- **GIVEN** operator-facing semantics уже используют термин `Execution Pack`
- **WHEN** runtime сохраняет provenance или выполняет preview/create-run
- **THEN** immutable opaque revision id остаётся authoritative pin
- **AND** transitional aliasing field names не меняют воспроизводимость runtime lineage

### Requirement: Binding compatibility MUST проверять execution-pack coverage относительно structural slot contract
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
