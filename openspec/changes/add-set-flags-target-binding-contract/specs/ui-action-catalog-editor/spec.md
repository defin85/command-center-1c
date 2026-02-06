# Spec Delta: ui-action-catalog-editor

## ADDED Requirements
### Requirement: Editor MUST поддерживать настройку `target_binding` для `extensions.set_flags`
Система ДОЛЖНА (SHALL) в staff-only Action Catalog editor отображать и сохранять поле `executor.target_binding.extension_name_param` для actions с `capability="extensions.set_flags"`.

#### Scenario: Staff задаёт binding в guided editor
- **GIVEN** staff редактирует action с `capability="extensions.set_flags"`
- **WHEN** staff открывает секцию capability-specific полей
- **THEN** UI показывает поле для `target_binding.extension_name_param`
- **AND** значение сохраняется в payload action catalog

### Requirement: Backend hints MUST включать schema для `target_binding` у `extensions.set_flags`
Система ДОЛЖНА (SHALL) возвращать в hints endpoint capability-schema для `executor.target_binding` у `extensions.set_flags`, чтобы UI не хардкодил структуру binding.

#### Scenario: Hints содержат target_binding schema
- **WHEN** staff вызывает endpoint hints для action catalog editor
- **THEN** capability `extensions.set_flags` содержит описание `target_binding.extension_name_param`
- **AND** UI строит поле по этим hints

#### Scenario: Ошибка target binding показывается с путём
- **GIVEN** staff сохраняет action с невалидным `target_binding.extension_name_param`
- **WHEN** backend возвращает ошибку валидации
- **THEN** UI отображает ошибку с путём до `executor.target_binding...`
- **AND** UI не выполняет silent fallback/автопочинку binding
