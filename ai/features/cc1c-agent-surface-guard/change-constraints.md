# Feature Change Constraints

## Protected files

- `frontend/`
- `orchestrator/`
- `go-services/`
- `contracts/`
- `openspec/`

## API and schema invariants

- Do not change existing runtime, API, OpenAPI, or UI contracts.
- Do not rename the canonical agent docs files already owned by the repo.

## Verification boundaries

- Do not edit `holdout.jsonl` during tuning.
- Do not weaken `scripts/dev/check-agent-doc-freshness.sh`.
- Keep repo-owned docs freshness checks as the source of truth for agent-facing guidance integrity.

## Operational boundaries

- Keep the write scope inside the portable process layer and feature pack files.
- Prefer wrappers that call existing repo-owned checks instead of inventing new parallel checks.
