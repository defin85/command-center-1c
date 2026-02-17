## MODIFIED Requirements
### Requirement: Pool runtime templates MUST быть system-managed и недоступны для пользовательского write-path
Система ДОЛЖНА (SHALL) помечать runtime templates с alias `pool.*` как system-managed в domain `pool_runtime`.

Система НЕ ДОЛЖНА (SHALL NOT) позволять create/update/delete этих templates через публичный templates management API.

Система ДОЛЖНА (SHALL) показывать system-managed `pool.*` templates в `/templates` list для пользователей с правом просмотра templates, как read-only сущности с явным индикатором system-managed/domain.

#### Scenario: Попытка изменить system-managed pool template через `/templates` отклоняется
- **GIVEN** существует system-managed template alias `pool.prepare_input`
- **WHEN** пользователь отправляет update/delete через templates write endpoint
- **THEN** система возвращает отказ доступа или business conflict
- **AND** definition/exposure не изменяются

#### Scenario: `/templates` list показывает system-managed pool templates как read-only
- **GIVEN** в registry присутствуют alias `pool.prepare_input` и `pool.publication_odata`
- **WHEN** пользователь с правом template view открывает `/templates`
- **THEN** список содержит эти alias
- **AND** строки помечены как `system-managed` в domain `pool_runtime`
- **AND** UI не предлагает edit/delete action для этих строк
