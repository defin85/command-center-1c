## MODIFIED Requirements
### Requirement: Editor hints MUST включать `target_binding` schema для `extensions.set_flags`
Система НЕ ДОЛЖНА (SHALL NOT) использовать editor hints action-catalog как основной путь настройки binding для runtime `extensions.set_flags`.

Основная настройка runtime `extensions.*` ДОЛЖНА (SHALL) выполняться через templates-first execution flow.

#### Scenario: Editor hints для `extensions.set_flags` не используются как runtime-контракт
- **GIVEN** staff открывает action catalog editor
- **WHEN** редактирует exposure с `capability="extensions.set_flags"`
- **THEN** UI показывает сообщение, что runtime-путь для `extensions.*` отключён
- **AND** рекомендует использовать templates-first execution path

## ADDED Requirements
### Requirement: Editor MUST блокировать runtime-публикацию `extensions.*` action capabilities
Система ДОЛЖНА (SHALL) блокировать публикацию `extensions.*` action capabilities как runtime execution контракт.

#### Scenario: Staff получает hard-block при публикации `extensions.*`
- **GIVEN** staff пытается создать или изменить action exposure с `capability` префикса `extensions.`
- **WHEN** пытается опубликовать runtime-конфигурацию
- **THEN** UI блокирует публикацию с ошибкой валидации
- **AND** сообщение содержит переход к templates-first execution flow
