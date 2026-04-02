## MODIFIED Requirements

### Requirement: Publication payload MUST использовать resolved master-data refs из binding artifact
Система ДОЛЖНА (SHALL) при `pool.publication_odata` формировать документный payload на основе `master_data_binding_artifact` и передавать в OData только resolved ссылки на сущности ИБ (`Ref_Key`/эквивалент), а не свободные строковые значения.

Это правило ДОЛЖНО (SHALL) распространяться на canonical refs для:
- `Item`;
- `Party`;
- `Contract`;
- `TaxProfile`;
- `GLAccount`, если `document_policy` использует canonical account tokens в header или table-part fields.

Система НЕ ДОЛЖНА (SHALL NOT) выполнять implicit free-text lookup reusable data в момент OData side effects, если required binding отсутствует.

#### Scenario: Публикация использует resolved refs для номенклатуры, контрагента и account fields
- **GIVEN** `master_data_binding_artifact` содержит resolved ссылки для `Item`, `Party` и `GLAccount` в target ИБ
- **WHEN** worker исполняет `pool.publication_odata`
- **THEN** в OData payload используются соответствующие resolved refs
- **AND** account fields документа не опираются на raw GUID literals или lookup по textual account code

#### Scenario: Несовместимый или отсутствующий account binding блокирует publication до side effects
- **GIVEN** `document_policy` использует canonical account token
- **AND** target database не имеет compatible `GLAccount` binding для required field
- **WHEN** publication compile/gate подготавливает payload
- **THEN** выполнение завершается fail-closed до OData create/post
- **AND** diagnostics указывает проблему reusable account coverage, а не позднюю transport-level ошибку
