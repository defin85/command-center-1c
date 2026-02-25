## ADDED Requirements
### Requirement: Pool runtime MUST компилировать document plan перед publication step
Система ДОЛЖНА (SHALL) перед шагом `pool.publication_odata` формировать `document_plan_artifact` на основе runtime distribution artifact, active topology version и валидной `document_policy`.

Система ДОЛЖНА (SHALL) передавать в publication step только этот artifact как source-of-truth для create-run path.

#### Scenario: Publication step получает document plan из runtime compile
- **GIVEN** distribution шаги завершились успешно и policy валидна
- **WHEN** runtime переходит к pre-publication стадии
- **THEN** в execution context сохраняется `document_plan_artifact`
- **AND** publication step использует artifact вместо произвольного raw payload

### Requirement: Document plan compile MUST принимать distribution_artifact.v1 как обязательный upstream контракт
Система ДОЛЖНА (SHALL) выполнять compile `document_plan_artifact` только от валидного `distribution_artifact.v1`, сохраненного в execution context create-run path.

Система ДОЛЖНА (SHALL) валидировать минимальный обязательный набор полей `distribution_artifact.v1` перед downstream compile:
- `version`;
- `topology_version_ref`;
- `node_totals[]`;
- `edge_allocations[]`;
- `coverage`;
- `balance`;
- `input_provenance`.

Система НЕ ДОЛЖНА (SHALL NOT) использовать raw `run_input` как authoritative источник распределенных сумм для compile document plan.

#### Scenario: Compile document plan получает распределение только из runtime artifact
- **GIVEN** execution context содержит валидный `distribution_artifact.v1`
- **WHEN** runtime запускает compile `document_plan_artifact`
- **THEN** вход распределения берется из сохраненного artifact
- **AND** значения из raw `run_input` не используются как источник распределенных сумм

#### Scenario: Неполный upstream artifact блокирует compile document plan fail-closed
- **GIVEN** в execution context отсутствует `distribution_artifact.v1` или отсутствуют обязательные поля контракта
- **WHEN** runtime пытается выполнить compile `document_plan_artifact`
- **THEN** compile завершается fail-closed до publication step
- **AND** execution diagnostics содержит machine-readable код нарушения artifact-контракта

#### Scenario: Попытка bypass через raw run_input artifact-поля отклоняется
- **GIVEN** оператор/клиент передал в `run_input` поля, имитирующие runtime artifacts (`distribution_artifact`/`document_plan_artifact`/`pool_runtime_*`)
- **WHEN** create-run path формирует execution context и downstream compile вход
- **THEN** эти raw поля не используются как source-of-truth для compile
- **AND** downstream compile читает только валидный artifact из execution context contract key

### Requirement: Document plan artifact MUST публиковаться как downstream handoff контракт для atomic compiler
Система ДОЛЖНА (SHALL) сохранять `document_plan_artifact.v1` в execution context как downstream handoff-контракт для atomic workflow compiler из change `refactor-03-unify-platform-execution-runtime`.

Система НЕ ДОЛЖНА (SHALL NOT) требовать повторного policy compile на стороне atomic compiler, если валидный `document_plan_artifact.v1` уже сохранен.

#### Scenario: Downstream atomic compiler потребляет готовый document_plan_artifact.v1
- **GIVEN** runtime успешно сохранил `document_plan_artifact.v1` после compile policy
- **WHEN** atomic workflow compiler (Track B, `refactor-03`) строит execution graph
- **THEN** compiler использует сохраненный `document_plan_artifact.v1` как входной контракт
- **AND** повторная policy-компиляция в atomic compiler не выполняется

### Requirement: Runtime MUST блокировать publication fail-closed при policy compile errors
Система ДОЛЖНА (SHALL) завершать execution fail-closed до `pool.publication_odata`, если policy отсутствует там, где обязательна, policy невалидна, compile chain/mapping завершился ошибкой или нарушен required invoice rule.

#### Scenario: Ошибка compile policy блокирует переход к публикации
- **GIVEN** runtime не смог построить корректный `document_plan_artifact`
- **WHEN** выполняется transition к `pool.publication_odata`
- **THEN** publication step не запускается
- **AND** execution diagnostics содержит machine-readable policy error code

### Requirement: Retry path MUST использовать persisted document plan artifact
Система ДОЛЖНА (SHALL) при retry publication использовать persisted `document_plan_artifact` исходного run как базовый источник структуры документов и link rules.

Система НЕ ДОЛЖНА (SHALL NOT) требовать от оператора повторной передачи полного произвольного payload документов для восстановления chain semantics.

#### Scenario: Retry переиспользует persisted chain-план
- **GIVEN** run завершился `partial_success` и содержит persisted `document_plan_artifact`
- **WHEN** оператор инициирует retry failed targets
- **THEN** runtime формирует retry payload из persisted artifact
- **AND** успешные документы цепочки не дублируются
