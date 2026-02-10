## ADDED Requirements
### Requirement: Completion MUST резолвить mapping строго по pinned reference
Система ДОЛЖНА (SHALL) использовать для completion normalization только mapping, зафиксированный в metadata (`mapping_spec_id`, `mapping_spec_version`), без неявного переключения на текущее состояние mapping.

#### Scenario: Pinned mapping version расходится с текущим опубликованным mapping
- **GIVEN** план создан с pinned `mapping_spec_version=A`
- **AND** к моменту completion в системе опубликована версия `B`
- **WHEN** выполняется completion по данному плану
- **THEN** normalization использует версию `A`
- **AND** canonical snapshot детерминирован относительно metadata плана

#### Scenario: Pinned mapping недоступен на completion
- **GIVEN** metadata содержит `mapping_spec_ref`, но соответствующий mapping отсутствует/недоступен
- **WHEN** выполняется completion
- **THEN** система сохраняет raw snapshot и diagnostics о невозможности применить pinned mapping
- **AND** не подменяет mapping на произвольный runtime fallback

### Requirement: Completion MUST сохранять diagnostics при нарушении result contract
Система ДОЛЖНА (SHALL) валидировать canonical payload против `result_contract` и сохранять diagnostics при несоответствии, не теряя append-only snapshot историю.

#### Scenario: Canonical payload не проходит валидацию result contract
- **GIVEN** metadata содержит `result_contract`
- **WHEN** completion формирует canonical payload, который нарушает contract schema
- **THEN** snapshot сохраняется вместе с validation diagnostics
- **AND** raw payload остаётся доступным для аудита и разбора
