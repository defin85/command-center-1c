## 0. Contract Freeze
- [x] 0.1 Зафиксировать execution matrix по review findings: `binding persistence`, `public run boundary`, `pinned subworkflow runtime`, `templates compatibility surface`, `acceptance proof path`.
- [x] 0.2 Подтвердить sequencing: change должен укреплять platform base для `add-13-service-workflow-automation`, а не дублировать его domain scope.
- [x] 0.3 Зафиксировать migration contract `edge.metadata.document_policy -> decision resource + binding refs`, включая provenance, replacement UI и deprecation criteria для legacy edge editor.
- [x] 0.4 Зафиксировать metadata snapshot contract: canonical reuse идёт по configuration scope/signature, а не по `database_id`, при этом одинаковый `config_version` без совпавшего metadata payload не считается достаточным условием reuse.

## 1. Pool Workflow Binding Persistence
- [x] 1.1 Спроектировать dedicated canonical persistence/store/table для `pool_workflow_binding` с indexed scalar columns `pool_id`, `status`, `effective_from`, `effective_to`, `direction`, `mode`, JSON fields `decisions`, `parameters`, `role_mapping` и service fields `revision`, `created_by`, `updated_by`, `created_at`, `updated_at`.
- [x] 1.2 Спроектировать migration/import из `pool.metadata["workflow_bindings"]` как legacy source только для backfill/cutover, без post-cutover runtime dual source-of-truth.
- [x] 1.3 Зафиксировать list/detail/upsert/delete/read-model/runtime resolution через один и тот же canonical binding store и запретить post-cutover runtime reads из `pool.metadata["workflow_bindings"]`.
- [x] 1.4 Зафиксировать conflict-safe mutating semantics, где server-managed `revision` обязателен для update/delete и stale requests возвращают machine-readable conflict.

## 2. Public Run Contract Hardening
- [x] 2.1 Изменить public create-run и binding preview contract так, чтобы explicit `pool_workflow_binding_id` был обязательным.
- [x] 2.2 Зафиксировать, что selector matching может использоваться только для prefill/assistive UX до submit, но не как скрытый public runtime fallback.
- [x] 2.3 Зафиксировать, что preview/create-run читают binding только из canonical store и сохраняют binding lineage snapshot на `PoolRun`/execution.
- [x] 2.4 Обновить idempotency/migration notes для внешних клиентов и operator runbook.

## 3. Pinned Subworkflow Runtime
- [x] 3.1 Зафиксировать runtime resolution subworkflow через `subworkflow_ref(binding_mode="pinned_revision")`.
- [x] 3.2 Зафиксировать fail-closed поведение при missing/drifted/conflicting pinned metadata.
- [x] 3.3 Зафиксировать lineage/read-model contract для pinned subworkflow revision и сохранение pinned provenance в run diagnostics.

## 4. Shared Metadata Snapshots
- [x] 4.1 Спроектировать canonical metadata snapshot registry по configuration scope/signature (`config_name`, `config_version`, `extensions_fingerprint`, `metadata_hash` или эквивалент) вместо database-only current snapshot и определить migration/backfill существующих database-local snapshot'ов в shared registry.
- [x] 4.2 Спроектировать database-specific read/refresh/provenance path, где конкретная ИБ остаётся auth/probe source, но может ссылаться на shared canonical snapshot.
- [x] 4.3 Спроектировать, что `/decisions` document_policy authoring, import и validation используют shared configuration-scoped snapshot, а не strict database-local snapshot.
- [x] 4.4 Зафиксировать fail-closed поведение для случая, когда у ИБ совпадает `config_version`, но published OData metadata surface отличается и reuse snapshot невозможен.
- [x] 4.5 Зафиксировать, что каждая decision revision для `document_policy` сохраняет resolved metadata snapshot provenance/compatibility markers и использует их в preview/validation/read-model.

## 5. Legacy Document Policy Migration
- [x] 5.1 Спроектировать backend migration/backfill `edge.metadata.document_policy -> versioned decision resource`, который выдаёт совместимый `document_policy` output и сохраняет provenance `edge -> decision revision`.
- [x] 5.2 Спроектировать update affected `pool_workflow_binding.decisions`, чтобы migrated decision refs стали canonical runtime path для preview/create-run.
- [x] 5.3 Спроектировать frontend decision table lifecycle UI на отдельном route `/decisions` (`list/detail/create/revise/archive-deactivate`) и replacement authoring/import flow для `document_policy.v1`, чтобы новые policies создавались/редактировались через decision-resource surface, а не через topology edge editor.
- [x] 5.4 Зафиксировать, что `/pools/catalog` legacy edge editor становится explicit compatibility/migration action с read-only by default и явным migrate/import outcome.

## 6. Compatibility Surface Hardening
- [x] 6.1 Зафиксировать `/templates` workflow executor templates как compatibility/integration path с обязательной shipped маркировкой.
- [x] 6.2 Зафиксировать, что default analyst composition остаётся anchored в `/workflows`, а compatibility constructs не становятся silently recommended path.
- [x] 6.3 Зафиксировать, что `/pools/catalog` редактирует bindings через isolated first-class workspace, использует тот же canonical CRUD/revision contract и не пишет canonical binding payload через pool upsert.

## 7. Validation
- [x] 7.1 Обновить OpenAPI/contracts/generated clients для binding persistence, `revision`-based mutating contract, shared metadata snapshot surfaces, decision-resource migration surfaces и explicit create-run boundary.
- [x] 7.2 Добавить backend integration coverage для shared metadata snapshot reuse across infobases, backfill database-local snapshots в shared registry, fail-closed divergence при разном published metadata surface, migration path `edge.metadata.document_policy -> decision resource + binding refs`, explicit binding requirement, stale revision conflicts, отсутствия metadata runtime read после cutover и pinned subworkflow runtime.
- [x] 7.3 Добавить frontend/browser acceptance coverage для `/decisions` с shared metadata snapshots, decision table lifecycle UI, metadata snapshot provenance/compatibility markers, decision authoring/import flow, `/templates`, `/pools/catalog` и `/pools/runs` shipped flow.
- [x] 7.4 Обновить operator-facing runbook/release notes/cutover notes под новый hardened contract, включая shared metadata snapshots, backfill, tenant-scoped cutover, decision-resource migration и rollback window.
- [x] 7.5 Провести `openspec validate refactor-14-workflow-centric-hardening --strict --no-interactive`.
