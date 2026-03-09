## 0. Contract Freeze
- [ ] 0.1 Зафиксировать execution matrix по review findings: `binding persistence`, `public run boundary`, `pinned subworkflow runtime`, `templates compatibility surface`, `acceptance proof path`.
- [ ] 0.2 Подтвердить sequencing: change должен укреплять platform base для `add-13-service-workflow-automation`, а не дублировать его domain scope.

## 1. Pool Workflow Binding Persistence
- [ ] 1.1 Спроектировать dedicated canonical persistence/store для `pool_workflow_binding`.
- [ ] 1.2 Спроектировать migration из `pool.metadata["workflow_bindings"]` без runtime dual source-of-truth.
- [ ] 1.3 Зафиксировать list/detail/upsert/delete/read-model/runtime resolution через один и тот же canonical binding store.
- [ ] 1.4 Зафиксировать conflict-safe mutating semantics и audit expectations для binding CRUD.

## 2. Public Run Contract Hardening
- [ ] 2.1 Изменить public create-run и binding preview contract так, чтобы explicit `pool_workflow_binding_id` был обязательным.
- [ ] 2.2 Зафиксировать, что selector matching может использоваться только для prefill/assistive UX до submit, но не как скрытый public runtime fallback.
- [ ] 2.3 Обновить idempotency/migration notes для внешних клиентов и operator runbook.

## 3. Pinned Subworkflow Runtime
- [ ] 3.1 Зафиксировать runtime resolution subworkflow через `subworkflow_ref(binding_mode="pinned_revision")`.
- [ ] 3.2 Зафиксировать fail-closed поведение при missing/drifted/conflicting pinned metadata.
- [ ] 3.3 Зафиксировать lineage/read-model contract для pinned subworkflow revision.

## 4. Compatibility Surface Hardening
- [ ] 4.1 Зафиксировать `/templates` workflow executor templates как compatibility/integration path с обязательной shipped маркировкой.
- [ ] 4.2 Зафиксировать, что default analyst composition остаётся anchored в `/workflows`, а compatibility constructs не становятся silently recommended path.
- [ ] 4.3 Зафиксировать, что `/pools/catalog` редактирует bindings через isolated first-class workspace и не пишет canonical binding payload через pool upsert.

## 5. Validation
- [ ] 5.1 Обновить OpenAPI/contracts/generated clients для binding persistence и explicit create-run boundary.
- [ ] 5.2 Добавить backend integration coverage для migration path, explicit binding requirement и pinned subworkflow runtime.
- [ ] 5.3 Добавить frontend/browser acceptance coverage для `/templates`, `/pools/catalog` и `/pools/runs` shipped flow.
- [ ] 5.4 Обновить operator-facing runbook/release notes/cutover notes под новый hardened contract.
- [ ] 5.5 Провести `openspec validate refactor-14-workflow-centric-hardening --strict --no-interactive`.
