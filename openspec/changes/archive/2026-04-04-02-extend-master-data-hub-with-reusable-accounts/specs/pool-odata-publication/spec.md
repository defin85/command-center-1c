## ADDED Requirements

### Requirement: Publication payload MUST использовать resolved GLAccount refs из binding artifact
Система ДОЛЖНА (SHALL) при `pool.publication_odata` формировать account fields документа через reusable-data binding artifact и передавать в OData только target-local resolved refs (`Ref_Key` или эквивалент), а не свободные string literals.

Система НЕ ДОЛЖНА (SHALL NOT) использовать cross-infobase `Ref_Key` reuse или implicit lookup по account code в момент OData side effects.

#### Scenario: Account field публикации использует resolved target-local ref
- **GIVEN** `document_policy` использует canonical `GLAccount` token
- **AND** target ИБ имеет валидный `GLAccount` binding
- **WHEN** worker подготавливает publication payload
- **THEN** account field получает resolved target-local ref из binding artifact
- **AND** payload не содержит свободный account code вместо OData reference

#### Scenario: Отсутствие required account binding блокирует OData side effects
- **GIVEN** policy требует canonical `GLAccount`, но для target ИБ binding отсутствует
- **WHEN** система формирует publication payload
- **THEN** шаг завершается fail-closed до OData create/post
- **AND** diagnostics указывает на missing reusable account binding
