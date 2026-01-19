## ADDED Requirements

### Requirement: Extensions Action Catalog Runtime Setting
The system SHALL store an extensions action catalog in RuntimeSetting key `ui.action_catalog`.

#### Scenario: Missing catalog returns empty
- **WHEN** `ui.action_catalog` is not configured
- **THEN** the system returns an empty extensions action catalog

#### Scenario: Valid catalog is available
- **WHEN** a valid action catalog is configured in `ui.action_catalog`
- **THEN** the system returns the configured extensions actions and executor bindings

### Requirement: Effective Action Catalog API
The system SHALL expose an API endpoint that returns the effective action catalog for the current user.

#### Scenario: User receives only allowed actions
- **WHEN** a user requests the action catalog
- **THEN** the response omits actions that the user is not allowed to see or execute

### Requirement: Action Executors
The system SHALL support action executors `ibcmd_cli`, `designer_cli`, and `workflow` in the action catalog.

#### Scenario: ibcmd_cli action maps to execute-ibcmd-cli
- **WHEN** an action uses executor `ibcmd_cli`
- **THEN** it can be executed using `POST /api/v2/operations/execute-ibcmd-cli/` with the mapped fields

#### Scenario: workflow action maps to execute-workflow
- **WHEN** an action uses executor `workflow`
- **THEN** it can be executed using `POST /api/v2/workflows/execute-workflow/` with the mapped `workflow_id` and `input_context`

### Requirement: Deactivate and Delete Are Distinct
The system SHALL model deactivation and deletion of an extension as separate actions with separate semantics.

#### Scenario: Deactivate does not delete
- **WHEN** the operator runs the deactivate action for extension `X`
- **THEN** extension `X` remains present and only its active flag changes

#### Scenario: Delete removes extension
- **WHEN** the operator runs the delete action for extension `X` and confirms a dangerous operation
- **THEN** extension `X` is removed from the infobase

### Requirement: Bulk Execution
The system SHALL support executing extensions actions for one database or for a list of databases (bulk).

#### Scenario: Bulk creates per-database tasks
- **WHEN** the operator runs a per-database action for N databases
- **THEN** a single batch operation is created with N tasks

### Requirement: Fail-Closed Validation
The system SHALL validate action catalog entries against available driver catalogs and workflows and MUST fail closed for invalid references.

#### Scenario: Unknown command is filtered out
- **WHEN** an action references a `command_id` not present in the effective driver catalog
- **THEN** the action is omitted from the effective action catalog

#### Scenario: Dangerous commands are hidden for non-staff
- **WHEN** an action resolves to a dangerous command and the user is not staff
- **THEN** the action is omitted from the effective action catalog

### Requirement: Extensions Snapshot in Postgres
The system SHALL persist the latest known extensions snapshot per database in Postgres.

#### Scenario: Snapshot updated after successful sync
- **WHEN** the configured extensions sync action completes successfully for a database
- **THEN** the extensions snapshot record for that database is upserted with the latest data

