## ADDED Requirements

### Requirement: extensions.set_flags поддерживает selective apply через params-based executor
Система ДОЛЖНА (SHALL) обеспечивать selective apply для reserved capability `extensions.set_flags` через executor, который задаёт флаги в `executor.params`.

#### Scenario: selective apply требует params-based executor shape
- **GIVEN** в `ui.action_catalog` есть действие с `capability="extensions.set_flags"`
- **WHEN** оператор запускает selective apply (не все флаги выбраны)
- **THEN** backend применяет mask, удаляя невыбранные флаги из `executor.params`
- **AND** если executor не поддерживает params-based режим (например, использует только `additional_args`), backend возвращает ошибку конфигурации (fail-closed)

