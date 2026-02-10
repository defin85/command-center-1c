## ADDED Requirements
### Requirement: `/operations` MUST использовать hardcoded manual contracts для ручных extensions запусков
Система ДОЛЖНА (SHALL) использовать в `/operations` фиксированный (hardcoded) реестр manual contracts для ручных atomic запусков extensions-операций.

Manual contract ДОЛЖЕН (SHALL) явно определять:
- `manual_contract_id`,
- schema runtime input,
- schema binding slots,
- правила совместимости с template exposure.

#### Scenario: Оператор выбирает ручной контракт из фиксированного списка
- **GIVEN** оператор открывает мастер ручной операции в `/operations`
- **WHEN** выбирает manual contract `extensions.set_flags.v1`
- **THEN** UI строит форму по hardcoded contract schema
- **AND** не запрашивает динамический список действий из `ui/action-catalog`

### Requirement: Manual contract execution MUST быть template-based
Система ДОЛЖНА (SHALL) выполнять manual запуск по связке `manual_contract_id + template_id + bindings + runtime input`.

#### Scenario: Пользователь задаёт bindings для slot-ов контракта
- **GIVEN** выбран manual contract с обязательными binding slots
- **WHEN** оператор маппит slot-ы на параметры template и заполняет runtime input
- **THEN** backend валидирует совместимость template и bindings
- **AND** при успехе строит execution plan только из template + runtime input

### Requirement: Manual contracts MUST быть fail-closed с preview перед запуском
Система ДОЛЖНА (SHALL) блокировать запуск при невалидном runtime input/bindings и ДОЛЖНА (SHALL) показывать preview (execution plan + binding provenance) до enqueue.

#### Scenario: Невалидный binding slot блокирует запуск
- **GIVEN** оператор указал binding к несуществующему параметру template
- **WHEN** выполняется preview/plan
- **THEN** backend возвращает `VALIDATION_ERROR`/`CONFIGURATION_ERROR`
- **AND** операция не ставится в очередь

#### Scenario: Валидный manual contract проходит через plan/apply pipeline
- **GIVEN** runtime input и bindings валидны
- **WHEN** оператор подтверждает запуск после preview
- **THEN** UI выполняет планирование и запуск через единый execution pipeline
- **AND** прогресс отслеживается в `/operations`

