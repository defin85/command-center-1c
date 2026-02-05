## MODIFIED Requirements

### Requirement: Зарезервированные capability валидируются fail-closed
Система ДОЛЖНА (SHALL) обеспечивать детерминизм для reserved capability, которые backend понимает и использует для особой семантики (plan/apply, snapshot-marking), но НЕ ДОЛЖНА (SHALL NOT) требовать уникальности `capability` на уровне update-time валидации `ui.action_catalog`.

#### Scenario: Дубликаты reserved capability допускаются, но требуют детерминизма на запуске
- **GIVEN** в `ui.action_catalog` есть два actions с `capability="extensions.set_flags"`
- **WHEN** UI/клиент вызывает reserved endpoint без `action_id` (только по `capability`)
- **THEN** backend возвращает ошибку ambiguity и не выполняет действие
- **AND** error message содержит список candidate `action.id`

## ADDED Requirements

### Requirement: Presets для `extensions.set_flags` через `executor.fixed.apply_mask`
Система ДОЛЖНА (SHALL) поддерживать presets selective apply для `extensions.set_flags` на уровне action catalog через `executor.fixed.apply_mask`.

#### Scenario: apply_mask берётся из action preset по умолчанию
- **GIVEN** action с `capability="extensions.set_flags"` содержит `executor.fixed.apply_mask`, выбирающий только один флаг (например `active=true`, остальные `false`)
- **WHEN** UI вызывает plan без `apply_mask`, но с `action_id` этого action
- **THEN** backend использует `executor.fixed.apply_mask` как effective mask
- **AND** apply изменяет только выбранный флаг

