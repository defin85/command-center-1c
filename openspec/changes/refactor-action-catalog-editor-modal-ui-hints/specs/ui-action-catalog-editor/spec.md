## MODIFIED Requirements

### Requirement: Поддержка executor kinds
Система ДОЛЖНА (SHALL) поддерживать в редакторе executor kinds `ibcmd_cli`, `designer_cli` и `workflow`, а capability‑специфичные поля НЕ ДОЛЖНЫ (SHALL NOT) масштабироваться через хардкод условных веток в UI.

#### Scenario: Capability fixed UI определяется backend hints
- **GIVEN** staff редактирует action с `capability="extensions.set_flags"`
- **WHEN** UI отображает секцию fixed/presets
- **THEN** UI строит поля на основе backend-provided hints (schema/uiSchema), а не через `if capability === ...`

## ADDED Requirements

### Requirement: Staff-only endpoint для Action Catalog editor hints
Система ДОЛЖНА (SHALL) предоставить staff-only endpoint, который возвращает UI hints для capability (минимум: `executor.fixed.*`) в виде JSON Schema + uiSchema.

#### Scenario: Hints endpoint доступен только staff
- **WHEN** non-staff вызывает hints endpoint
- **THEN** доступ запрещён (403)

#### Scenario: Hints содержат fixed schema для extensions.set_flags
- **WHEN** staff вызывает hints endpoint
- **THEN** ответ содержит capability `extensions.set_flags` с описанием `fixed.apply_mask`

