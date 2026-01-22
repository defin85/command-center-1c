## MODIFIED Requirements
### Requirement: Канонический argv включает driver options + command params
Система ДОЛЖНА (SHALL) формировать канонический `argv[]` (и `argv_masked[]`) на стороне API до постановки операции в очередь, включая:
1) driver-level connection options (`connection.*`)
2) command-level params (`params`)
3) `additional_args` после нормализации

Система ДОЛЖНА (SHALL) дополнительно формировать `bindings[]` (Binding Provenance), описывающий происхождение каждого добавленного/нормализованного элемента `argv` и его источник (request/driver catalog/action catalog/database/env), без хранения секретов.

#### Scenario: Preview отражает provenance для argv
- **WHEN** staff делает preview для schema-driven команды с заполненными `connection`/`params`/`additional_args`
- **THEN** preview возвращает `argv_masked[]` и `bindings[]`, где видно, какие элементы пришли из `connection`, какие из `params`, а какие из `additional_args`/нормализации

