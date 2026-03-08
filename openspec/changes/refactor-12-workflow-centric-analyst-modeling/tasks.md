## 0. Sequencing
- [x] 0.1 Зафиксировать `refactor-12` как prerequisite platform phase для новой workflow-centric authoring model.
- [x] 0.2 Явно исключить из scope этого change перенос reusable service domains (`extensions.*`, `database.ib_user.*`) и отнести их к follow-up `add-13-service-workflow-automation`.

## 1. Domain Model
- [x] 1.1 Определить канонические модели `workflow definition`, `decision_table` и `pool_workflow_binding`, включая revisioning, pinned references и lineage.
- [x] 1.2 Зафиксировать compile boundary `analyst model -> runtime projection -> execution artifacts` без двойного source-of-truth.

## 2. Workflow And Decision Contracts
- [x] 2.1 Спроектировать analyst-friendly workflow notation: domain task types, gateway/decision semantics, subworkflow binding, approval nodes, explicit IO.
- [x] 2.2 Спроектировать decision contract с deterministic evaluation, fail-closed validation и version binding.
- [x] 2.3 Определить, какие текущие low-level workflow constructs остаются публичными, а какие становятся internal/runtime-only.

## 3. Pool Bindings And Runs
- [x] 3.1 Спроектировать API и UI для `pool_workflow_binding`, поддерживающие несколько активных схем на один `pool`.
- [x] 3.2 Перевести create-run contract на binding-based запуск с явным lineage до workflow revision и decision snapshot.
- [x] 3.3 Зафиксировать fail-closed resolution policy для ambiguous bindings и покрыть её acceptance-сценариями.

## 4. Runtime Projection
- [x] 4.1 Спроектировать compile path из `workflow + decision + binding` в concrete `document_policy.v1` и `document_plan_artifact.v1`.
- [x] 4.2 Зафиксировать границы между user-authored workflow definitions и system-managed runtime workflow projections.

## 5. UI And Information Architecture
- [x] 5.1 Перепроектировать `/workflows` как analyst-facing scheme library и убрать из неё generated runtime workflows по умолчанию.
- [x] 5.2 Зафиксировать роль `/templates` как catalog of atomic operations и исключить из неё analyst-facing process composition.
- [x] 5.3 Сохранить `/pools/runs` как primary operator-facing surface для lifecycle, safe commands, retry и diagnostics.

## 6. Validation
- [x] 6.1 Обновить OpenAPI/contracts и generated clients для новых binding/run/workflow/decision surfaces.
- [x] 6.2 Добавить automated coverage: backend unit/integration tests, frontend browser tests, validation tests для workflow/decision/binding compile path.
- [x] 6.3 Подготовить cutover/rollback plan и operator-facing diagnostics для migration на workflow-centric authoring.
