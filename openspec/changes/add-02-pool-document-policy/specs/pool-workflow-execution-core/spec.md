## ADDED Requirements
### Requirement: Pool runtime MUST компилировать document plan перед publication step
Система ДОЛЖНА (SHALL) перед шагом `pool.publication_odata` формировать `document_plan_artifact` на основе runtime distribution artifact, active topology version и валидной `document_policy`.

Система ДОЛЖНА (SHALL) передавать в publication step только этот artifact как source-of-truth для create-run path.

#### Scenario: Publication step получает document plan из runtime compile
- **GIVEN** distribution шаги завершились успешно и policy валидна
- **WHEN** runtime переходит к pre-publication стадии
- **THEN** в execution context сохраняется `document_plan_artifact`
- **AND** publication step использует artifact вместо произвольного raw payload

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
