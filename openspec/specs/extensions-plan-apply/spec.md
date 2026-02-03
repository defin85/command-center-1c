# extensions-plan-apply Specification

## Purpose
TBD - created by archiving change add-tenancy-extensions-plan-apply. Update Purpose after archive.
## Requirements
### Requirement: Plan/apply для extensions с drift check
Система ДОЛЖНА (SHALL) поддерживать plan/apply для extensions операций с drift check.

#### Scenario: Apply обновляет snapshot по маркеру в операции
- **GIVEN** apply успешно выполнен
- **WHEN** операция завершилась
- **THEN** latest extensions snapshot для каждой базы обновлён на основании маркера snapshot-поведения в `BatchOperation.metadata`

#### Scenario: Catalog change mid-flight не ломает обновление snapshot
- **GIVEN** apply операция была поставлена в очередь с валидным extensions executor
- **AND** `ui.action_catalog` изменился после enqueue операции
- **WHEN** операция завершилась
- **THEN** extensions snapshot обновляется (решение не зависит от action catalog на стадии completion)

#### Scenario: Apply выбирает executor по capability, а не по action.id
- **GIVEN** в effective `ui.action_catalog` настроено действие с `capability="extensions.sync"` и произвольным `id`
- **WHEN** пользователь запускает apply
- **THEN** backend выбирает executor по `capability`, а `id` не участвует в определении семантики

### Requirement: Tenant-scoped mapping для extensions inventory
Система ДОЛЖНА (SHALL) позволять tenant-admin настроить mapping нормализованного extensions snapshot в канонический `extensions_inventory`.

#### Scenario: Mapping применяется в preview
- **GIVEN** tenant A настроил mapping для `extensions_inventory`
- **WHEN** пользователь делает preview snapshot
- **THEN** результат отображается в каноническом формате и валидируется по schema

