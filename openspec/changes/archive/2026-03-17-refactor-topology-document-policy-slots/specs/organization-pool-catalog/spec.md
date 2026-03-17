## MODIFIED Requirements

### Requirement: Topology API MUST сохранять и возвращать metadata, достаточную для document-policy slot управления
Система ДОЛЖНА (SHALL) в mutating topology snapshot API сохранять `node.metadata` и `edge.metadata` без потери данных, достаточных для structural topology authoring и выбора publication slot, включая `edge.metadata.document_policy_key`.

Система ДОЛЖНА (SHALL) в read-path topology/graph API возвращать metadata узлов и рёбер, чтобы оператор мог безопасно редактировать structural topology и slot selectors без внешних инструментов.

Система НЕ ДОЛЖНА (SHALL NOT) принимать в штатном mutating authoring path legacy payload `edge.metadata.document_policy` или `pool.metadata.document_policy` после cutover.

#### Scenario: Оператор сохраняет `document_policy_key` в edge metadata и видит его в read-path
- **GIVEN** оператор отправляет topology snapshot с `edge.metadata.document_policy_key`
- **WHEN** snapshot сохраняется и затем читается через graph/topology endpoint
- **THEN** response содержит сохранённое `edge.metadata.document_policy_key`
- **AND** оператор может выполнить повторное редактирование без потери metadata

#### Scenario: Legacy document policy payload отклоняется на этапе topology save
- **GIVEN** оператор отправляет topology snapshot с `edge.metadata.document_policy` или `pool.metadata.document_policy`
- **WHEN** backend выполняет pre-persist validation
- **THEN** запрос отклоняется fail-closed валидационной ошибкой
- **AND** topology snapshot в БД не изменяется

### Requirement: Topology metadata contract MUST быть schema-stable для API и клиента
Система ДОЛЖНА (SHALL) публиковать в topology/graph API явные поля `node.metadata` и `edge.metadata` как часть стабильного read-model контракта, включая `edge.metadata.document_policy_key`.

Система ДОЛЖНА (SHALL) сохранять round-trip совместимость structural metadata: пользовательские поля metadata не теряются между mutating и последующим read-path вызовом.

#### Scenario: Round-trip topology metadata не теряет structural поля и slot selector
- **GIVEN** snapshot содержит `node.metadata`, `edge.metadata` и валидный `edge.metadata.document_policy_key`
- **WHEN** snapshot сохраняется и затем читается через graph/topology API
- **THEN** response содержит те же metadata структуры без потери пользовательских полей
- **AND** frontend может безопасно повторно отправить snapshot без реконструкции metadata вне API

### Requirement: Topology editor UI MUST поддерживать structural metadata и edge policy slots
Система ДОЛЖНА (SHALL) предоставлять в `/pools/catalog` topology editor для structural `node.metadata` / `edge.metadata` и явного выбора `edge.metadata.document_policy_key`.

Topology editor ДОЛЖЕН (SHALL) быть slot-oriented workspace, а не legacy document-policy editor.

Topology editor НЕ ДОЛЖЕН (SHALL NOT) оставаться shipped surface для inline `document_policy` authoring или import.

Для pool, зависящих от legacy topology policy, UI ДОЛЖЕН (SHALL) входить в blocking remediation state и направлять оператора в canonical decision/binding remediation flow.

Topology editor ДОЛЖЕН (SHALL) показывать status coverage для `document_policy_key` относительно выбранного canonical binding context, когда такой context доступен.

Coverage НЕ ДОЛЖЕН (SHALL NOT) отображаться как resolved, если canonical binding context не выбран и не может быть auto-resolved детерминированно.

#### Scenario: Новый edge получает slot selector без inline policy builder
- **GIVEN** оператор добавляет новый edge в topology editor
- **WHEN** UI рендерит controls для edge metadata
- **THEN** structural metadata и `document_policy_key` остаются доступны
- **AND** inline `document_policy` editor/import не предлагается как shipped action

#### Scenario: Editor показывает coverage selected slot относительно binding
- **GIVEN** оператор редактирует edge с `document_policy_key=sale`
- **AND** для выбранного pool доступен canonical binding с pinned slot `sale`
- **WHEN** UI рендерит edge editor
- **THEN** editor показывает, что slot coverage резолвится успешно
- **AND** оператор видит связь между topology edge и binding slot без перехода в raw JSON

#### Scenario: Coverage context ambiguous не маскируется как valid slot coverage
- **GIVEN** для одного `pool` существует несколько active bindings
- **AND** оператор не выбрал явный binding context для topology coverage
- **WHEN** UI рендерит edge editor
- **THEN** editor показывает, что coverage context ambiguous или unavailable
- **AND** не маркирует `document_policy_key` как resolved без детерминированного binding context

#### Scenario: Legacy topology переводит UI в remediation state
- **GIVEN** выбранный pool или topology snapshot содержит legacy `edge.metadata.document_policy` или `pool.metadata.document_policy`
- **WHEN** оператор открывает topology editor
- **THEN** UI показывает blocking remediation state
- **AND** normal topology save для legacy policy authoring недоступен
- **AND** оператор получает handoff к `/decisions` и binding remediation flow

## REMOVED Requirements

### Requirement: Topology document-policy mutating MUST валидироваться fail-closed до persistence
**Reason**: topology mutating path больше не принимает full `document_policy` payload как штатный authoring contract.

**Migration**: использовать `/decisions` для authoring concrete policy, `pool_workflow_binding.decisions[].slot_key` для pinning slot'ов и `edge.metadata.document_policy_key` для привязки slot к edge.

### Requirement: Topology mutating validation MUST проверять соответствие policy актуальному metadata catalog
**Reason**: metadata-aware validation полного `document_policy` переносится в decision-resource lifecycle и binding/runtime preview, а не остается в topology save path.

**Migration**: выполнять metadata validation в `/decisions` и в preview/run path после materialization binding slots.
