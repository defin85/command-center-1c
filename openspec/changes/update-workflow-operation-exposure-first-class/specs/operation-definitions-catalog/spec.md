## ADDED Requirements
### Requirement: Template exposure payload MUST проходить strict runtime-contract validation до публикации
Система ДОЛЖНА (SHALL) проверять template exposure payload на write/publish path до перехода в `published`.

Минимальный обязательный runtime-контракт для `surface="template"`:
- `operation_type` должен быть непустой строкой;
- `template_data` должен быть JSON object;
- `operation_type` должен поддерживаться зарегистрированным runtime backend.

Эта валидация ДОЛЖНА (SHALL) выполняться единообразно в `validate`, `upsert`, `publish`, `sync-from-registry`.

#### Scenario: Публикация блокируется при невалидном template_data
- **GIVEN** exposure имеет `executor_payload.template_data` не-object значение
- **WHEN** выполняется publish template exposure
- **THEN** публикация отклоняется с `validation_errors`
- **AND** exposure не переходит в `published`

#### Scenario: Публикация блокируется при неподдерживаемом operation_type
- **GIVEN** exposure имеет `operation_type`, не поддерживаемый runtime backend registry
- **WHEN** выполняется publish template exposure
- **THEN** публикация отклоняется с детализированной ошибкой валидации
- **AND** runtime execution такого exposure невозможен до исправления

### Requirement: Operation exposure MUST иметь monotonic revision для deterministic bindings
Система ДОЛЖНА (SHALL) хранить `exposure_revision` как монотонно растущую версию exposure.

`exposure_revision` ДОЛЖЕН (SHALL) увеличиваться при изменениях exposure/definition, влияющих на runtime execution contract.

#### Scenario: exposure_revision увеличивается при изменении execution payload
- **GIVEN** template exposure опубликован с `exposure_revision=7`
- **WHEN** изменяется связанный execution payload через upsert
- **THEN** exposure получает `exposure_revision=8`
- **AND** старые pinned workflow binding могут быть обнаружены как drift

#### Scenario: API возвращает exposure_revision для template surface
- **WHEN** клиент запрашивает list/detail template exposures
- **THEN** ответ содержит `template_exposure_id` и `exposure_revision`
- **AND** этих данных достаточно для формирования `operation_ref(binding_mode="pinned_exposure")`
