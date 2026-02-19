## ADDED Requirements
### Requirement: Topology API MUST сохранять и возвращать metadata, достаточную для document-policy управления
Система ДОЛЖНА (SHALL) в mutating topology snapshot API сохранять `node.metadata` и `edge.metadata` без потери данных, включая `edge.metadata.document_policy`.

Система ДОЛЖНА (SHALL) в read-path topology/graph API возвращать metadata узлов и рёбер, чтобы оператор мог безопасно редактировать document-policy без внешних инструментов.

#### Scenario: Оператор сохраняет document-policy в edge metadata и видит его в read-path
- **GIVEN** оператор отправляет topology snapshot с `edge.metadata.document_policy`
- **WHEN** snapshot сохраняется и затем читается через graph/topology endpoint
- **THEN** response содержит сохранённое `edge.metadata.document_policy`
- **AND** оператор может выполнить повторное редактирование без потери metadata

### Requirement: Topology document-policy mutating MUST валидироваться fail-closed до persistence
Система ДОЛЖНА (SHALL) валидировать `edge.metadata.document_policy` на соответствие contract version (`document_policy.v1`) в момент topology mutating запроса.

Система НЕ ДОЛЖНА (SHALL NOT) сохранять snapshot с невалидной policy.

#### Scenario: Невалидная policy отклоняется на этапе topology upsert
- **GIVEN** оператор отправляет snapshot с `document_policy`, нарушающим contract schema
- **WHEN** backend выполняет pre-persist validation
- **THEN** запрос отклоняется валидационной ошибкой
- **AND** topology snapshot в БД остаётся неизменным
