# Frontend query/stream runtime runbook

## Canonical shell/bootstrap path

Shell-level consumers must read session context from:

- `GET /api/v2/system/bootstrap/`

The bootstrap payload is the default source for:

- current user summary
- tenant context
- effective access summary
- shell capability flags

`MainLayout`, `AuthzProvider`, and route guards must not rebuild this context through separate `system/me`, `tenants/list-my-tenants`, RBAC, or command-schema probe calls on the default path.

## Database stream session contract

Database realtime connects through:

1. `POST /api/v2/databases/stream-ticket/`
2. `GET /api/v2/databases/stream/?ticket=...`

Required request fields for the ticket endpoint:

- `client_instance_id`

Optional recovery fields:

- `session_id`
- `recovery`

Success response must include:

- `session_id`
- `lease_id`
- `client_instance_id`
- `scope`
- `stream_url`

Conflict behavior:

- default connect is fail-closed
- active lease returns `429 STREAM_ALREADY_ACTIVE`
- `Retry-After` and `error.details.retry_after` are authoritative cooldown hints
- recovery is explicit; do not emulate takeover with a blind retry loop

## Frontend runtime expectations

- query workloads use the registry in `frontend/src/lib/queryRuntime.ts`
- shell/bootstrap queries use the `bootstrap` policy
- repeated background `429` errors must be deduplicated into one notification class
- `/decisions` must not do `unscoped -> scoped` collection waterfalls on initial load
- `/pools/binding-profiles` must not read `/api/v2/pools/` until usage is explicitly requested
- one browser instance should keep one database stream owner path across tabs

## Validation commands

From repository root:

```bash
./scripts/dev/pytest.sh apps/api_v2/tests/test_system_bootstrap.py apps/api_v2/tests/test_database_stream_ticket_contract.py
./contracts/scripts/build-orchestrator-openapi.sh check
```

From `frontend/`:

```bash
npm run generate:api
npm run test:run -- src/api/queries/__tests__/queryOptions.performance.test.ts src/App.bindingProfilesRoute.test.tsx src/authz/AuthzProvider.test.tsx src/pages/Decisions/__tests__/DecisionsPage.test.tsx src/pages/Pools/__tests__/PoolBindingProfilesPage.test.tsx src/realtime/database/__tests__/databaseEventProjector.test.ts src/realtime/database/__tests__/databaseStreamCoordinator.test.ts src/realtime/database/__tests__/databaseStreamTransport.test.ts
npm run test:browser:ui-platform
npm run build
```

## Operator symptoms

If users report repeated `429` or toast floods:

1. verify `system/bootstrap` is the only shell bootstrap path in the affected route
2. verify only one browser tab acquires a database stream lease
3. inspect `Retry-After` on `/api/v2/databases/stream-ticket/`
4. inspect whether a route started eager secondary reads (`/api/v2/pools/`, unscoped `/api/v2/decisions/`)
