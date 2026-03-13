# workflow-hardening-rollout-evidence Specification

## Purpose
TBD - created by archiving change tighten-workflow-hardening-canonical-contracts. Update Purpose after archive.
## Requirements
### Requirement: Workflow-centric hardening evidence MUST различать repository proof и tenant live cutover proof
Система ДОЛЖНА (SHALL) различать два класса evidence для workflow-centric hardening rollout:
- checked-in repository acceptance evidence для shipped default path;
- tenant-scoped live cutover evidence для staging/prod go-no-go.

Repository acceptance evidence ДОЛЖЕН (SHALL) доказывать repository-local shipped behavior через код, контракты, тесты и shipped docs, но НЕ ДОЛЖЕН (SHALL NOT) считаться достаточным production/staging rollout proof для конкретного tenant/environment.

Tenant-scoped cutover НЕ ДОЛЖЕН (SHALL NOT) получать `Go`, если присутствует только checked-in repository evidence без live evidence bundle.

#### Scenario: Repository evidence без tenant bundle блокирует cutover
- **GIVEN** change содержит checked-in repository acceptance evidence
- **AND** для целевого tenant/environment отсутствует live cutover evidence bundle
- **WHEN** оператор выполняет staging или production go-no-go
- **THEN** cutover отклоняется fail-closed
- **AND** диагностический результат явно указывает, что repository proof не заменяет tenant live evidence

### Requirement: Tenant live cutover evidence MUST быть schema-validated и operator-gated
Система ДОЛЖНА (SHALL) публиковать стабильный capability artifact path `docs/observability/artifacts/workflow-hardening-rollout-evidence/`, который содержит:
- `workflow-hardening-cutover-evidence.schema.json`;
- `workflow-hardening-cutover-evidence.example.json`;
- `README.md` с verifier invocation и interpretation rules.

Default live bundle location ДОЛЖЕН (SHALL) быть `docs/observability/artifacts/workflow-hardening-rollout-evidence/live/<tenant_id>/<environment>/workflow-hardening-cutover-evidence.json`.

Система ДОЛЖНА (SHALL) определять machine-readable bundle tenant-scoped live cutover evidence со schema version `workflow_hardening_cutover_evidence.v1`, включая поля:
- `schema_version`;
- `change_id`;
- `git_sha`;
- `environment`;
- `tenant_id`;
- `runbook_version`;
- `captured_at`;
- `bundle_digest`;
- `evidence_refs[]`;
- `overall_status`;
- `sign_off[]`.

`environment` ДОЛЖЕН (SHALL) иметь значение `staging` или `production`.

`overall_status` ДОЛЖЕН (SHALL) иметь значение `go` или `no_go`.

`evidence_refs[]` ДОЛЖЕН (SHALL) покрывать операторский canary минимум для:
- binding preview;
- create-run;
- inspect lineage;
- migration outcome или явный `not_applicable` reason.

Каждый `evidence_refs[]` item ДОЛЖЕН (SHALL) содержать:
- `kind` (`binding_preview`, `create_run`, `inspect_lineage`, `migration_outcome`);
- `uri`;
- `digest` в формате `sha256:<hex>`;
- `captured_at`;
- `result` (`passed`, `failed`, `not_applicable`).

Если `kind=migration_outcome` и `result=not_applicable`, item ДОЛЖЕН (SHALL) содержать `reason`.

Каждый `sign_off[]` item ДОЛЖЕН (SHALL) содержать:
- `role` (`platform`, `security`, `operations`);
- `actor`;
- `signed_at`;
- `verdict` (`go` или `no_go`).

Валидный bundle ДОЛЖЕН (SHALL) содержать ровно один `sign_off[]` item для каждой обязательной роли `platform`, `security`, `operations`.

Система ДОЛЖНА (SHALL) хранить schema/example/verifier contract в стабильном capability artifact path и валидировать bundle fail-closed до выдачи `Go`.

Verifier ДОЛЖЕН (SHALL) быть Django management command `verify_workflow_hardening_cutover_evidence`, принимать bundle path/URI и возвращать machine-readable verdict с полями:
- `status` (`passed` или `failed`);
- `go_no_go` (`go` или `no_go`);
- `bundle_digest`;
- `missing_requirements[]`;
- `failed_checks[]`.

Verifier ДОЛЖЕН (SHALL) отклонять bundle при отсутствии обязательных refs, digest, sign-off, schema match или machine-readable verdict.

Verifier ДОЛЖЕН (SHALL) завершаться с exit code `0` только при `status=passed` и `go_no_go=go`.

Runbook и release notes ДОЛЖНЫ (SHALL) ссылаться на bundle artifact location и digest, а не ограничиваться описанием repository-local evidence.

#### Scenario: Неполный evidence bundle блокирует go-no-go
- **GIVEN** оператор приложил tenant live evidence bundle
- **AND** в bundle отсутствует один из обязательных refs или sign-off
- **WHEN** выполняется verifier/gate check
- **THEN** система возвращает fail-closed результат
- **AND** go-no-go решение остаётся `No-Go`

#### Scenario: Полный evidence bundle позволяет завершить cutover
- **GIVEN** tenant live evidence bundle валиден по schema
- **AND** bundle содержит обязательные refs, digest и sign-off
- **WHEN** выполняется verifier/gate check
- **THEN** система помечает evidence как complete
- **AND** оператор может использовать этот bundle как вход для staging/prod go-no-go решения

#### Scenario: Migration outcome marked as not applicable remains machine-readable
- **GIVEN** tenant cutover не требует migration step
- **WHEN** оператор формирует live evidence bundle
- **THEN** `evidence_refs[]` содержит item с `kind=migration_outcome` и `result=not_applicable`
- **AND** item содержит machine-readable `reason`
- **AND** verifier не требует отсутствующий migration artifact сверх этого explicit outcome

