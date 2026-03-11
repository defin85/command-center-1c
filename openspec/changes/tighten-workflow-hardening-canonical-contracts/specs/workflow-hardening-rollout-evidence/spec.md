## ADDED Requirements
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
Система ДОЛЖНА (SHALL) определять machine-readable bundle tenant-scoped live cutover evidence в стабильном capability path после archive, включая как минимум:
- `schema_version`;
- `change_id`;
- `git_sha`;
- `environment`;
- `tenant_id`;
- `runbook_version`;
- `captured_at`;
- `evidence_refs[]`;
- `overall_status`;
- `sign_off[]`.

`evidence_refs[]` ДОЛЖЕН (SHALL) покрывать операторский canary минимум для:
- binding preview;
- create-run;
- inspect lineage;
- migration outcome или явный `not_applicable` reason.

Система ДОЛЖНА (SHALL) хранить schema/example/verifier contract в стабильном capability artifact path и валидировать bundle fail-closed до выдачи `Go`.

Verifier ДОЛЖЕН (SHALL) отклонять bundle при отсутствии обязательных refs, digest, sign-off или machine-readable verdict.

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
