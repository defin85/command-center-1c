## MODIFIED Requirements

### Requirement: Plan/apply для extensions с drift check
Система ДОЛЖНА (SHALL) поддерживать plan/apply для extensions операций с drift check.

#### Scenario: Apply set_flags обновляет snapshots по маркеру snapshot-producing
- **GIVEN** оператор запускает apply для `capability="extensions.set_flags"`
- **WHEN** операция завершилась (success или partial success)
- **THEN** latest extensions snapshot для каждой затронутой базы обновлён или переобновлён по маркеру snapshot-producing
- **AND** UI может пересчитать дрейф на основании обновлённых snapshots

## ADDED Requirements

### Requirement: Drift check для применения флагов
Система ДОЛЖНА (SHALL) выполнять drift check при применении policy флагов расширений.

#### Scenario: Планирование фиксирует preconditions
- **WHEN** пользователь делает plan для `extensions.set_flags` по списку баз
- **THEN** plan содержит preconditions по snapshot hash/updated_at, чтобы apply мог detect drift (изменение snapshots между plan и apply)

