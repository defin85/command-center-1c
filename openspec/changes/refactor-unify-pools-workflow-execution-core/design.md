## Context
Целевой пользовательский поток состоит из трёх типов многошаговых операций:
1. Развёртывание ИБ (cf/dt).
2. Подготовка публикации метаданных через OData.
3. Манипулирование данными в ИБ.

Для этих операций уже существует общий execution/runtime стек (`workflows`, queue, retries, audit, execution plan), а `pools` добавляет предметную область межорганизационного распределения и публикации.

Проблема: если `pools` развивать как отдельный runtime, появляется дублирование lifecycle/retry/audit и divergence в операционном управлении.

## Goals / Non-Goals
- Goals:
  - Единый runtime для всех многошаговых операций над ИБ.
  - `pools` как domain facade/DSL без собственного оркестратора.
  - Прозрачная трассировка `pool run -> workflow run -> step diagnostics`.
- Non-Goals:
  - Big-bang удаление `workflows`.
  - Перепроектирование доменной математики распределения.

## Decisions
- Decision: `workflows` является execution-core для `pools`.
- Decision: `Pool Schema Template` компилируется в workflow-compatible graph (operation nodes + I/O mapping + retry policy).
- Decision: `pools/runs` остаётся доменным API-слоем и хранит reference на workflow run.
- Decision: publication service (OData) исполняется как adapter шага в workflow graph.
- Decision: идемпотентность `pool` домена сохраняется и маппится в workflow metadata/idempotency.
- Decision: удаление `workflows` запрещено до завершения миграции всех runtime consumers.

## Execution Mapping (Target)
- `PoolTemplate` -> compiler -> `WorkflowTemplate`.
- `PoolRun(start)` -> creates/starts `WorkflowRun`.
- Workflow steps:
  - `prepare_input` (source/template validation),
  - `distribution_calculation` (top-down/bottom-up),
  - `publication_odata` (document upsert + posting),
  - `reconciliation_report` (balance checks + artifacts).
- Pool status в API считается как projection поверх workflow step/run states.

## Migration Plan
1. Добавить явные reference поля и адаптер статусов.
2. Перевести create/start path `pools/runs` на workflow runtime.
3. Включить dual-read для historical/legacy run записей.
4. Выполнить backfill `pool_run -> workflow_run`.
5. После стабилизации выключить legacy pool-local execution path.

## Risks / Trade-offs
- Риск: рассинхронизация доменных и runtime статусов.
  - Mitigation: единый status projection contract + контрактные тесты.
- Риск: усложнение отладки при двух id (`pool_run_id`, `workflow_run_id`).
  - Mitigation: обязательный provenance block в API/UI.
- Риск: регрессии retry semantics при переносе публикации в workflow steps.
  - Mitigation: интеграционные тесты на partial_success/retry/retry_failed.

## Open Questions
- Нужен ли отдельный SLA/priority lane для pool-run workload в общей workflow очереди.
- Где хранить canonical mapping pool domain status <-> workflow status (domain service vs shared mapper).
