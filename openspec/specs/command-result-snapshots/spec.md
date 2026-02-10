# command-result-snapshots Specification

## Purpose
TBD - created by archiving change add-tenancy-extensions-plan-apply. Update Purpose after archive.
## Requirements
### Requirement: Система хранит append-only command result snapshots
Система ДОЛЖНА (SHALL) сохранять snapshots по metadata manual operations контракта.

#### Scenario: Snapshot сохраняется по metadata manual operation
- **GIVEN** операция содержит metadata `manual_operation`, `template_id`, `result_contract`
- **WHEN** приходит событие completion
- **THEN** snapshot сохраняется с raw + normalized representation

#### Scenario: Изменение deprecated action-catalog ключей не влияет на completion
- **GIVEN** action-catalog capability decommissioned
- **WHEN** приходит completion
- **THEN** snapshot pipeline не зависит от `ui.action_catalog`
- **AND** использует metadata manual operations контракта

### Requirement: Snapshot имеет детерминированный hash для drift check
Система ДОЛЖНА (SHALL) вычислять hash нормализованного snapshot (canonical hash), пригодный для drift check.

#### Scenario: Два одинаковых результата дают одинаковый hash
- **GIVEN** два snapshot’а с одинаковым нормализованным содержимым
- **WHEN** вычисляется canonical hash
- **THEN** hash совпадает

### Requirement: Snapshot доступен для preview в UI (RBAC+tenant)
Система ДОЛЖНА (SHALL) предоставлять API для выборки snapshot’ов и preview, ограниченный tenant context и RBAC.

#### Scenario: Пользователь не видит чужие snapshot’ы
- **GIVEN** пользователь работает в tenant A
- **WHEN** он запрашивает snapshot’ы
- **THEN** в ответе отсутствуют snapshot’ы tenant B

### Requirement: Snapshot normalization MUST использовать pinned mapping reference
Система ДОЛЖНА (SHALL) нормализовать raw результат через mapping spec, зафиксированный в metadata плана (`mapping_spec_id`, `mapping_spec_version`).

#### Scenario: Post-enqueue изменение mapping не меняет completion для существующего плана
- **GIVEN** план создан с pinned `mapping_spec_version=A`
- **AND** пользователь позже публикует версию `B`
- **WHEN** завершается операция по плану
- **THEN** completion использует mapping version `A`
- **AND** normalized snapshot детерминирован относительно plan metadata

### Requirement: Result contract MUST быть явным в metadata
Система ДОЛЖНА (SHALL) фиксировать `result_contract` в metadata операции.

#### Scenario: Completion валидирует normalized snapshot против result contract
- **GIVEN** metadata содержит `result_contract`
- **WHEN** выполняется normalization raw output
- **THEN** normalized payload валидируется против contract schema
- **AND** при ошибке сохраняется parse/validation diagnostics без потери raw snapshot

