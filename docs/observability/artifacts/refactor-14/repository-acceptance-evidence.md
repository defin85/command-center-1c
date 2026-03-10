# refactor-14 repository acceptance evidence

This file is the checked-in repository acceptance evidence for the shipped default path of
`add-refactor-14-workflow-centric-hardening`.

It proves repository-local acceptance through source code, contracts, tests, and shipped docs.
It is not a tenant-specific production rollout log.

Tenant-scoped live cutover evidence belongs in the `*.template.json` files in this directory.

## Default shipped path evidence

- Explicit binding is mandatory for `POST /api/v2/pools/runs/`.
  Code: `orchestrator/apps/api_v2/views/intercompany_pools.py`, `orchestrator/apps/intercompany_pools/workflow_runtime.py`
  Tests: `orchestrator/apps/api_v2/tests/test_intercompany_pool_runs.py`, `frontend/src/pages/Pools/__tests__/PoolRunsPage.test.tsx`
- Explicit binding is mandatory for `POST /api/v2/pools/workflow-bindings/preview/`.
  Code: `orchestrator/apps/api_v2/views/intercompany_pools.py`, `orchestrator/apps/intercompany_pools/binding_preview.py`
  Tests: `orchestrator/apps/api_v2/tests/test_intercompany_pool_runs.py`, `frontend/src/pages/Pools/__tests__/PoolRunsPage.test.tsx`
- Canonical binding CRUD/read-model uses a dedicated store with revision-safe mutating contract.
  Code: `orchestrator/apps/intercompany_pools/workflow_bindings_store.py`, `orchestrator/apps/api_v2/views/intercompany_pools.py`
  Tests: `orchestrator/apps/api_v2/tests/test_intercompany_pool_runs.py`, `orchestrator/apps/api_v2/tests/test_pool_workflow_bindings_src_contract.py`
- `/decisions` is the primary `document_policy` lifecycle surface on shared metadata snapshots.
  Code: `orchestrator/apps/api_v2/views/decisions.py`, `orchestrator/apps/intercompany_pools/metadata_catalog.py`
  Tests: `orchestrator/apps/api_v2/tests/test_decision_tables_api.py`, `orchestrator/apps/intercompany_pools/tests/test_metadata_catalog.py`
- Legacy `edge.metadata.document_policy` migrates to decision revisions plus binding refs on the default path.
  Code: `orchestrator/apps/api_v2/views/pool_document_policy_migrations.py`
  Tests: `orchestrator/apps/api_v2/tests/test_intercompany_pool_runs.py`
- Pinned subworkflow execution stays on the pinned revision and fails closed on drift/mismatch.
  Code: `orchestrator/apps/templates/workflow/schema.py`, `orchestrator/apps/templates/workflow/handlers/factory.py`, `orchestrator/apps/templates/workflow/handlers/subworkflow.py`
  Tests: `orchestrator/apps/templates/workflow/tests/test_handlers_advanced.py`, `orchestrator/apps/api_v2/tests/test_workflows_binding_policy.py`, `frontend/src/components/workflow/__tests__/PropertyEditor.test.tsx`, `frontend/tests/browser/workflow-io-editor.spec.ts`
- `/templates` stays a compatibility catalog while `/workflows` remains the primary analyst authoring surface.
  Code: `frontend/src/pages/Templates/TemplatesPage.tsx`, `frontend/src/pages/Workflows/WorkflowDesigner.tsx`
  Tests: `frontend/tests/browser/workflow-hardening-acceptance.spec.ts`, `orchestrator/apps/api_v2/tests/test_workflow_authoring_phase_api.py`

## Repository docs parity

- Runbook: `docs/observability/WORKFLOW_CENTRIC_POOLS_RUNBOOK.md`
- Release notes: `docs/release-notes/2026-03-10-workflow-centric-hardening-cutover.md`
- Cutover notes: `openspec/changes/add-refactor-14-workflow-centric-hardening/cutover.md`
- Docs parity test: `orchestrator/apps/api_v2/tests/test_workflow_centric_hardening_docs_parity.py`
