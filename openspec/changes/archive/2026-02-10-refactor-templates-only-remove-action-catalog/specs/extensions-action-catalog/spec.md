## ADDED Requirements
### Requirement: Action Catalog capability MUST быть полностью decommissioned
Система НЕ ДОЛЖНА (SHALL NOT) предоставлять runtime и management контракты Action Catalog как platform capability.

#### Scenario: Legacy endpoint недоступен
- **WHEN** клиент вызывает `GET /api/v2/ui/action-catalog/`
- **THEN** API возвращает `HTTP 404`
- **AND** тело ошибки содержит `error.code="NOT_FOUND"`
- **AND** runtime execution через action catalog недоступен

#### Scenario: Action-catalog surface недоступен в operation-catalog
- **WHEN** клиент вызывает operation-catalog c `surface=action_catalog`
- **THEN** API возвращает `HTTP 400` (`VALIDATION_ERROR`)
- **AND** action-catalog management path не активируется

#### Scenario: Legacy action-catalog данные удалены
- **WHEN** завершён cutover migration
- **THEN** `surface=action_catalog` exposure rows отсутствуют в БД
- **AND** capability не может быть реактивирована конфигурацией

## REMOVED Requirements
### Requirement: RuntimeSetting для каталога действий расширений
**Reason**: capability decommissioned.
**Migration**: templates/manual-operations execution only.

### Requirement: API для effective action catalog
**Reason**: endpoint удалён.
**Migration**: templates/manual-operations APIs.

### Requirement: Action executors
**Reason**: action layer удалён.
**Migration**: executors настраиваются в templates.

### Requirement: Deactivate и delete — разные действия
**Reason**: action model удалён.
**Migration**: ручные операции задаются hardcoded manual operations layer.

### Requirement: Bulk execution
**Reason**: bulk через action catalog удалён.
**Migration**: template-based manual operations bulk path.

### Requirement: Fail-closed validation
**Reason**: action-catalog validation больше неактуальна.
**Migration**: fail-closed validation в manual operations + template compatibility.

### Requirement: Snapshot расширений в Postgres
**Reason**: этот аспект переопределяется в `command-result-snapshots` через result-contract mapping.
**Migration**: использовать manual_operation metadata + pinned mapping.

### Requirement: Staff может увидеть plan/provenance при запуске действия расширений
**Reason**: action-catalog launch flow удалён.
**Migration**: preview/provenance в templates/manual flow.

### Requirement: User-friendly ошибки preflight для действий расширений
**Reason**: action-catalog launch flow удалён.
**Migration**: ошибки остаются в manual operations UI.

### Requirement: Семантика extensions действий задаётся capability, а не id
**Reason**: action entity удалён.
**Migration**: semantics задаются hardcoded `manual_operation` keys.

### Requirement: Зарезервированные capability валидируются fail-closed
**Reason**: reserved action-catalog semantics удалены.
**Migration**: fail-closed manual_operation/template compatibility.

### Requirement: Actions для управления флагами расширений через capability
**Reason**: action capability слой удалён.
**Migration**: `extensions.set_flags` в manual operations registry.

### Requirement: extensions.set_flags поддерживает selective apply через params-based executor
**Reason**: перенос в `extensions-plan-apply` как template-based правило.
**Migration**: runtime input `flags_values` + `apply_mask`.

### Requirement: Presets для `extensions.set_flags` через `executor.fixed.apply_mask`
**Reason**: action-layer contract удалён.
**Migration**: selective state только в request.

### Requirement: Unified action exposure MUST хранить capability-specific binding contract
**Reason**: action exposure удалён.
**Migration**: binding хранится в template payload.

### Requirement: `extensions.set_flags` binding MUST валидироваться против схемы команды
**Reason**: перенос в template compatibility validation.
**Migration**: validation на template plan path.

### Requirement: `extensions.set_flags` action SHALL быть transport/binding-конфигурацией
**Reason**: action entity decommissioned.
**Migration**: transport/binding в template contract.
