## MODIFIED Requirements
### Requirement: Editor hints MUST включать `target_binding` schema для `extensions.set_flags`
Система ДОЛЖНА (SHALL) возвращать в editor hints для `extensions.set_flags` schema binding-поля (`target_binding.extension_name_param`) и НЕ ДОЛЖНА (SHALL NOT) возвращать capability preset schema для `apply_mask`.

#### Scenario: Hints для set_flags не содержат preset apply_mask
- **GIVEN** staff открывает editor action catalog
- **WHEN** UI получает hints для capability `extensions.set_flags`
- **THEN** hints содержат `target_binding` schema
- **AND** hints не содержат capability fixed schema для `apply_mask`

## ADDED Requirements
### Requirement: Editor SHALL скрывать runtime-поля selective apply для `extensions.set_flags`
Система ДОЛЖНА (SHALL) в UI-редакторе action catalog скрывать/запрещать capability-specific runtime поля selective apply (`apply_mask`, fixed значения флагов) для `extensions.set_flags`.

#### Scenario: Staff не может задать preset mask в editor
- **GIVEN** staff редактирует action с `capability="extensions.set_flags"`
- **WHEN** открыта вкладка safety/fixed
- **THEN** UI не показывает control для `apply_mask (preset)`
- **AND** сохранённый payload не содержит `executor.fixed.apply_mask`

### Requirement: Editor SHALL показывать подсказку про runtime source `$flags.*`
Система ДОЛЖНА (SHALL) в editor UI явно объяснять, что значения флагов для `extensions.set_flags` задаются при запуске (workflow/request), а не внутри action exposure.

#### Scenario: Staff видит явную подсказку источника значений
- **WHEN** staff редактирует action `extensions.set_flags`
- **THEN** UI показывает helper text о runtime source (`$flags.*`)
- **AND** это снижает риск неверной конфигурации preset внутри action
