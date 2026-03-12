## MODIFIED Requirements
### Requirement: Document policy authoring MUST использовать configuration-scoped metadata snapshots
Система ДОЛЖНА (SHALL) валидировать и preview'ить новый `document_policy` против canonical metadata snapshot, разделяемого между ИБ с совместимой configuration signature.

Система НЕ ДОЛЖНА (SHALL NOT) требовать отдельный database-local snapshot для каждого policy, если compatible canonical snapshot уже существует.

Система НЕ ДОЛЖНА (SHALL NOT) silently reuse snapshot только по совпадению `config_version`, если metadata surface differs.

Каждая versioned decision revision, materializing `document_policy`, ДОЛЖНА (SHALL) сохранять resolved metadata snapshot provenance/compatibility markers, чтобы builder, preview и binding selection использовали один и тот же auditable configuration-scoped context.

Guided rollover flow, создающий новую revision из существующей revision под новую ИБ, ДОЛЖЕН (SHALL) использовать source revision только как editable seed и НЕ ДОЛЖЕН (SHALL NOT) обходить validation против target metadata snapshot выбранной ИБ.

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

#### Scenario: Старая revision может быть seed для новой revision под target database
- **GIVEN** аналитик выбрал source revision, опубликованную под предыдущий релиз ИБ
- **AND** в `/decisions` выбрана target database с другим resolved metadata snapshot
- **WHEN** аналитик сохраняет новую revision через guided rollover flow
- **THEN** backend валидирует policy source revision против target metadata snapshot выбранной ИБ
- **AND** resulting revision сохраняет target metadata provenance вместо provenance source revision

#### Scenario: Несовместимая source revision блокирует publish новой revision fail-closed
- **GIVEN** source revision содержит field mapping или entity references, отсутствующие в target metadata snapshot
- **WHEN** аналитик пытается опубликовать новую revision под выбранную ИБ
- **THEN** publish отклоняется fail-closed с metadata validation error
- **AND** ни source revision, ни existing pinned consumers не изменяются
