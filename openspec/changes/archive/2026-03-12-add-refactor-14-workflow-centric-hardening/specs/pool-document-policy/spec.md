## MODIFIED Requirements
### Requirement: Legacy edge document policy MUST мигрировать в decision resources и binding refs
Система ДОЛЖНА (SHALL) предоставлять deterministic migration path `edge.metadata.document_policy -> decision resource + pool_workflow_binding.decisions` для workflow-centric source-of-truth.

Migration path ДОЛЖЕН (SHALL):
- materialize versioned decision resource revision, который возвращает совместимый `document_policy.v1`;
- сохранять provenance от legacy topology edge к resulting decision revision и affected binding refs;
- позволять backend backfill/import и operator-driven frontend migration использовать один и тот же deterministic contract;
- не требовать ручного внешнего API-клиента как обязательного шага migration для штатного UI flow.

#### Scenario: Backend backfill materializes legacy edge policy в decision resource
- **GIVEN** topology edge содержит валидный `edge.metadata.document_policy`
- **AND** для пула уже существуют workflow-centric bindings
- **WHEN** backend migration/backfill запускается для этого pool
- **THEN** система создаёт или резолвит versioned decision resource revision с эквивалентным `document_policy.v1`
- **AND** affected bindings получают pinned decision refs на resulting revision
- **AND** migration report фиксирует source edge и target decision/binding provenance

#### Scenario: Frontend migration flow переносит legacy edge policy без потери compiled parity
- **GIVEN** оператор открыл explicit compatibility action для legacy edge policy
- **WHEN** он подтверждает import в decision-resource surface
- **THEN** UI показывает resulting decision revision и updated binding refs
- **AND** binding preview подтверждает compiled `document_policy` parity для migrated path

### Requirement: Net-new document policy authoring MUST использовать decision-resource surface
Система ДОЛЖНА (SHALL) предоставлять frontend surface на отдельном route `/decisions` для net-new `document_policy.v1` authoring через decision resources, а не через direct topology-edge editing как primary path.

Decision-resource authoring surface ДОЛЖЕН (SHALL):
- предоставлять lifecycle `list/detail/create/revise/archive-deactivate` для policy-bearing decision resources;
- предоставлять structured builder для chain/documents/field_mapping/table_parts_mapping/link_rules;
- поддерживать optional raw JSON fallback без потери валидного `document_policy.v1`;
- использовать shared configuration-scoped metadata snapshots для metadata-aware validation и preview до pin в binding;
- выдавать versioned decision revision, пригодный для first-class selection в workflow/binding editor.

#### Scenario: Новый document policy authorится без topology edge editor
- **GIVEN** аналитик создаёт новую workflow-centric схему
- **WHEN** он настраивает document rules для публикации через `/decisions`
- **THEN** policy authorится в decision-resource surface
- **AND** resulting decision revision pin-ится в workflow/binding без direct edge authoring как primary path

### Requirement: Document policy authoring MUST использовать configuration-scoped metadata snapshots
Система ДОЛЖНА (SHALL) валидировать и preview'ить новый `document_policy` против canonical metadata snapshot, разделяемого между ИБ с совместимой configuration signature.

Система НЕ ДОЛЖНА (SHALL NOT) требовать отдельный database-local snapshot для каждого policy, если compatible canonical snapshot уже существует.

Система НЕ ДОЛЖНА (SHALL NOT) silently reuse snapshot только по совпадению `config_version`, если metadata surface differs.

Каждая versioned decision revision, materializing `document_policy`, ДОЛЖНА (SHALL) сохранять resolved metadata snapshot provenance/compatibility markers, чтобы builder, preview и binding selection использовали один и тот же auditable configuration-scoped context.

#### Scenario: Policy builder переиспользует shared metadata snapshot для другой ИБ той же конфигурации
- **GIVEN** canonical metadata snapshot уже существует для configuration signature
- **AND** оператор или аналитик выбирает другую ИБ с той же configuration signature
- **WHEN** открывается builder или preview в `/decisions`
- **THEN** UI/backend используют тот же canonical metadata snapshot
- **AND** не требуют отдельный manual refresh только из-за другого `database_id`

#### Scenario: Diverged metadata surface блокирует reuse в policy builder
- **GIVEN** выбранная ИБ имеет ту же `config_version`, но другой published metadata payload
- **WHEN** система пытается резолвить metadata snapshot для `/decisions`
- **THEN** reuse чужого canonical snapshot не происходит
- **AND** UI получает новый resolved snapshot scope или fail-closed indication о несовместимой metadata surface

#### Scenario: Decision revision сохраняет metadata snapshot provenance
- **GIVEN** аналитик сохраняет новый `document_policy` через `/decisions`
- **WHEN** backend публикует resulting decision revision
- **THEN** revision сохраняет resolved configuration-scoped metadata snapshot markers
- **AND** последующий preview/binding selection использует эти же markers для compatibility/audit
