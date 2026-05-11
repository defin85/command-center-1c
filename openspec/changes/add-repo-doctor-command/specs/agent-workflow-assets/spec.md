## ADDED Requirements

### Requirement: Repository doctor command MUST provide bounded triage entrypoint

Система ДОЛЖНА (SHALL) предоставлять единый repository doctor entrypoint для first-line diagnostics по repo readiness, agent guidance и local runtime state.

Doctor entrypoint ДОЛЖЕН (SHALL) быть discoverable как минимум через:
- `make doctor`;
- stable checked-in wrapper under `scripts/qa/`;
- authoritative agent-facing docs.

Default doctor run ДОЛЖЕН (SHALL) быть bounded, локальным и read-only. Он НЕ ДОЛЖЕН (SHALL NOT) запускать full lint/test/build/browser gates, production SSH probes или mutating repair actions без explicit operator opt-in.

Doctor ДОЛЖЕН (SHALL) переиспользовать существующие checked-in source-of-truth checks and inventories вместо silent duplicate logic, включая:
- agent docs / feature-loop verification;
- machine-readable runtime inventory;
- local runtime probe/health entrypoints;
- OpenSpec/spec validation entrypoints where selected by profile.

#### Scenario: Агент запускает default doctor для fresh checkout triage
- **GIVEN** агент находится в корне репозитория
- **WHEN** он запускает `make doctor`
- **THEN** command выполняет bounded local readiness checks
- **AND** выводит понятный human-readable summary
- **AND** не запускает production SSH probes, full frontend/browser gates или mutating restart/repair actions

#### Scenario: Runtime stopped не маскируется под broken repo guidance
- **GIVEN** локальные runtime services намеренно не запущены
- **WHEN** агент запускает default doctor
- **THEN** doctor сообщает stopped runtime state как profile-aware diagnostic
- **AND** не смешивает это с failure authoritative docs, specs или repo tooling surfaces

### Requirement: Repository doctor command MUST expose stable structured results

Система ДОЛЖНА (SHALL) предоставлять stable machine-readable doctor output для agents и automation.

Каждый doctor check result ДОЛЖЕН (SHALL) включать как минимум:
- stable `id`;
- short title;
- status/severity;
- profile или tags;
- bounded evidence;
- remediation hint, если применимо;
- duration.

Doctor ДОЛЖЕН (SHALL) поддерживать `--json` output, который сохраняет этот contract независимо от human-readable formatting.

Doctor exit codes ДОЛЖНЫ (SHALL) быть стабильными:
- `0` when no fail/error result exists;
- `1` when at least one fail/error result exists;
- `2` for usage/configuration errors.

Strict mode ДОЛЖЕН (SHALL) allow warnings to become blocking without changing result status semantics.

#### Scenario: Automation consumes doctor JSON
- **GIVEN** automation needs repo triage evidence
- **WHEN** it runs doctor with `--json`
- **THEN** output contains one structured result per executed check
- **AND** each result has stable id, status/severity, bounded evidence, hint, and duration
- **AND** exit code follows the documented doctor contract

### Requirement: Repository doctor command MUST support selectable checks and profiles

Система ДОЛЖНА (SHALL) поддерживать discovery and selective execution of doctor checks.

Doctor ДОЛЖЕН (SHALL) поддерживать как минимум:
- `--list-checks`;
- named profiles for `agent`, `runtime`, and `ci`;
- explicit opt-in production profile for read-only production probes;
- direct execution by check id.

Unknown profile or check id ДОЛЖЕН (SHALL) fail with usage/configuration error and actionable message.

Production profile ДОЛЖЕН (SHALL) be opt-in and read-only, and it ДОЛЖЕН (SHALL) use canonical production alias guidance instead of embedding raw host/user/port details in the command contract.

#### Scenario: Operator limits doctor to runtime checks
- **GIVEN** local app services were just restarted
- **WHEN** operator runs doctor with runtime profile
- **THEN** doctor executes runtime inventory/probe/health checks
- **AND** does not run unrelated frontend full tests or production checks

#### Scenario: Agent lists available doctor checks
- **GIVEN** agent needs a narrow diagnostic check
- **WHEN** it runs doctor with `--list-checks`
- **THEN** output lists stable check ids, profiles/tags, and short descriptions
- **AND** the agent can rerun one check by id
