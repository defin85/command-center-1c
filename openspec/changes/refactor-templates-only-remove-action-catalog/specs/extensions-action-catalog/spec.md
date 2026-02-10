## ADDED Requirements
### Requirement: Extensions Action Catalog MUST быть decommissioned
Система НЕ ДОЛЖНА (SHALL NOT) предоставлять runtime или management контракт Action Catalog для домена extensions.

#### Scenario: Action Catalog endpoint для extensions недоступен
- **WHEN** клиент вызывает legacy endpoint `GET /api/v2/ui/action-catalog/`
- **THEN** endpoint возвращает unsupported (`404`/`410` по целевому контракту)
- **AND** runtime execution `extensions.*` через action catalog не выполняется

#### Scenario: Action-catalog exposure не используется в execution
- **GIVEN** в хранилище остаются legacy записи `surface=action_catalog`
- **WHEN** пользователь запускает ручную operations flow для `extensions.*`
- **THEN** система не читает эти записи для runtime-резолва
- **AND** execution строится только из templates

## REMOVED Requirements
### Requirement: RuntimeSetting для каталога действий расширений
**Reason**: capability decommissioned.
**Migration**: использовать templates-only execution контракты.

### Requirement: API для effective action catalog
**Reason**: endpoint удаляется из поддерживаемого контракта.
**Migration**: использовать templates-based list/plan/apply.

### Requirement: Action executors
**Reason**: executor semantics переносятся в template-based execution.
**Migration**: настраивать executors в templates.

### Requirement: Deactivate и delete — разные действия
**Reason**: action-catalog action model удаляется.
**Migration**: фиксировать ручные операции через templates/manual contract.

### Requirement: Bulk execution
**Reason**: bulk execution больше не управляется action catalog.
**Migration**: использовать template-based plan/apply bulk path.

### Requirement: Fail-closed validation
**Reason**: validation переносится в template-based contracts.
**Migration**: проверять template compatibility и runtime input.

### Requirement: Snapshot расширений в Postgres
**Reason**: требование не относится к decommissioned action-catalog capability.
**Migration**: требования snapshot остаются в capabilities `extensions-overview`/`extensions-plan-apply`.

### Requirement: Staff может увидеть plan/provenance при запуске действия расширений
**Reason**: action-catalog launch flow удаляется.
**Migration**: preview/provenance показывается в template-based manual flow.

### Requirement: User-friendly ошибки preflight для действий расширений
**Reason**: action-catalog launch flow удаляется.
**Migration**: ошибки остаются в template-based plan/apply UX.

### Requirement: Семантика extensions действий задаётся capability, а не id
**Reason**: action entity (`id/capability` в action catalog) деcommissioned.
**Migration**: семантика ручной операции задаётся manual contract + template compatibility.

### Requirement: Зарезервированные capability валидируются fail-closed
**Reason**: reserved capability логика action-catalog больше не используется.
**Migration**: fail-closed валидация переносится в template-based contracts.

### Requirement: Actions для управления флагами расширений через capability
**Reason**: action catalog decommissioned.
**Migration**: `extensions.set_flags` выполняется через `template_id`.

### Requirement: extensions.set_flags поддерживает selective apply через params-based executor
**Reason**: требование переносится в `extensions-plan-apply` как template-based execution правило.
**Migration**: selective apply задаётся runtime input `flags_values` + `apply_mask`.

### Requirement: Presets для `extensions.set_flags` через `executor.fixed.apply_mask`
**Reason**: action-layer preset contract удаляется вместе с capability.
**Migration**: runtime selective state передаётся только в request.

### Requirement: Unified action exposure MUST хранить capability-specific binding contract
**Reason**: action exposure decommissioned.
**Migration**: binding/compatibility хранится и валидируется в template execution contract.

### Requirement: `extensions.set_flags` binding MUST валидироваться против схемы команды
**Reason**: перенос binding validation в template-based path.
**Migration**: валидация выполняется для selected template до plan/apply.

### Requirement: `extensions.set_flags` action SHALL быть transport/binding-конфигурацией
**Reason**: action entity удаляется.
**Migration**: runtime/source contract определяется template payload + runtime input.
