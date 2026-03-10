# pool-document-policy Specification

## Purpose
TBD - created by archiving change add-02-pool-document-policy. Update Purpose after archive.
## Requirements
### Requirement: Document policy MUST быть декларативным и пользовательски управляемым в tenant scope
Система ДОЛЖНА (SHALL) поддерживать versioned domain contract `document_policy.v1` как concrete compiled runtime contract, используемый downstream publication/runtime слоями.

После workflow-centric cutover analyst-facing source-of-truth для document rules ДОЛЖЕН (SHALL) формироваться через:
- workflow definitions;
- decision resources;
- pool workflow bindings.

Direct authoring `document_policy` на pool topology edges НЕ ДОЛЖЕН (SHALL NOT) оставаться primary путем моделирования для новых analyst-facing схем.

Система МОЖЕТ (MAY) сохранять compiled `document_policy.v1` в runtime projection, включая metadata/read-model структуры, если это нужно для compatibility, preview, audit и downstream compile.

#### Scenario: Workflow binding компилируется в concrete document policy
- **GIVEN** аналитик настроил workflow definition, decisions и pool binding
- **WHEN** система строит effective runtime projection для запуска
- **THEN** формируется concrete `document_policy.v1`
- **AND** downstream runtime использует именно этот compiled contract, а не raw analyst authoring objects

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
Система ДОЛЖНА (SHALL) компилировать `document_plan_artifact` детерминированно из active topology version за период run, distribution artifact run и `document_policy`.

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

#### Scenario: Одинаковый вход и policy дают идентичный document plan artifact
- **GIVEN** одинаковые distribution artifact, topology version и document-policy
- **WHEN** runtime выполняет compile document plan повторно
- **THEN** структура и порядок `document_plan_artifact` совпадают
- **AND** idempotency ключи документов совпадают

#### Scenario: Неполный document plan artifact блокирует публикацию
- **GIVEN** runtime сформировал artifact без одного из обязательных полей `document_plan_artifact.v1`
- **WHEN** выполняется pre-publication gate
- **THEN** run завершается fail-closed до OData side effects
- **AND** diagnostics содержит machine-readable код нарушения artifact-контракта

### Requirement: Document plan artifact MUST быть downstream execution-контрактом для атомарного workflow compile
Система ДОЛЖНА (SHALL) публиковать versioned `document_plan_artifact` как downstream input-контракт для атомарного workflow compiler.

Система НЕ ДОЛЖНА (SHALL NOT) требовать повторного compile policy на этапе атомарного execution graph compile.

#### Scenario: Atomic workflow compiler получает готовый document plan artifact
- **GIVEN** `document_plan_artifact.v1` сохранён после compile policy
- **WHEN** downstream runtime компилирует атомарный workflow graph
- **THEN** compiler использует сохранённый artifact без повторной policy-компиляции
- **AND** шаги документа/счёт-фактуры соответствуют сохранённому плану

### Requirement: Document policy errors MUST быть machine-readable и диагностируемыми
Система ДОЛЖНА (SHALL) возвращать стабильные machine-readable коды для policy-ошибок до OData side effects.

Минимальный набор кодов:
- `POOL_DOCUMENT_POLICY_INVALID`
- `POOL_DOCUMENT_POLICY_CHAIN_INVALID`
- `POOL_DOCUMENT_POLICY_MAPPING_INVALID`
- `POOL_DOCUMENT_POLICY_MISSING_REQUIRED_INVOICE`

#### Scenario: Невалидный mapping policy возвращает стабильный код ошибки
- **GIVEN** policy содержит некорректный mapping реквизита или табличной части
- **WHEN** runtime выполняет policy validation/compile
- **THEN** run останавливается fail-closed до публикации
- **AND** diagnostics содержит machine-readable код `POOL_DOCUMENT_POLICY_MAPPING_INVALID`

#### Scenario: Невалидная структура цепочки возвращает стабильный код ошибки
- **GIVEN** policy содержит некорректную структуру chain (например, duplicate `chain_id` или invalid `invoice_mode`)
- **WHEN** runtime выполняет policy validation/compile
- **THEN** run останавливается fail-closed до публикации
- **AND** diagnostics содержит machine-readable код `POOL_DOCUMENT_POLICY_CHAIN_INVALID`

### Requirement: Migration path MUST быть backward-compatible для run-ов без document policy
Система ДОЛЖНА (SHALL) поддерживать переходный режим, в котором существующие run-ы без `metadata.document_policy` продолжают выполняться по legacy create-run path без policy compile ошибки.

Система НЕ ДОЛЖНА (SHALL NOT) требовать retroactive миграции исторических run-ов или topology версий только для сохранения текущего поведения публикации.

#### Scenario: Legacy run без document policy выполняется без policy compile шага
- **GIVEN** run создан для topology версии, где отсутствует `edge.metadata.document_policy`
- **WHEN** runtime выполняет distribution/reconciliation create-run path
- **THEN** run не завершается ошибкой policy-missing
- **AND** legacy publication payload семантика сохраняется до включения policy

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

#### Scenario: Одинаковый binding и decisions дают одинаковый compiled document policy
- **GIVEN** одинаковые workflow revision, decision revisions, binding parameters и pool context
- **WHEN** система повторно компилирует effective document policy
- **THEN** структура compiled `document_policy.v1` совпадает
- **AND** downstream `document_plan_artifact` получает один и тот же source contract

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

