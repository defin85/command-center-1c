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

### Requirement: Зарезервированные capability валидируются fail-closed
Система ДОЛЖНА (SHALL) обеспечивать детерминизм для capability, которые backend понимает и использует для особой семантики (plan/apply, snapshot-marking).

#### Scenario: Дубликаты зарезервированного capability отвергаются
- **GIVEN** payload `ui.action_catalog` содержит два actions с одинаковым `capability`, который поддерживается backend (например `extensions.list`)
- **WHEN** staff пытается сохранить/обновить `ui.action_catalog`
- **THEN** система возвращает ошибку валидации (fail-closed) и не сохраняет payload

#### Scenario: Unknown capability допускается и не ломает валидацию
- **GIVEN** payload содержит `capability`, который backend пока не поддерживает (например `custom.extensions.list`)
- **WHEN** staff сохраняет `ui.action_catalog`
- **THEN** payload проходит schema-валидацию (при условии корректного формата строки)
- **AND** backend не приписывает этому capability особую семантику, пока явно не поддержит

## MODIFIED Requirements

### Requirement: Snapshot расширений в Postgres
Система ДОЛЖНА (SHALL) хранить последний известный snapshot расширений по каждой базе в Postgres.

#### Scenario: Snapshot обновляется после успешного list/sync (capability-based)
- **WHEN** завершается успешная операция list/sync расширений, помеченная как snapshot-producing
- **THEN** запись snapshot расширений для этой базы upsert'ится с актуальными данными
