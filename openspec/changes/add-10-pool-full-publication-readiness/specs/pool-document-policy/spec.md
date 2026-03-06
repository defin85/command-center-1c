## ADDED Requirements
### Requirement: Document policy completeness profile MUST задавать обязательные реквизиты и табличные части per entity
Document policy MUST поддерживать декларативный completeness profile для каждого `entity_name`, включая обязательные реквизиты шапки и обязательные табличные части с минимально допустимым количеством строк.

#### Scenario: Неполный mapping блокирует compile document plan fail-closed
- **GIVEN** policy для edge содержит document chain с `entity_name`, требующим completeness profile
- **WHEN** compile path обнаруживает отсутствие обязательного поля или обязательной табличной части
- **THEN** runtime завершает compile fail-closed с machine-readable кодом ошибки
- **AND** публикация не выполняется

### Requirement: Режим `minimal_documents_full_payload` MUST минимизировать число документов без ослабления policy инвариантов
При активном профиле минимизации система MUST сокращать только количество документов, но не MUST удалять обязательные роли документов, обязательные связи и обязательные поля из policy.

#### Scenario: Минимизация не удаляет обязательный документ из цепочки
- **GIVEN** chain policy требует обязательный связанный документ
- **WHEN** включён режим `minimal_documents_full_payload`
- **THEN** compile path сохраняет обязательный документ в chain
- **AND** попытка исключить его приводит к fail-closed ошибке compile
