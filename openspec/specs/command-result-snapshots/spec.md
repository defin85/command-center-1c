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

### Requirement: Completion MUST резолвить mapping строго по pinned reference
Система ДОЛЖНА (SHALL) использовать для completion normalization только mapping, зафиксированный в metadata (`mapping_spec_id`, `mapping_spec_version`), без неявного переключения на текущее состояние mapping.

#### Scenario: Pinned mapping ref доступен и согласован по версии
- **GIVEN** metadata содержит `mapping_spec_ref` с корректными `mapping_spec_id`, `mapping_spec_version`, `entity_kind`
- **WHEN** выполняется completion
- **THEN** canonical normalization использует только pinned mapping из metadata
- **AND** canonical snapshot детерминирован относительно metadata плана

#### Scenario: Pinned mapping version расходится с текущим опубликованным mapping
- **GIVEN** план создан с pinned `mapping_spec_version=A`
- **AND** к моменту completion в системе опубликована версия `B`
- **WHEN** выполняется completion по данному плану
- **THEN** система не применяет runtime fallback на текущий mapping
- **AND** raw snapshot сохраняется вместе с diagnostics о version mismatch

#### Scenario: Pinned mapping недоступен на completion
- **GIVEN** metadata содержит `mapping_spec_ref`, но соответствующий mapping отсутствует/недоступен
- **WHEN** выполняется completion
- **THEN** система сохраняет raw snapshot и diagnostics о невозможности применить pinned mapping
- **AND** не подменяет mapping на произвольный runtime fallback

### Requirement: Completion MUST сохранять diagnostics при нарушении result contract
Система ДОЛЖНА (SHALL) валидировать canonical payload против `result_contract` и сохранять diagnostics при несоответствии, не теряя append-only snapshot историю.

#### Scenario: Canonical payload не проходит валидацию result contract
- **GIVEN** metadata содержит `result_contract`
- **WHEN** completion формирует canonical payload, который нарушает contract schema
- **THEN** snapshot сохраняется вместе с validation diagnostics
- **AND** raw payload остаётся доступным для аудита и разбора

