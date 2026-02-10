## MODIFIED Requirements
### Requirement: Staff может увидеть plan/provenance при запуске действия расширений
Система ДОЛЖНА (SHALL) позволять staff пользователю увидеть Execution Plan + Binding Provenance при запуске действий расширений из UI до подтверждения запуска, включая `/databases` и ручной fallback-путь в `/operations`.

#### Scenario: Staff видит preview перед запуском действия из `/operations`
- **GIVEN** staff пользователь запускает ручный `extensions.set_flags` flow в `/operations`
- **WHEN** формируется plan
- **THEN** UI отображает plan+bindings
- **AND** операция enqueue/apply выполняется только после подтверждения

## ADDED Requirements
### Requirement: Ручной `extensions.set_flags` в `/operations` SHALL выбирать `action_id` из effective Action Catalog
Система ДОЛЖНА (SHALL) в ручном `/operations` flow использовать effective action catalog и требовать выбор конкретного `action_id` для `capability="extensions.set_flags"`.

#### Scenario: Оператор выбирает action из effective catalog
- **GIVEN** в effective action catalog доступны published actions для `extensions.set_flags`
- **WHEN** оператор открывает ручной flow в `/operations`
- **THEN** UI показывает список доступных `action_id`/label
- **AND** выбранный action используется при `extensions.plan`

#### Scenario: Action catalog недоступен или пуст для capability
- **GIVEN** нет доступных actions `extensions.set_flags`
- **WHEN** оператор пытается запустить ручной flow
- **THEN** UI блокирует запуск
- **AND** показывает actionable подсказку открыть Action Catalog и настроить/publish action
