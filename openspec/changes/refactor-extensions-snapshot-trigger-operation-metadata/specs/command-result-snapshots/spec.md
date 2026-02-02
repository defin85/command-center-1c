# Delta: command-result-snapshots

## MODIFIED Requirements

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

