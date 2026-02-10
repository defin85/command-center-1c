## MODIFIED Requirements
### Requirement: API для effective action catalog
Система ДОЛЖНА (SHALL) предоставлять effective action catalog endpoint для поддерживаемых action-catalog доменов.

Для домена extensions effective action catalog НЕ ДОЛЖЕН (SHALL NOT) быть runtime source of truth для execution path в `/extensions` и `/databases`.

#### Scenario: Extensions execution path не читает runtime actions из action catalog
- **GIVEN** в action catalog есть exposure с `capability` из префикса `extensions.`
- **WHEN** пользователь запускает extensions-сценарий из `/extensions` или `/databases`
- **THEN** runtime execution не резолвится через `ui/action-catalog`
- **AND** используется templates-first контракт

## ADDED Requirements
### Requirement: `extensions.*` action exposures MUST быть отключены как runtime execution контракт
Система НЕ ДОЛЖНА (SHALL NOT) использовать `extensions.*` action exposures для runtime execution в `/extensions` и `/databases`.

#### Scenario: Попытка runtime execution через `extensions.*` action exposure отклоняется
- **GIVEN** в persistent store присутствуют action exposures с `capability` префикса `extensions.`
- **WHEN** пользователь инициирует execution-path, который требует runtime action-catalog резолв для `extensions.*`
- **THEN** система отклоняет запуск fail-closed
- **AND** указывает использовать templates-first execution path

## REMOVED Requirements
### Requirement: Actions для управления флагами расширений через capability
**Reason**: runtime execution `extensions.*` через action catalog удаляется.
**Migration**: использовать template-based запуск с `template_id`.

### Requirement: extensions.set_flags поддерживает selective apply через params-based executor
**Reason**: selective apply остаётся, но описывается в `extensions-plan-apply` как часть template-based контракта, а не action-catalog контракта.
**Migration**: задавать selective apply через runtime input template-based запуска.

### Requirement: Presets для `extensions.set_flags` через `executor.fixed.apply_mask`
**Reason**: preset-mask в action catalog исключается из runtime-контракта.
**Migration**: переносить mask в runtime request (`apply_mask`) в template-based flow.
