## 1. Contract And Scaffolding

- [ ] 1.1 Define the doctor check registry, profiles, severity/status taxonomy, exit codes, and JSON schema in `scripts/qa/doctor.py`.
- [ ] 1.2 Add `scripts/qa/doctor.sh` as the stable executable wrapper.
- [ ] 1.3 Add `make doctor` and document its default profile in `Makefile`.

## 2. Checks

- [ ] 2.1 Implement repo-root and required-surface checks for `AGENTS.md`, `openspec/`, `docs/agent/INDEX.md`, `.codex/config.toml`, and script availability.
- [ ] 2.2 Implement toolchain presence/version checks against `.tool-versions` without installing or mutating tools.
- [ ] 2.3 Wrap `./scripts/dev/check-agent-doc-freshness.sh` as an agent/docs check.
- [ ] 2.4 Wrap `make agent-verify` or its underlying script as an explicit `agent` profile check.
- [ ] 2.5 Validate `./debug/runtime-inventory.sh --json` and expected runtime entries.
- [ ] 2.6 Wrap `./debug/probe.sh all` with profile-aware severity for stopped local runtimes.
- [ ] 2.7 Wrap `./scripts/dev/health-check.sh` under `--profile runtime`.
- [ ] 2.8 Add optional read-only `--profile prod` checks through the canonical `cc1c-prod` alias.

## 3. CLI Behavior

- [ ] 3.1 Support default run, `--profile <name>`, `--json`, `--strict`, `--list-checks`, and explicit check ids.
- [ ] 3.2 Ensure unknown profile/check ids fail with usage exit code `2` and actionable messages.
- [ ] 3.3 Ensure each check has a stable id, title, tags/profile, evidence, hint, status, severity, and duration.
- [ ] 3.4 Ensure command output redacts obvious secrets and does not print raw environment values by default.

## 4. Documentation And Freshness

- [ ] 4.1 Document doctor in `docs/agent/INDEX.md`, `docs/agent/RUNBOOK.md`, `docs/agent/VERIFY.md`, and `docs/agent/TASK_ROUTING.md`.
- [ ] 4.2 Update `scripts/dev/check-agent-doc-freshness.py` so authoritative docs and `Makefile` cannot drift from the doctor command.
- [ ] 4.3 Add or update tests for doc freshness fixtures that mention doctor.

## 5. Verification

- [ ] 5.1 Add unit tests for doctor result schema, profile selection, exit-code behavior, and representative wrapped-check outcomes.
- [ ] 5.2 Run `make doctor` and `make doctor -- --json` or the repo-conventional equivalent.
- [ ] 5.3 Run `make agent-verify`.
- [ ] 5.4 Run `openspec validate add-repo-doctor-command --strict --no-interactive`.
