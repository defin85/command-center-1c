# Change: Add Repository Doctor Command

## Why

Сейчас repo readiness и runtime diagnostics разложены по нескольким entrypoints: `make agent-verify`, `./debug/runtime-inventory.sh --json`, `./scripts/dev/health-check.sh`, `./debug/probe.sh all` и `./scripts/dev/check-agent-doc-freshness.sh`.

Это работает для опытного оператора, но плохо как first-line triage: агенту или разработчику нужно помнить порядок, scope и то, какие failures являются blockers. Нужен единый bounded `doctor` facade с profile-aware checks, стабильным JSON output и честными exit codes.

## What Changes

- Add a repo-level doctor entrypoint discoverable as `make doctor` and `./scripts/qa/doctor.sh`.
- Define bounded profiles for `agent`, `runtime`, `ci`, and explicit opt-in `prod` diagnostics.
- Reuse existing checked-in checks instead of duplicating health/probe/doc-freshness logic.
- Add stable check identifiers, severity/status taxonomy, remediation hints, timing, and `--json` output.
- Keep default doctor fast and local; heavy validation and production probes must be opt-in.
- Extend agent-doc freshness validation so authoritative docs cannot drift from the doctor entrypoint and check contract.

## Impact

- Affected specs:
  - `agent-workflow-assets`
  - `agent-doc-freshness`
- Affected code/docs:
  - `Makefile`
  - `scripts/qa/doctor.sh`
  - `scripts/qa/doctor.py`
  - `scripts/qa/*` tests or `scripts/dev/tests/*`
  - `docs/agent/INDEX.md`
  - `docs/agent/RUNBOOK.md`
  - `docs/agent/VERIFY.md`
  - `docs/agent/TASK_ROUTING.md`
  - `scripts/dev/check-agent-doc-freshness.py`
