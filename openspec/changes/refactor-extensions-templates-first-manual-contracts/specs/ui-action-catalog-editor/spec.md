## MODIFIED Requirements
### Requirement: Editor hints MUST включать `target_binding` schema для `extensions.set_flags`
Система НЕ ДОЛЖНА (SHALL NOT) использовать editor hints action-catalog как основной путь настройки binding для runtime `extensions.set_flags`.

Основная настройка binding для manual extensions запуска ДОЛЖНА (SHALL) выполняться в contract-driven форме `/operations`.

#### Scenario: Editor hints для `extensions.set_flags` не используются как runtime-контракт
- **GIVEN** staff открывает action catalog editor
- **WHEN** редактирует exposure с `capability="extensions.set_flags"`
- **THEN** UI показывает сообщение о депрекации runtime-пути
- **AND** рекомендует настраивать binding в `/operations` manual contract flow

## ADDED Requirements
### Requirement: Editor SHALL предупреждать о депрекации `extensions.*` action capabilities
Система ДОЛЖНА (SHALL) явно предупреждать staff, что `extensions.*` action capabilities не являются основным runtime execution контрактом.

#### Scenario: Staff получает deprecation warning для `extensions.*`
- **GIVEN** staff пытается создать или изменить action exposure с `capability` префикса `extensions.`
- **WHEN** открывает экран редактирования
- **THEN** UI показывает deprecation warning
- **AND** предупреждение содержит переход к templates-first manual contracts в `/operations`

