---
paths: contracts/**/*.yaml
---

# OpenAPI Contracts (Contract-First Development)

> Single source of truth for REST API contracts.

## Structure

```
contracts/
├── ras-adapter/openapi.yaml      # ras-adapter API spec
├── orchestrator/openapi.yaml     # Orchestrator API spec
├── api-gateway/openapi.yaml      # (future)
└── scripts/
    ├── generate-all.sh           # Generate all clients
    ├── validate-specs.sh         # Validate specs
    └── check-breaking-changes.sh # Check breaking changes
```

## API Change Workflow

1. **Update OpenAPI spec** (`contracts/<service>/openapi.yaml`)
2. **Validate:** `./contracts/scripts/validate-specs.sh`
3. **Generate clients:** `./contracts/scripts/generate-all.sh`
4. **Implement handlers** using generated types
5. **Commit** (pre-commit hook auto-validates)

## Generation

**Automatic (on start):**
```bash
./scripts/dev/start-all.sh  # Phase 1.5: API client generation
```

**Manual:**
```bash
./contracts/scripts/generate-all.sh         # All services
./contracts/scripts/generate-all.sh --force # Force regeneration
```

**Results:**
- **Go server types:** `go-services/<service>/internal/api/generated/server.go`
- **Python client:** `orchestrator/apps/databases/clients/generated/<service>_api_client/`

## Git Hooks

Enable pre-commit hook for auto-validation:

```bash
git config core.hooksPath .githooks
```

On commit to `contracts/**/*.yaml`:
1. OpenAPI spec validation
2. Breaking changes check
3. Client regeneration

## Best Practices

- **ALWAYS** use `cluster_id` parameter (not `cluster`) for infobases endpoints
- **All parameters:** `snake_case` (Go/Python convention match)
- **Breaking changes:** require API versioning (v1 → v2) and deprecation notice
- **Reuse:** use `$ref` for common schemas

**Details:** See `contracts/README.md`
