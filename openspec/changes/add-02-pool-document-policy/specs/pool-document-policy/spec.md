## ADDED Requirements
### Requirement: Document policy MUST быть декларативным и пользовательски управляемым в tenant scope
Система ДОЛЖНА (SHALL) поддерживать versioned domain contract `document_policy.v1`, в котором пользователь описывает правила формирования документов на рёбрах пула без изменения backend кода.

Система ДОЛЖНА (SHALL) поддерживать хранение document-policy в topology edge metadata и использовать этот contract как source-of-truth для построения публикационного плана документов.

Минимальный обязательный набор полей `document_policy.v1`:
- `version = "document_policy.v1"`;
- `chains[]` (ordered);
- `chains[].chain_id`;
- `chains[].documents[]` (ordered);
- `chains[].documents[].document_id`;
- `chains[].documents[].entity_name`;
- `chains[].documents[].document_role`;
- `chains[].documents[].field_mapping` (object);
- `chains[].documents[].table_parts_mapping` (object);
- `chains[].documents[].link_rules` (object);
- `chains[].documents[].invoice_mode` (`optional|required`);
- `chains[].documents[].link_to` (optional).

#### Scenario: Оператор задаёт policy для ребра без backend hardcode
- **GIVEN** оператор редактирует topology snapshot пула
- **WHEN** для ребра задаётся `metadata.document_policy` с `version=document_policy.v1`
- **THEN** backend принимает policy только при успешной schema validation
- **AND** policy сохраняется как часть topology версии в tenant scope

### Requirement: Document policy mapping MUST поддерживать реквизиты и табличные части
Система ДОЛЖНА (SHALL) поддерживать в policy явный mapping реквизитов документа (`field_mapping`) и табличных частей (`table_parts_mapping`).

Система НЕ ДОЛЖНА (SHALL NOT) требовать backend hardcode под каждый tenant-вариант заполнения реквизитов/табличных частей, если variant укладывается в policy contract `v1`.

#### Scenario: Policy задаёт заполнение реквизитов и строк табличной части
- **GIVEN** policy содержит mapping реквизитов документа и mapping табличной части
- **WHEN** runtime компилирует документный план
- **THEN** итоговый payload документа включает поля и табличные строки по policy mapping
- **AND** отсутствие required mapping вызывает fail-closed validation error

### Requirement: Document policy MUST поддерживать цепочки документов и обязательную связанную счёт-фактуру
Система ДОЛЖНА (SHALL) поддерживать ordered document chains (`documents[]`) в рамках одного edge rule, включая per-document `entity_name` и link rules между документами цепочки.

Система ДОЛЖНА (SHALL) поддерживать `invoice_mode=required` для policy, где связанная счёт-фактура обязательна.

#### Scenario: Для sale/purchase chain создаются документы и связанная счёт-фактура
- **GIVEN** policy содержит chain с `Реализация` и `invoice_mode=required` для связанной счёт-фактуры
- **WHEN** runtime формирует `document_plan_artifact`
- **THEN** план включает и основной документ, и связанную счёт-фактуру в корректном порядке
- **AND** link rules между документами цепочки зафиксированы в artifact

#### Scenario: Отсутствие required счёт-фактуры блокирует публикацию fail-closed
- **GIVEN** policy требует `invoice_mode=required`
- **AND** по итогам compile отсутствует корректно сформированный invoice step
- **WHEN** runtime выполняет pre-publication gate
- **THEN** publication блокируется
- **AND** возвращается machine-readable код `POOL_DOCUMENT_POLICY_MISSING_REQUIRED_INVOICE`

### Requirement: Runtime MUST строить детерминированный document plan artifact из policy
Система ДОЛЖНА (SHALL) компилировать `document_plan_artifact` детерминированно из active topology version за период run, distribution artifact run и `document_policy`.

Система ДОЛЖНА (SHALL) использовать этот artifact как source-of-truth для create-run publication и retry semantics.

Минимальный обязательный набор полей `document_plan_artifact.v1`:
- `version`;
- `run_id`;
- `distribution_artifact_ref`;
- `topology_version_ref`;
- `policy_refs[]`;
- `targets[].chains[].documents[]` с `entity_name`, `document_role`, `field_mapping`, `table_parts_mapping`, `link_rules`, `invoice_mode`, `idempotency_key`;
- `compile_summary`.

Система НЕ ДОЛЖНА (SHALL NOT) формировать create-run publication chain напрямую из raw `run_input`, если `document_plan_artifact.v1` успешно построен и сохранён.

#### Scenario: Одинаковый вход и policy дают идентичный document plan artifact
- **GIVEN** одинаковые distribution artifact, topology version и document-policy
- **WHEN** runtime выполняет compile document plan повторно
- **THEN** структура и порядок `document_plan_artifact` совпадают
- **AND** idempotency ключи документов совпадают

#### Scenario: Неполный document plan artifact блокирует публикацию
- **GIVEN** runtime сформировал artifact без одного из обязательных полей `document_plan_artifact.v1`
- **WHEN** выполняется pre-publication gate
- **THEN** run завершается fail-closed до OData side effects
- **AND** diagnostics содержит machine-readable код нарушения artifact-контракта

### Requirement: Document plan artifact MUST быть downstream execution-контрактом для атомарного workflow compile
Система ДОЛЖНА (SHALL) публиковать versioned `document_plan_artifact` как downstream input-контракт для атомарного workflow compiler.

Система НЕ ДОЛЖНА (SHALL NOT) требовать повторного compile policy на этапе атомарного execution graph compile.

#### Scenario: Atomic workflow compiler получает готовый document plan artifact
- **GIVEN** `document_plan_artifact.v1` сохранён после compile policy
- **WHEN** downstream runtime компилирует атомарный workflow graph
- **THEN** compiler использует сохранённый artifact без повторной policy-компиляции
- **AND** шаги документа/счёт-фактуры соответствуют сохранённому плану

### Requirement: Document policy errors MUST быть machine-readable и диагностируемыми
Система ДОЛЖНА (SHALL) возвращать стабильные machine-readable коды для policy-ошибок до OData side effects.

Минимальный набор кодов:
- `POOL_DOCUMENT_POLICY_INVALID`
- `POOL_DOCUMENT_POLICY_CHAIN_INVALID`
- `POOL_DOCUMENT_POLICY_MAPPING_INVALID`
- `POOL_DOCUMENT_POLICY_MISSING_REQUIRED_INVOICE`

#### Scenario: Невалидный mapping policy возвращает стабильный код ошибки
- **GIVEN** policy содержит некорректный mapping реквизита или табличной части
- **WHEN** runtime выполняет policy validation/compile
- **THEN** run останавливается fail-closed до публикации
- **AND** diagnostics содержит machine-readable код `POOL_DOCUMENT_POLICY_MAPPING_INVALID`

#### Scenario: Невалидная структура цепочки возвращает стабильный код ошибки
- **GIVEN** policy содержит некорректную структуру chain (например, duplicate `chain_id` или invalid `invoice_mode`)
- **WHEN** runtime выполняет policy validation/compile
- **THEN** run останавливается fail-closed до публикации
- **AND** diagnostics содержит machine-readable код `POOL_DOCUMENT_POLICY_CHAIN_INVALID`

### Requirement: Migration path MUST быть backward-compatible для run-ов без document policy
Система ДОЛЖНА (SHALL) поддерживать переходный режим, в котором существующие run-ы без `metadata.document_policy` продолжают выполняться по legacy create-run path без policy compile ошибки.

Система НЕ ДОЛЖНА (SHALL NOT) требовать retroactive миграции исторических run-ов или topology версий только для сохранения текущего поведения публикации.

#### Scenario: Legacy run без document policy выполняется без policy compile шага
- **GIVEN** run создан для topology версии, где отсутствует `edge.metadata.document_policy`
- **WHEN** runtime выполняет distribution/reconciliation create-run path
- **THEN** run не завершается ошибкой policy-missing
- **AND** legacy publication payload семантика сохраняется до включения policy
