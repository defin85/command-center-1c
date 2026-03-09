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
- Сделать public operator path deterministic и explicit по binding reference.
- Согласовать runtime reusable subworkflows с pinned authoring semantics.
- Зафиксировать compatibility surfaces как осознанный migration path, а не как неявный рекомендуемый flow.
- Поднять proof level для default shipped path через contracts, docs и acceptance coverage.

## Non-Goals
- Не менять базовую `workflow + decision + binding -> runtime projection` модель.
- Не открывать новый analyst/domain capability поверх service automation.
- Не убирать все legacy compatibility representations в одном шаге, если они нужны для controlled migration/history read.

## Decisions
### Decision 1: Canonical binding persistence становится отдельным store
`pool_workflow_binding` должен иметь отдельный persistent store/resource и единый canonical read/write path.

`pool.metadata["workflow_bindings"]` может участвовать только в controlled migration/import, но не должен оставаться runtime source-of-truth после cutover этого change.

### Decision 2: Public operator boundary требует explicit binding ref
Default operator-facing create-run и preview path должны требовать `pool_workflow_binding_id`.

Selector-based matching допустим только как assistive UX-mechanism:
- preselect в UI, если найден ровно один кандидат;
- advisory diagnostics до submit.

Но public request boundary не должен silently полагаться на selector fallback.

### Decision 3: Pinned subworkflow runtime следует pinned authoring contract
Если analyst-facing workflow сохраняет `subworkflow_ref(binding_mode="pinned_revision")`, runtime обязан исполнять именно эту pinned revision.

Legacy `subworkflow_id` может оставаться compatibility field для read-path/history, но не должен silently override pinned metadata на runtime path.

### Decision 4: Compatibility surfaces должны быть явно промаркированы
Workflow executor templates на `/templates` остаются допустимым compatibility/integration path, но shipped UI обязан явно маркировать их как non-primary path и направлять analyst authoring в `/workflows`.

### Decision 5: Acceptance proof path является частью hardening contract
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
- Минус: migration binding storage потребует аккуратного cutover и backfill.
- Минус: stricter subworkflow runtime может вскрыть существующие compatibility payloads, которые раньше проходили случайно.

## Migration Plan
1. Ввести dedicated binding persistence и backfill/import из legacy metadata store.
2. Перевести binding CRUD, create-run resolution и read-model на новый canonical store.
3. Обновить public contracts и generated clients под mandatory `pool_workflow_binding_id`.
4. Дожать runtime subworkflow resolution и fail-closed diagnostics.
5. Обновить `/templates` compatibility marker, operator docs и release notes.
6. Подтвердить change acceptance coverage и только затем использовать новый contract как baseline для follow-up changes.

## Open Questions
- Нужен ли отдельный public version/token для optimistic concurrency binding CRUD, или достаточно server-managed revision field в каноническом binding resource.
