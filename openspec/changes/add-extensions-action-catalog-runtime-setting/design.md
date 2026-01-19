## Context
The platform already has:
- Schema-driven driver catalogs (ibcmd/cli) and an execution endpoint for ibcmd: `POST /api/v2/operations/execute-ibcmd-cli/`
- A workflow execution endpoint: `POST /api/v2/workflows/execute-workflow/`
- Bulk semantics for operations (one batch operation, multiple per-database tasks)
- Streams for UI progress (Operations SSE)

Stage 9 (Extensions) requires a UI that can manage extensions lifecycle across 1+ databases while reusing existing operations/workflows and streaming.

## Goals / Non-Goals
- Goals:
  - Avoid hardcoding extension-management command bindings in the frontend.
  - Allow operators to configure which drivers/commands/workflows implement each extensions action.
  - Support both single-database and bulk execution.
  - Keep security enforced by existing RBAC + driver catalog filtering + dangerous-confirm gates.
  - Allow persisting extensions snapshot in Postgres for fast UI reads.
- Non-Goals:
  - Rebuild the driver catalog system or command schema editor.
  - Introduce a new execution engine (Go Worker remains the only engine).
  - Make action catalog a security boundary (execution endpoints still enforce RBAC).

## Decisions
- Store action mappings in DB as a RuntimeSetting:
  - Key: `ui.action_catalog`
  - Value: JSON "action catalog" (v1), with an `extensions` section.
- Expose an "effective" action catalog for the current user:
  - New API endpoint (path TBD): `GET /api/v2/ui/action-catalog/`
  - Filters actions based on:
    - Referenced driver catalog entries (exists, not disabled, visible to user)
    - Referenced workflows (exists, active, valid, executable by user)
    - Environment / role constraints (reusing existing driver catalog filtering rules)
- Action executors supported by the catalog:
  - `ibcmd_cli` -> `POST /api/v2/operations/execute-ibcmd-cli/`
  - `designer_cli` -> `POST /api/v2/operations/execute/` (`operation_type=designer_cli`)
  - `workflow` -> `POST /api/v2/workflows/execute-workflow/`
- Deactivation vs deletion are distinct actions (never merged).
- Bulk semantics:
  - `ibcmd_cli`: pass `database_ids` (per_database) to create N tasks.
  - `workflow`: pass `target_database_ids` (or equivalent) inside `input_context`.

## Action Catalog Schema (v1)
Stored in RuntimeSetting `ui.action_catalog`.

High-level structure:
```json
{
  "catalog_version": 1,
  "extensions": {
    "actions": [
      {
        "id": "extensions.list",
        "label": "List extensions",
        "contexts": ["database_card", "bulk_page"],
        "executor": {
          "kind": "ibcmd_cli",
          "driver": "ibcmd",
          "command_id": "infobase.extension.list",
          "mode": "guided",
          "fixed": {
            "timeout_seconds": 300,
            "confirm_dangerous": false
          }
        }
      }
    ]
  }
}
```

Executor payload mapping rules:
- `ibcmd_cli` executor:
  - `command_id` maps to `ExecuteIbcmdCliOperationRequestSerializer.command_id`
  - `mode`, `params`, `additional_args`, `stdin`, `confirm_dangerous`, `timeout_seconds` map 1:1
  - Target databases come from UI selection (single DB card -> 1 id; bulk -> list)
- `workflow` executor:
  - `workflow_id` maps to `ExecuteWorkflowRequestSerializer.workflow_id`
  - `input_context` is built from UI inputs and MUST include target database ids for bulk

Note: the catalog stores UI metadata (label, contexts) and execution bindings; command parameter schemas are sourced from the driver catalogs (`/api/v2/operations/driver-commands/`).

## Validation / Resolution
- Update-time validation (staff-only update flow):
  - Validate JSON shape and required fields (`catalog_version`, `actions[*].id`, `executor.kind`, etc.)
  - Validate references:
    - `ibcmd_cli`/`designer_cli`: `command_id` MUST exist in the effective driver catalog
    - `workflow`: `workflow_id` MUST exist and be active + valid
- Read-time validation:
  - If stored value is malformed, fail closed (return empty `extensions.actions`) and log diagnostics.
  - If a specific action is invalid (unknown command/workflow), omit it from the effective catalog.

## Snapshot Storage (Postgres)
Optional but supported to improve UI responsiveness:
- New model/table (name TBD): per-database "extensions snapshot"
  - `database_id` (FK)
  - `snapshot` (JSON)
  - `updated_at`
  - `source_operation_id` (optional, for audit)
- Updated after successful completion of the configured "sync/list extensions" action.

## Migration Plan
1) Add RuntimeSetting definition + default empty action catalog.
2) Add API endpoint to return effective action catalog for current user.
3) Add UI:
   - Database card: Extensions tab/panel (single DB)
   - Bulk page: Extensions actions for selected databases
4) Add snapshot persistence + update pipeline.
5) Add tests and docs.

## Open Questions
- Endpoint naming: `GET /api/v2/ui/action-catalog/` vs a resource-scoped endpoint (e.g., `/api/v2/extensions/action-catalog/`).
- Do we also want a backend "execute action by id" endpoint to reduce frontend coupling further?
- Key naming: keep `ui.action_catalog` (multi-domain) vs `ui.extensions.action_catalog` (narrow).
- File references for install/update actions: artifacts (`artifact://<storage_key>`) vs uploaded files (resolve to a shared filesystem path).

