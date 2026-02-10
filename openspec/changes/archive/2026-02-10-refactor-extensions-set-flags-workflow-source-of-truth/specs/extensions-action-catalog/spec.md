## MODIFIED Requirements
### Requirement: Presets для `extensions.set_flags` через `executor.fixed.apply_mask`
Система НЕ ДОЛЖНА (SHALL NOT) поддерживать presets selective apply для `extensions.set_flags` на уровне action catalog через `executor.fixed.apply_mask`.

#### Scenario: Exposure с preset apply_mask становится невалидным
- **GIVEN** action/exposure с `capability="extensions.set_flags"` содержит `executor.fixed.apply_mask` (или exposure-level `capability_config.apply_mask`)
- **WHEN** exposure проходит validate/publish
- **THEN** backend возвращает ошибку валидации по пути preset-поля
- **AND** exposure не публикуется в effective action catalog

### Requirement: extensions.set_flags поддерживает selective apply через params-based executor
Система ДОЛЖНА (SHALL) обеспечивать selective apply для reserved capability `extensions.set_flags` через params-based executor и runtime-токены `$flags.*`.

#### Scenario: selective apply использует runtime flags и request mask
- **GIVEN** action `extensions.set_flags` задаёт флаговые параметры через `$flags.*` в `executor.params`
- **WHEN** оператор запускает plan/apply с `flags_values` и `apply_mask`
- **THEN** backend применяет mask, удаляя невыбранные флаги из effective params
- **AND** если executor не params-based, backend возвращает ошибку конфигурации (fail-closed)

## ADDED Requirements
### Requirement: `extensions.set_flags` action SHALL быть transport/binding-конфигурацией
Система ДОЛЖНА (SHALL) хранить в action catalog для `extensions.set_flags` только transport/binding/safety конфигурацию и НЕ ДОЛЖНА (SHALL NOT) хранить runtime state (значения флагов и selective mask).

#### Scenario: Runtime state не хранится в exposure
- **GIVEN** staff редактирует action с `capability="extensions.set_flags"`
- **WHEN** action сохраняется
- **THEN** exposure не содержит capability-specific runtime state (`apply_mask`, fixed значения флагов)
- **AND** runtime state передаётся только в request/workflow input при запуске
