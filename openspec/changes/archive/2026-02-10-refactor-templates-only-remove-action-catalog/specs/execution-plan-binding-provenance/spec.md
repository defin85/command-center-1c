## MODIFIED Requirements
### Requirement: Preview plan/provenance до запуска
Система ДОЛЖНА (SHALL) предоставлять staff-only preview API для templates/manual operations flow без создания исполнения.

#### Scenario: Preview доступен из `/databases` manual operations
- **GIVEN** пользователь staff
- **WHEN** запрашивает preview перед запуском manual operation из `/databases`
- **THEN** UI получает plan+bindings до запуска

#### Scenario: Preview доступен из `/extensions` manual operations
- **GIVEN** пользователь staff
- **WHEN** запрашивает preview перед запуском manual operation из `/extensions`
- **THEN** UI получает plan+bindings до запуска

### Requirement: Persisted plan/provenance доступен в details
Система ДОЛЖНА (SHALL) сохранять provenance с привязкой к templates/manual operations контракту.

#### Scenario: Persisted metadata содержит manual operation context
- **WHEN** staff открывает details выполнения
- **THEN** metadata включает `manual_operation` и `template_id`
- **AND** action-catalog поля (`action_id`, `action_capability`) отсутствуют
