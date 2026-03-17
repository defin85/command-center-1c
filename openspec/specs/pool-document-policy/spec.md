# pool-document-policy Specification

## Purpose
TBD - created by archiving change add-02-pool-document-policy. Update Purpose after archive.
## Requirements
### Requirement: Document policy MUST быть декларативным и пользовательски управляемым в tenant scope
Система ДОЛЖНА (SHALL) поддерживать versioned domain contract `document_policy.v1` как concrete compiled runtime contract, используемый downstream publication/runtime слоями.

После topology-slot cutover analyst-facing source-of-truth для document rules ДОЛЖЕН (SHALL) формироваться через:
- decision resources;
- pool workflow bindings;
- topology edge selectors `edge.metadata.document_policy_key`.

Direct authoring `document_policy` на pool topology edges НЕ ДОЛЖЕН (SHALL NOT) оставаться primary путем моделирования для новых analyst-facing схем.

Система МОЖЕТ (MAY) сохранять compiled `document_policy.v1` в runtime projection, включая metadata/read-model структуры, если это нужно для compatibility, preview, audit и downstream compile.

#### Scenario: Один binding materialize'ит несколько concrete policy slots
- **GIVEN** аналитик настроил несколько decision resources и pool binding с разными `slot_key`
- **AND** topology использует разные `edge.metadata.document_policy_key` на разных рёбрах
- **WHEN** система строит effective runtime projection для запуска
- **THEN** document rules materialize'ятся через pinned binding decisions и topology selectors
- **AND** downstream runtime использует concrete `document_policy.v1` per edge, а не raw topology authoring payload

### Requirement: Document policy mapping MUST поддерживать реквизиты и табличные части
Система ДОЛЖНА (SHALL) поддерживать в policy явный mapping реквизитов документа (`field_mapping`) и табличных частей (`table_parts_mapping`).

Система НЕ ДОЛЖНА (SHALL NOT) требовать backend hardcode под каждый tenant-вариант заполнения реквизитов/табличных частей, если variant укладывается в policy contract `v1`.

#### Scenario: Policy задаёт заполнение реквизитов и строк табличной части
- **GIVEN** policy содержит mapping реквизитов документа и mapping табличной части
- **WHEN** runtime компилирует документный план
- **THEN** итоговый payload документа включает поля и табличные строки по policy mapping
- **AND** отсутствие required mapping вызывает fail-closed validation error

### Requirement: Document policy MUST поддерживать цепочки документов и обязательную связанную счёт-фактуру
Система ДОЛЖНА (SHALL) поддерживать ordered document chains (`documents[]`) в рамках одного edge rule, включая per-document `entity_name` и link rules между документами цепочки.

Система ДОЛЖНА (SHALL) поддерживать `invoice_mode=required` для policy, где связанная счёт-фактура обязательна.

#### Scenario: Для sale/purchase chain создаются документы и связанная счёт-фактура
- **GIVEN** policy содержит chain с `Реализация` и `invoice_mode=required` для связанной счёт-фактуры
- **WHEN** runtime формирует `document_plan_artifact`
- **THEN** план включает и основной документ, и связанную счёт-фактуру в корректном порядке
- **AND** link rules между документами цепочки зафиксированы в artifact

#### Scenario: Отсутствие required счёт-фактуры блокирует публикацию fail-closed
- **GIVEN** policy требует `invoice_mode=required`
- **AND** по итогам compile отсутствует корректно сформированный invoice step
- **WHEN** runtime выполняет pre-publication gate
- **THEN** publication блокируется
- **AND** возвращается machine-readable код `POOL_DOCUMENT_POLICY_MISSING_REQUIRED_INVOICE`

### Requirement: Runtime MUST строить детерминированный document plan artifact из policy
Система ДОЛЖНА (SHALL) компилировать `document_plan_artifact` детерминированно из active topology version за период run, distribution artifact run и per-edge `document_policy`, резолвимого через `edge.metadata.document_policy_key` и selected binding decisions.

Система ДОЛЖНА (SHALL) использовать этот artifact как source-of-truth для create-run publication и retry semantics.

Минимальный обязательный набор полей `document_plan_artifact.v1`:
- `version`;
- `run_id`;
- `distribution_artifact_ref`;
- `topology_version_ref`;
- `policy_refs[]`;
- `targets[].chains[].documents[]` с `entity_name`, `document_role`, `field_mapping`, `table_parts_mapping`, `link_rules`, `invoice_mode`, `idempotency_key`;
- `compile_summary`.

Система НЕ ДОЛЖНА (SHALL NOT) формировать create-run publication chain напрямую из raw `run_input`, если `document_plan_artifact.v1` успешно построен и сохранён.

#### Scenario: Разные edges одного run получают разные document chains
- **GIVEN** один run содержит два allocation на разных topology edges
- **AND** у edges указаны разные `document_policy_key`
- **AND** selected binding pin-ит matching decisions для обоих slot'ов
- **WHEN** runtime выполняет compile document plan
- **THEN** artifact содержит разные document chains для этих targets/edges
- **AND** каждая chain materialize'ится из matching slot policy

#### Scenario: Отсутствующий slot блокирует document plan compile
- **GIVEN** topology edge участвует в allocation
- **AND** у edge отсутствует `document_policy_key` или binding не содержит matching `slot_key`
- **WHEN** runtime выполняет compile document plan
- **THEN** compile завершается fail-closed до OData side effects
- **AND** diagnostics содержит machine-readable код missing slot resolution

### Requirement: Document plan artifact MUST быть downstream execution-контрактом для атомарного workflow compile
Система ДОЛЖНА (SHALL) публиковать versioned `document_plan_artifact` как downstream input-контракт для атомарного workflow compiler.

Система НЕ ДОЛЖНА (SHALL NOT) требовать повторного compile policy на этапе атомарного execution graph compile.

#### Scenario: Atomic workflow compiler получает готовый document plan artifact
- **GIVEN** `document_plan_artifact.v1` сохранён после compile policy
- **WHEN** downstream runtime компилирует атомарный workflow graph
- **THEN** compiler использует сохранённый artifact без повторной policy-компиляции
- **AND** шаги документа/счёт-фактуры соответствуют сохранённому плану

### Requirement: Document policy slot diagnostics MUST быть machine-readable и стабильными
Система ДОЛЖНА (SHALL) возвращать стабильные machine-readable коды для topology-slot resolution ошибок и remediation state'ов.

Минимальный набор кодов:
- `POOL_DOCUMENT_POLICY_SLOT_SELECTOR_MISSING`
- `POOL_DOCUMENT_POLICY_SLOT_NOT_BOUND`
- `POOL_DOCUMENT_POLICY_SLOT_DUPLICATE`
- `POOL_DOCUMENT_POLICY_SLOT_OUTPUT_INVALID`
- `POOL_DOCUMENT_POLICY_SLOT_COVERAGE_AMBIGUOUS`
- `POOL_DOCUMENT_POLICY_LEGACY_SOURCE_REJECTED`

#### Scenario: Missing selector возвращает стабильный slot error code
- **GIVEN** distribution artifact содержит allocation по edge без `document_policy_key`
- **WHEN** runtime выполняет compile document plan
- **THEN** execution завершается fail-closed
- **AND** diagnostics содержит `POOL_DOCUMENT_POLICY_SLOT_SELECTOR_MISSING`

#### Scenario: Legacy topology dependency после cutover возвращает стабильный code
- **GIVEN** topology или pool по-прежнему зависят от legacy `document_policy`
- **WHEN** shipped preview/run path выполняется после cutover
- **THEN** legacy payload не используется как fallback
- **AND** diagnostics содержит `POOL_DOCUMENT_POLICY_LEGACY_SOURCE_REJECTED`

### Requirement: Legacy topology policy cutover MUST быть phased и наблюдаемым
Система ДОЛЖНА (SHALL) выполнять отказ от legacy topology policy по фазам, а не как silent one-shot switch.

Cutover flow ДОЛЖЕН (SHALL) включать как минимум:
- remediation diagnostics/inventory;
- blocking warnings в operator surfaces;
- blocking preview/create-run для unresolved legacy dependencies;
- явное отключение runtime fallback;
- последующее удаление compatibility UI/code path.

Rollback МОЖЕТ (MAY) существовать только как явный operational mode и НЕ ДОЛЖЕН (SHALL NOT) превращаться в silent per-request fallback к legacy topology policy.

#### Scenario: Legacy dependency сначала видна как remediation backlog
- **GIVEN** pool все еще зависит от legacy `edge.metadata.document_policy` или `pool.metadata.document_policy`
- **WHEN** оператор открывает shipped topology/binding workspace до финального cutover
- **THEN** UI/runtime diagnostics показывают remediation backlog
- **AND** legacy dependency не скрывается behind generic validation error

#### Scenario: После cutover shipped runtime не откатывается в legacy fallback молча
- **GIVEN** финальная стадия cutover включена
- **AND** для pool не завершена remediation
- **WHEN** оператор запускает preview или create-run
- **THEN** shipped path завершается fail-closed
- **AND** legacy fallback не включается автоматически только ради совместимости

### Requirement: Document policy completeness profile MUST задавать обязательные реквизиты и табличные части per entity
Document policy MUST поддерживать декларативный completeness profile для каждого `entity_name`, включая обязательные реквизиты шапки и обязательные табличные части с минимально допустимым количеством строк.

#### Scenario: Неполный mapping блокирует compile document plan fail-closed
- **GIVEN** policy для edge содержит document chain с `entity_name`, требующим completeness profile
- **WHEN** compile path обнаруживает отсутствие обязательного поля или обязательной табличной части
- **THEN** runtime завершает compile fail-closed с machine-readable кодом ошибки
- **AND** публикация не выполняется

### Requirement: Режим `minimal_documents_full_payload` MUST минимизировать число документов без ослабления policy инвариантов
При активном профиле минимизации система MUST сокращать только количество документов, но не MUST удалять обязательные роли документов, обязательные связи и обязательные поля из policy.

#### Scenario: Минимизация не удаляет обязательный документ из цепочки
- **GIVEN** chain policy требует обязательный связанный документ
- **WHEN** включён режим `minimal_documents_full_payload`
- **THEN** compile path сохраняет обязательный документ в chain
- **AND** попытка исключить его приводит к fail-closed ошибке compile

### Requirement: Workflow-centric authoring MUST материализоваться в deterministic document policy до publication compile
Система ДОЛЖНА (SHALL) материализовать workflow-centric authoring в deterministic concrete `document_policy.v1` до построения `document_plan_artifact.v1` и атомарного workflow compile.

Система НЕ ДОЛЖНА (SHALL NOT) выполнять publication compile напрямую из raw workflow/decision authoring без промежуточного concrete policy contract.

Для topology-slot scheme concrete policy resolution ДОЛЖЕН (SHALL) выполняться per edge через `document_policy_key -> binding decision`.

#### Scenario: Один и тот же binding дает одинаковый per-edge policy map
- **GIVEN** одинаковые workflow revision, decision revisions, binding parameters, topology version и pool context
- **WHEN** система повторно компилирует effective per-edge document policy map
- **THEN** структура compiled `document_policy.v1` для каждого slot совпадает
- **AND** downstream `document_plan_artifact` получает один и тот же source contract

### Requirement: Legacy edge document policy MUST мигрировать в decision resources и binding refs
Система ДОЛЖНА (SHALL) предоставлять deterministic migration path `edge.metadata.document_policy -> decision resource + pool_workflow_binding.decisions + edge.metadata.document_policy_key`.

Migration path ДОЛЖЕН (SHALL):
- materialize versioned decision resource revision, который возвращает совместимый `document_policy.v1`;
- сохранять provenance от legacy topology edge к resulting decision revision, slot key и affected binding refs;
- позволять backend backfill/import и operator-driven remediation использовать один и тот же deterministic contract;
- не требовать ручного внешнего API-клиента как обязательного шага migration для штатного remediation flow.

#### Scenario: Backend remediation materializes legacy edge policy в decision resource и topology slot
- **GIVEN** topology edge содержит валидный `edge.metadata.document_policy`
- **AND** для пула уже существуют workflow-centric bindings
- **WHEN** backend migration/backfill запускается для этого pool
- **THEN** система создаёт или резолвит versioned decision resource revision с эквивалентным `document_policy.v1`
- **AND** affected bindings получают pinned decision refs с canonical `decision_key` и явным `slot_key`
- **AND** topology edge получает matching `document_policy_key`
- **AND** migration report фиксирует source edge и target decision/binding provenance

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

