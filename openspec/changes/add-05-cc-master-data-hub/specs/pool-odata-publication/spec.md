## ADDED Requirements
### Requirement: Publication payload MUST использовать resolved master-data refs из binding artifact
Система ДОЛЖНА (SHALL) при `pool.publication_odata` формировать документный payload на основе `master_data_binding_artifact` и передавать в OData только resolved ссылки на сущности ИБ (`Ref_Key`/эквивалент), а не свободные строковые значения.

Система НЕ ДОЛЖНА (SHALL NOT) выполнять implicit free-text lookup мастер-данных в момент OData side effects, если required binding отсутствует.

#### Scenario: Публикация использует resolved refs для номенклатуры и контрагента
- **GIVEN** `master_data_binding_artifact` содержит resolved ссылки для `Item` и `Party` в target ИБ
- **WHEN** worker исполняет `pool.publication_odata`
- **THEN** в OData payload используются соответствующие resolved refs
- **AND** публикация не опирается на lookup по текстовым наименованиям

#### Scenario: Отсутствие required binding блокирует OData side effects
- **GIVEN** для required сущности в target ИБ отсутствует resolved binding в artifact
- **WHEN** worker подготавливает payload публикации
- **THEN** шаг завершается fail-closed до OData create/post
- **AND** diagnostics содержит machine-readable код `MASTER_DATA_BINDING_CONFLICT` или `MASTER_DATA_ENTITY_NOT_FOUND`
