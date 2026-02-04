## MODIFIED Requirements

### Requirement: Зарезервированные capability валидируются fail-closed
Система ДОЛЖНА (SHALL) обеспечивать детерминизм для capability, которые backend понимает и использует для особой семантики (plan/apply, snapshot-marking).

#### Scenario: capability для применения флагов детерминирован и уникален
- **GIVEN** payload `ui.action_catalog` содержит два actions с `capability="extensions.set_flags"`
- **WHEN** staff пытается сохранить/обновить `ui.action_catalog`
- **THEN** система возвращает ошибку валидации (fail-closed) и не сохраняет payload

## ADDED Requirements

### Requirement: Actions для управления флагами расширений через capability
Система ДОЛЖНА (SHALL) поддерживать зарезервированный capability `extensions.set_flags` для применения policy флагов расширений к списку баз (bulk).

#### Scenario: Effective action catalog содержит apply-flags action только если executor валиден
- **GIVEN** в `ui.action_catalog` есть действие с `capability="extensions.set_flags"`
- **WHEN** executor этого действия невалиден (unknown command / missing workflow / запрещённый dangerous)
- **THEN** действие исключается из effective action catalog (fail-closed)

