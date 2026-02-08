# Spec Delta: operation-definitions-catalog

## ADDED Requirements
### Requirement: Unified persistent contract MUST разделять definition и exposure
Система ДОЛЖНА (SHALL) хранить исполняемые конфигурации в двух связанных слоях:
- `operation_definition` — canonical execution payload,
- `operation_exposure` — surface-specific публикация (`template` или `action_catalog`).

#### Scenario: Один definition используется несколькими exposure
- **GIVEN** есть два объекта публикации (template и action) с идентичным execution payload
- **WHEN** данные сохраняются в unified persistent store
- **THEN** оба exposure ссылаются на один `operation_definition`
- **AND** дублирование execution payload не создаётся

### Requirement: Unified contract MUST поддерживать capability-specific config
Система ДОЛЖНА (SHALL) хранить capability-specific поля в exposure-уровне (`capability_config`) без смешивания с canonical execution payload definition.

#### Scenario: `extensions.set_flags` хранит target binding в exposure
- **GIVEN** action exposure с `capability="extensions.set_flags"`
- **WHEN** exposure проходит валидацию
- **THEN** `capability_config.target_binding.extension_name_param` обязателен
- **AND** exposure без этого поля получает fail-closed статус `invalid`

### Requirement: Migration MUST быть обратимо-наблюдаемой и fail-closed
Система ДОЛЖНА (SHALL) выполнять миграцию из legacy источников в unified store с журналом проблем и без публикации невалидных exposure.

#### Scenario: Невалидный legacy объект не публикуется
- **GIVEN** legacy запись не проходит unified validation
- **WHEN** выполняется backfill
- **THEN** создаётся запись в migration issues
- **AND** соответствующий exposure НЕ публикуется в effective read model

### Requirement: Unified contract MUST иметь явный API для definitions/exposures
Система ДОЛЖНА (SHALL) предоставить явный API-контур для работы с unified persistent моделью:
- list/get definitions,
- list/upsert/publish exposures,
- dry-run validate,
- list migration issues.

#### Scenario: Staff получает валидацию exposure до публикации
- **GIVEN** staff готовит новый action/template exposure
- **WHEN** вызывается endpoint dry-run validate
- **THEN** API возвращает детальные ошибки с путями полей
- **AND** exposure не публикуется автоматически без явного publish шага
