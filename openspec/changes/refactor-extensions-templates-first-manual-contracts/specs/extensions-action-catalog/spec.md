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
### Requirement: `extensions.*` action exposures MUST быть деприоритизированы в runtime-контуре
Система ДОЛЖНА (SHALL) поддерживать миграционный режим для `extensions.*` action exposures, но НЕ ДОЛЖНА (SHALL NOT) использовать их как основной execution контракт.

#### Scenario: Миграционная диагностика фиксирует `extensions.*` exposures
- **GIVEN** в persistent store присутствуют action exposures с `capability` префикса `extensions.`
- **WHEN** запускается migration diagnostics/report
- **THEN** система возвращает список таких exposure
- **AND** оператор получает указание перейти на template-based manual contracts

## REMOVED Requirements
### Requirement: Actions для управления флагами расширений через capability
**Reason**: set_flags manual execution переносится на template-based contract-driven flow.
**Migration**: использовать `/operations` manual contracts + `template_id` + `bindings`.

### Requirement: extensions.set_flags поддерживает selective apply через params-based executor
**Reason**: selective apply остаётся, но описывается в `extensions-plan-apply` как часть template-based контракта, а не action-catalog контракта.
**Migration**: задавать selective apply через runtime input manual contract.

### Requirement: Presets для `extensions.set_flags` через `executor.fixed.apply_mask`
**Reason**: preset-mask в action catalog исключается из runtime-контракта.
**Migration**: переносить mask в runtime request (`apply_mask`) в contract-driven flow.

