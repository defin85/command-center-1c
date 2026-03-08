## ADDED Requirements
### Requirement: Pools master-data workspace MUST показывать readiness checklist для run публикации
UI master-data workspace MUST предоставлять оператору readiness checklist перед запуском/подтверждением публикации, включая отсутствующие canonical сущности, bindings и неполноту policy profile.

#### Scenario: Оператор видит блокеры и может перейти к их устранению
- **GIVEN** readiness preflight вернул блокеры
- **WHEN** оператор открывает run inspection в UI
- **THEN** интерфейс показывает список блокеров в операторском формате
- **AND** для каждого блокера доступны remediation переходы в соответствующий раздел workspace

### Requirement: Run inspection UI MUST отображать результат OData verification после публикации
После завершения публикации UI MUST показывать verification summary по опубликованным refs, включая количество проверенных документов и mismatch counters.

#### Scenario: UI показывает итог сверки документов по OData
- **GIVEN** run завершён и verifier выполнил post-run проверку
- **WHEN** оператор открывает report
- **THEN** он видит `verification_status`, `verified_documents_count` и `mismatch_count`
- **AND** может раскрыть детали mismatches без чтения raw JSON
