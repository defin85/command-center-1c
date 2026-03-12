## MODIFIED Requirements
### Requirement: Document policy authoring MUST использовать configuration-scoped metadata snapshots
Система ДОЛЖНА (SHALL) валидировать и preview'ить новый `document_policy` против canonical metadata snapshot, резолвимого для target business configuration identity выбранной ИБ.

Система НЕ ДОЛЖНА (SHALL NOT) требовать отдельный database-local snapshot для каждого policy, если compatible canonical snapshot уже существует для target business configuration identity.

Same-release compatibility и reuse canonical snapshot должны следовать active metadata contract `/decisions`; guided rollover нужен не для same-release publication drift, а для controlled authoring новой revision под другой target release/business identity.

Каждая versioned decision revision, materializing `document_policy`, ДОЛЖНА (SHALL) сохранять resolved metadata snapshot provenance/compatibility markers, чтобы builder, preview и binding selection использовали один и тот же auditable configuration-scoped context.

Guided rollover flow, создающий новую revision из существующей revision под новую ИБ, ДОЛЖЕН (SHALL) использовать source revision только как editable seed и НЕ ДОЛЖЕН (SHALL NOT) обходить validation против target metadata snapshot выбранной ИБ.

#### Scenario: Policy builder переиспользует canonical snapshot для same-release target identity
- **GIVEN** canonical metadata snapshot уже существует для target business configuration identity
- **AND** оператор или аналитик выбирает другую ИБ той же конфигурации и релиза
- **WHEN** открывается builder или preview в `/decisions`
- **THEN** UI/backend используют тот же canonical metadata snapshot
- **AND** не требуют отдельный manual refresh только из-за другого `database_id`

#### Scenario: Revision предыдущего релиза используется как seed для target release
- **GIVEN** source revision опубликована под предыдущий релиз или другую target business identity
- **AND** в `/decisions` выбрана target database с новым release context
- **WHEN** аналитик запускает guided rollover flow
- **THEN** UI/backend резолвят target metadata snapshot для выбранной ИБ
- **AND** source revision используется только как editable seed, а не как уже-compatible target revision

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
