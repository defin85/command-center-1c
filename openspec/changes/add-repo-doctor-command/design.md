## Context

The repository already has useful diagnostics, but they are optimized for specific workflows rather than first-line triage:

- `make agent-verify` validates agent-facing docs and feature-loop scripts.
- `./debug/runtime-inventory.sh --json` is the source of truth for runtime topology.
- `./scripts/dev/health-check.sh` performs human-readable local health checks.
- `./debug/probe.sh all` performs a compact runtime PID/HTTP probe.
- `./scripts/dev/check-agent-doc-freshness.sh` validates authoritative docs against checked-in sources.

Prior art:

- `brew doctor` treats doctor as support/debug triage, supports listing/running individual checks, and exits non-zero on potential problems.
- `npm doctor` checks environment prerequisites and allows narrowing the executed check groups.
- Django system checks provide a useful model: stable check ids, severity, message, hint, and tags.

## Goals

- Provide one command that answers "is this repo ready enough for the requested class of work?"
- Keep default execution fast, local, read-only, and safe to run repeatedly.
- Make output useful both for humans and agents.
- Preserve existing source-of-truth scripts instead of reimplementing them inside doctor.
- Make failure severity explicit so a stopped runtime is not confused with broken repo guidance.

## Non-Goals

- Doctor is not a replacement for full `lint`, test, build, browser gates, or OpenSpec delivery validation.
- Doctor will not auto-fix issues in the first version.
- Doctor will not run production SSH checks unless `--profile prod` is explicitly requested.
- Doctor will not execute arbitrary shell commands or dynamically discover unbounded scripts.

## Decisions

### Decision: Implement doctor as a thin check registry

Use `scripts/qa/doctor.py` for orchestration and JSON output, with `scripts/qa/doctor.sh` as a stable shell wrapper. `make doctor` delegates to the wrapper.

Rationale:

- Python is already used for repo QA tooling and is better than shell for stable JSON, timeouts, and structured results.
- The shell wrapper keeps the command ergonomic and consistent with existing repo entrypoints.
- A check registry makes `--list-checks`, profile selection, and targeted checks straightforward.

### Decision: Default profile is local readiness, not full runtime acceptance

The default doctor should cover repo root, toolchain presence, docs freshness, OpenSpec specs, runtime inventory validity, and compact runtime probes. It should not require all runtimes to be started unless `--profile runtime` is selected.

Rationale:

- A fresh checkout may be healthy even when local services are intentionally stopped.
- Runtime-down diagnostics are useful as `WARN` in default mode and blocking as `FAIL` in runtime mode.

### Decision: Stable result contract

Each check result should include:

- `id`
- `title`
- `profile` / `tags`
- `status`: `ok`, `warn`, `fail`, `skip`, `error`
- `severity`
- `evidence`
- `hint`
- `duration_ms`

Exit codes:

- `0`: no `fail` or `error`
- `1`: at least one `fail` or `error`
- `2`: usage/configuration error

With `--strict`, `warn` also produces exit code `1`.

### Decision: Production diagnostics are explicit opt-in

`--profile prod` may run read-only checks through the canonical `cc1c-prod` alias, but the default profile must not touch production.

Rationale:

- Production probes can be slow, environment-sensitive, and surprising.
- The repo already treats production server status as a live source-of-truth workflow with explicit SSH alias usage.

## Alternatives Considered

### Shell-only doctor

Simpler to start, but weak for stable JSON, per-check timing, check selection, and unit testing.

### Replacing existing health/probe scripts

Cleaner long-term surface, but high risk of losing known local behavior. The first version should wrap existing scripts and only refactor once the structured contract is proven.

### Make `doctor` a full CI gate

Tempting, but it would become slow and noisy. CI/full delivery gates should stay in `docs/agent/VERIFY.md`; doctor should point to them when needed.

## Risks / Trade-offs

- Too many checks can make doctor slow. Mitigation: keep default bounded and require explicit profiles for expensive checks.
- Existing scripts are human-readable. Mitigation: parse only coarse exit/status in MVP; add JSON-native subcommands later if needed.
- Runtime checks can be false failures when services are intentionally stopped. Mitigation: profile-aware severity.
- JSON contract drift can break agents. Mitigation: add tests for schema, check ids, and representative status behavior.

## Open Questions

- Should `make doctor` run `agent-verify` by default, or keep it under `--profile agent` to reduce runtime?
- Should `--profile ci` include `openspec validate --specs --strict --no-interactive` by default even with dirty active changes?
- Should production profile include Prometheus target checks, or stay limited to service health in the first iteration?
