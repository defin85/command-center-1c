## Context
Review по `refactor-12-workflow-centric-analyst-modeling` подтвердил, что базовый workflow-centric path уже собран end-to-end, но выявил остаточные архитектурные риски:
- binding API уже first-class по surface, но не до конца first-class по persistence;
- public create-run boundary остаётся более permissive, чем default operator contract;
- pinned subworkflow semantics в authoring model сильнее, чем в runtime contract;
- compatibility paths явно существуют, но часть из них ещё недостаточно зафиксирована как shipped UX-policy;
- уровень proof для default operator path нужно поднять с "helper code + отдельные tests" до "обязательный acceptance path".

Это не новый продуктовый capability, а hardening/change-closure phase поверх уже выбранной workflow-centric модели.

## Goals
- Убрать dual source-of-truth для `pool_workflow_binding`.
- Зафиксировать один canonical binding store/table с предсказуемым query shape и optimistic concurrency.
- Перевести legacy `edge.metadata.document_policy` на decision resources + binding refs с контролируемой миграцией backend/frontend.
- Перевести metadata catalog на shared configuration-scoped snapshots для decision/policy authoring вместо strict database-local snapshots.
- Сделать public operator path deterministic и explicit по binding reference.
- Согласовать runtime reusable subworkflows с pinned authoring semantics.
- Зафиксировать compatibility surfaces как осознанный migration path, а не как неявный рекомендуемый flow.
- Поднять proof level для default shipped path через contracts, docs и acceptance coverage.

## Non-Goals
- Не менять базовую `workflow + decision + binding -> runtime projection` модель.
- Не открывать новый analyst/domain capability поверх service automation.
- Не убирать все legacy compatibility representations в одном шаге, если они нужны для controlled migration/history read.

## Decisions
### Decision 1: Canonical binding persistence становится отдельным store/table
`pool_workflow_binding` должен иметь отдельный persistent store/resource/table и единый canonical read/write path.

Канонический binding store ДОЛЖЕН быть зафиксирован как:
- indexed scalar columns: `pool_id`, `status`, `effective_from`, `effective_to`, `direction`, `mode`;
- workflow reference fields: `workflow_definition_id`, `workflow_revision`;
- JSON fields: `decisions`, `parameters`, `role_mapping`;
- service fields: `revision`, `created_by`, `updated_by`, `created_at`, `updated_at`.

`pool.metadata["workflow_bindings"]` может участвовать только в controlled migration/import, но не должен оставаться runtime source-of-truth после cutover этого change.

`lineage snapshot` binding state НЕ ДОЛЖЕН (SHALL NOT) храниться как mutable часть canonical binding row. Snapshot фиксируется на `PoolRun`/execution record в момент preview/create-run для детерминированного inspect/read-model.

### Decision 2: Binding CRUD использует server-managed revision
Mutating contract для `pool_workflow_binding` использует server-managed `revision` как обязательный optimistic concurrency token.

Read contract обязан возвращать актуальный `revision`, а update/delete/preview mutating flows обязаны отклонять stale requests machine-readable conflict ответом вместо silent last-write-wins.

### Decision 3: Public operator boundary требует explicit binding ref
Default operator-facing create-run и preview path должны требовать `pool_workflow_binding_id`.

Selector-based matching допустим только как assistive UX-mechanism:
- preselect в UI, если найден ровно один кандидат;
- advisory diagnostics до submit.

Но public request boundary не должен silently полагаться на selector fallback.

### Decision 4: Pinned subworkflow runtime следует pinned authoring contract
Если analyst-facing workflow сохраняет `subworkflow_ref(binding_mode="pinned_revision")`, runtime обязан исполнять именно эту pinned revision.

Legacy `subworkflow_id` может оставаться compatibility field для read-path/history, но не должен silently override pinned metadata на runtime path.

### Decision 5: Legacy edge document_policy мигрируется в decision resources + binding refs
Workflow-centric `document_policy` после cutover должен authorиться через versioned decision resources и pinned `pool_workflow_binding.decisions`, а не через primary editing `edge.metadata.document_policy`.

Backend migration path ДОЛЖЕН:
- детерминированно materialize legacy `edge.metadata.document_policy` в decision resource revision, который выдаёт совместимый `document_policy` output;
- записывать provenance `legacy edge -> decision resource revision -> binding ref`;
- обновлять affected `pool_workflow_binding` так, чтобы runtime preview/create-run использовали migrated decision refs;
- допускать дедупликацию identical policy payload только если provenance и remediation report остаются явными.

Frontend replacement path ДОЛЖЕН:
- предоставить first-class decision-resource lifecycle surface на route `/decisions` для `document_policy.v1`, включая `list/detail/create/revise/archive-deactivate`;
- позволять импорт legacy edge policy в decision resource и pin resulting decision revision в binding без ручного API-клиента;
- убрать raw edge policy editing из default net-new authoring path после поставки replacement UI.

`/workflows` остаётся primary composition surface и использует `/templates` как catalog atomic operations и `/decisions` как catalog/version lifecycle decision resources. `/workflows` НЕ ДОЛЖЕН (SHALL NOT) подменять собой полноценный CRUD decision resources.

### Decision 6: Metadata snapshots становятся shared configuration-scoped artifacts
Новый `document_policy` authoring и validation path НЕ ДОЛЖЕН (SHALL NOT) трактовать metadata snapshot как database-local source-of-truth, если несколько ИБ публикуют одинаковую конфигурацию и одинаковую OData metadata surface.

Canonical metadata snapshot registry ДОЛЖЕН:
- использовать configuration scope/signature вместо `database_id` как primary reuse boundary;
- включать как минимум `config_name`, `config_version`, `extensions_fingerprint` и нормализованный `metadata_hash` или эквивалентный publication-surface fingerprint;
- разрешать reuse одного canonical snapshot между несколькими ИБ только когда normalized metadata payload совпадает;
- НЕ ДОЛЖЕН (SHALL NOT) предполагать, что одинаковый `config_version` сам по себе гарантирует одинаковую published OData surface.

Для этого change configuration-scoped identity ДОЛЖНА трактоваться как `configuration profile`, а не как "любая ИБ той же версии". Один и тот же `config_version` МОЖЕТ (MAY) резолвиться в разные canonical snapshots, если:
- состав published OData objects различается из-за `SetStandardODataInterfaceContent` или эквивалентной публикационной настройки;
- extensions/applicability state изменяет effective metadata surface;
- normalized metadata payload после refresh не совпадает.

Migration/cutover ДОЛЖЕН:
- backfill'ить существующие database-local snapshots в shared registry с дедупликацией только по configuration profile + normalized metadata payload;
- сохранять provenance о том, какая ИБ последней подтвердила canonical snapshot;
- прекращать использовать `database_id` как часть canonical snapshot identity после cutover.

Database-specific path ДОЛЖЕН оставаться только для:
- auth/mapping resolution;
- live refresh/probe against a concrete infobase;
- provenance о том, какая ИБ последней подтвердила snapshot.

`/decisions` и связанные `document_policy` preview/validation paths ДОЛЖНЫ использовать resolved shared snapshot scope, а не жестко привязанный database-local snapshot.
Каждая versioned decision revision для `document_policy` ДОЛЖНА фиксировать resolved metadata snapshot provenance как часть audit/read-model contract, чтобы compatibility checks, preview и lineage не реконструировались из mutable latest database state.

### Decision 7: Compatibility surfaces должны быть явно промаркированы
Workflow executor templates на `/templates` остаются допустимым compatibility/integration path, но shipped UI обязан явно маркировать их как non-primary path и направлять analyst authoring в `/workflows`.

`/pools/catalog` topology editor остаётся structural metadata surface. Legacy edge `document_policy` editor должен открываться только как explicit compatibility/migration action и не должен оставаться primary surface для новых workflow-centric схем после migration cutover.

### Decision 8: Acceptance proof path является частью hardening contract
Для этого change недостаточно локальных helper/unit checks. Обязателен набор acceptance evidence:
- contracts/generated clients;
- backend integration coverage;
- frontend/browser coverage;
- operator docs/runbook examples;
- migration notes для breaking points.

## Risks / Trade-offs
- Плюс: уменьшается ambiguity и повышается доверие к runtime lineage.
- Плюс: `add-13` получает более надёжный platform baseline.
- Минус: появляется breaking change для внешних create-run/preview клиентов.
- Минус: migration `edge.metadata.document_policy -> decision resource + binding refs` потребует parity между legacy builder и новым decision authoring UX.
- Минус: metadata snapshot reuse потребует аккуратного distinction между truly shared configuration scope и infobase-specific OData publication differences.
- Минус: migration binding storage потребует аккуратного cutover и backfill без долгоживущего dual-write режима.
- Минус: stricter subworkflow runtime может вскрыть существующие compatibility payloads, которые раньше проходили случайно.

## Migration Plan
1. Ввести dedicated binding persistence/table и backfill/import из legacy metadata store.
2. Ввести shared configuration-scoped metadata snapshot registry, backfill existing database-local snapshots и database-to-snapshot provenance, чтобы identical metadata payloads переиспользовали один canonical snapshot across infobases.
3. Материализовать legacy `edge.metadata.document_policy` в decision resources и pin affected binding refs с migration report/provenance.
4. Перевести binding CRUD, preview/create-run resolution и read-model на новый canonical store.
5. Зафиксировать `revision`-based conflict-safe mutating contract и Problem Details ошибки.
6. Поставить frontend `/decisions` authoring/import UX на shared metadata snapshots, показывать metadata snapshot provenance в decision lifecycle UI и перевести `/pools/catalog` edge policy editor в explicit compatibility/migration mode.
7. Обновить public contracts и generated clients под mandatory `pool_workflow_binding_id`.
8. Дожать runtime subworkflow resolution и fail-closed diagnostics.
9. Обновить `/templates` compatibility marker, operator docs, release notes и cutover runbook.
10. Подтвердить acceptance coverage и только затем завершить tenant-scoped cutover без post-cutover metadata runtime fallback.
