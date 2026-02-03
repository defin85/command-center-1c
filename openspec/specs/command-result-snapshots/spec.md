# command-result-snapshots Specification

## Purpose
TBD - created by archiving change add-tenancy-extensions-plan-apply. Update Purpose after archive.
## Requirements
### Requirement: Система хранит append-only command result snapshots
Система ДОЛЖНА (SHALL) сохранять результаты выполнения “snapshot-producing” команд в append-only хранилище snapshot’ов.

#### Scenario: Snapshot сохраняется по маркеру в operation metadata
- **GIVEN** операция имеет маркер snapshot-поведения в `BatchOperation.metadata` (например `snapshot_kinds` содержит `"extensions"`)
- **WHEN** приходит событие `worker completed`
- **THEN** система сохраняет snapshot с `tenant_id`, `operation_id`, `command_id`, `database_id`, `raw` и `normalized`

#### Scenario: Изменение runtime settings после enqueue не влияет на snapshot
- **GIVEN** операция помечена как snapshot-producing через `BatchOperation.metadata`
- **AND** `ui.action_catalog` изменился после enqueue операции
- **WHEN** приходит событие `worker completed`
- **THEN** snapshot сохраняется (решение не зависит от runtime settings на стадии completion)

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

