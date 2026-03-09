## ADDED Requirements
### Requirement: Pool catalog workflow bindings MUST использовать isolated binding workspace и canonical CRUD
Система ДОЛЖНА (SHALL) управлять workflow bindings на `/pools/catalog` через dedicated binding workspace и dedicated binding endpoints, backed by the same canonical store, который использует runtime resolution.

Pool upsert contract НЕ ДОЛЖЕН (SHALL NOT) нести canonical binding payload и НЕ ДОЛЖЕН (SHALL NOT) переписывать binding state как side effect редактирования базовых полей пула.

UI ДОЛЖЕН (SHALL) разделять:
- mutating операции над базовыми полями `pool`;
- mutating операции над `pool_workflow_binding`.

#### Scenario: Сохранение базовых полей пула не переписывает workflow bindings
- **GIVEN** оператор редактирует `code` или `name` пула в `/pools/catalog`
- **AND** у пула уже есть active workflow bindings
- **WHEN** оператор сохраняет только базовые поля пула
- **THEN** UI использует pool upsert path без canonical binding payload
- **AND** существующие workflow bindings не теряются и не переписываются

#### Scenario: Binding editor использует тот же canonical CRUD, что и runtime
- **GIVEN** оператор добавляет или удаляет workflow binding в `/pools/catalog`
- **WHEN** изменение сохраняется
- **THEN** UI обращается к dedicated binding CRUD endpoint'ам
- **AND** следующий create-run/read-model видит это же изменение без дополнительного metadata sync шага
