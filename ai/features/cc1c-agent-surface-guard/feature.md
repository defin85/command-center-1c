# Feature Contract

## Goal

Expose a portable autoresearch process surface in `command-center-1c` without disrupting the repo's existing canonical agent guidance.

## User-visible behavior

A fresh agent can run `make codex-onboard`, discover the canonical onboarding router, verify the local process surface, and execute a feature loop against a safe repo-owned feature pack.

## Interfaces involved

- `Makefile`
- `scripts/qa/*`
- `scripts/feature_loop*.py`
- `scripts/start_run.py`
- `scripts/validate_dataset.py`
- `ai/features/`

## Acceptance criteria

- `make codex-onboard` prints the canonical onboarding router and the available feature pack.
- `make agent-verify` passes without touching product code paths.
- `make validate-feature`, `make feature-start`, `make feature-baseline`, `make feature-iteration`, `make feature-holdout`, and `make feature-ci-replay` work for this feature pack.
- The existing repo-owned docs freshness checker remains the source of truth for agent docs integrity.

## Non-goals

- No product behavior changes in `frontend/`, `orchestrator/`, `go-services/`, or `contracts/`.
- No rewrite of the existing `docs/agent/*` surface.
- No attempt to retrofit the whole repo onto the template's exact directory naming.

## Known risks

- The repo already has a strong agent surface, so the portable layer must stay a thin merge and not compete with the checked-in guidance.
- Clean replay copies the working tree and can be slower on a multi-stack repo.
