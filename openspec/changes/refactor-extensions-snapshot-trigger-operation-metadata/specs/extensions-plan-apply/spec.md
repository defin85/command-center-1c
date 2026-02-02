# Delta: extensions-plan-apply

## MODIFIED Requirements

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

