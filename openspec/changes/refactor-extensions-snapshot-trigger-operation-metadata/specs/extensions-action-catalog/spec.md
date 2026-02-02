# Delta: extensions-action-catalog

## ADDED Requirements

### Requirement: Семантика extensions действий задаётся capability, а не id
Система ДОЛЖНА (SHALL) поддерживать явное поле `capability` для действий extensions в `ui.action_catalog`, чтобы backend мог определять семантику без привязки к `action.id`.

#### Scenario: Произвольный action.id с capability работает
- **GIVEN** в `ui.action_catalog` есть действие с произвольным `id` (например `ListExtension`)
- **AND** у него `capability` задан в формате namespaced string (например `extensions.list`)
- **AND** `executor.command_id` указывает на валидную команду драйвера
- **WHEN** пользователь запускает это действие
- **THEN** система трактует его как `extensions.list` (для plan/apply и snapshot-marking), независимо от `id`

## MODIFIED Requirements

### Requirement: Snapshot расширений в Postgres
Система ДОЛЖНА (SHALL) хранить последний известный snapshot расширений по каждой базе в Postgres.

#### Scenario: Snapshot обновляется после успешного list/sync (capability-based)
- **WHEN** завершается успешная операция list/sync расширений, помеченная как snapshot-producing
- **THEN** запись snapshot расширений для этой базы upsert'ится с актуальными данными
