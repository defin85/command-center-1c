# Change: Add extensions action catalog in RuntimeSetting

## Why
We need to connect existing Operations + Workflow capabilities to the UI to manage 1C configuration extensions without hardcoding driver/command bindings in the frontend. Operators must be able to configure which drivers/commands/workflows are treated as "extensions management".

## What Changes
- Add a new RuntimeSetting key `ui.action_catalog` that stores a JSON action catalog (initial scope: `extensions` section).
- Add an API endpoint to fetch an effective action catalog for the current user (filtered by RBAC, driver catalogs, and environment).
- Define extension lifecycle actions with separate deactivate vs delete semantics and bulk execution support.
- Persist per-database extensions snapshot in Postgres (supported), updated from configured sync/list actions.
- UI uses existing Streams (Operations SSE) to show live progress and results.

## Impact
- Affected specs: `extensions-action-catalog` (new)
- Affected code (planned): Orchestrator runtime settings + API v2, Frontend extensions UI
- Breaking changes: none (additive)

