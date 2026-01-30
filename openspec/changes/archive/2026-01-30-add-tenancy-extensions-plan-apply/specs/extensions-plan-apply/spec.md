## ADDED Requirements

### Requirement: Plan/apply для extensions с drift check
Система ДОЛЖНА (SHALL) поддерживать plan/apply для extensions операций с drift check.

#### Scenario: Plan фиксирует preconditions по snapshot hash
- **GIVEN** пользователь строит plan для набора баз
- **WHEN** plan создан
- **THEN** plan содержит `base_snapshot_hash` (per database) и время snapshot’а

#### Scenario: Apply fail closed при дрейфе (strict)
- **GIVEN** plan построен по snapshot hash H
- **AND** фактическое состояние изменилось (preflight `extensions.list` даёт hash != H)
- **WHEN** пользователь запускает apply
- **THEN** система возвращает 409 (conflict) и требует re-plan

#### Scenario: Apply обновляет snapshot после выполнения
- **GIVEN** apply успешно выполнен
- **WHEN** операция завершилась
- **THEN** latest extensions snapshot для каждой базы обновлён и доступен в `/extensions` overview

### Requirement: Tenant-scoped mapping для extensions inventory
Система ДОЛЖНА (SHALL) позволять tenant-admin настроить mapping нормализованного extensions snapshot в канонический `extensions_inventory`.

#### Scenario: Mapping применяется в preview
- **GIVEN** tenant A настроил mapping для `extensions_inventory`
- **WHEN** пользователь делает preview snapshot
- **THEN** результат отображается в каноническом формате и валидируется по schema

