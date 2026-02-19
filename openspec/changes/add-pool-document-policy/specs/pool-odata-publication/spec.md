## ADDED Requirements
### Requirement: Publication transport MUST поддерживать chain payload с per-document entity
Система ДОЛЖНА (SHALL) принимать publication payload, где для каждой target database передаётся ordered chain документов с per-document `entity_name`, payload данными и link metadata.

Система ДОЛЖНА (SHALL) сохранять backward compatibility для legacy single-entity payload на переходном этапе.

#### Scenario: Worker публикует chain документов разных entity в одной target database
- **GIVEN** publication payload содержит ordered chain из документов разных `entity_name`
- **WHEN** worker исполняет `pool.publication_odata`
- **THEN** документы создаются/проводятся в порядке chain
- **AND** результат публикации содержит попытки и статусы по документам цепочки

### Requirement: Publication MUST обеспечивать обязательную связанную счёт-фактуру по policy
Система ДОЛЖНА (SHALL) при `invoice_mode=required` публиковать связанную счёт-фактуру как часть той же цепочки и проверять корректность linkage с базовым документом.

Система НЕ ДОЛЖНА (SHALL NOT) завершать публикацию success для цепочки, где required invoice не создана или не связана корректно.

#### Scenario: Required счёт-фактура публикуется и связывается с базовым документом
- **GIVEN** chain содержит базовый документ и шаг required invoice
- **WHEN** worker выполняет публикацию цепочки
- **THEN** сначала создаётся базовый документ, затем связанная счёт-фактура
- **AND** linkage между документами фиксируется в publication diagnostics/read-model

### Requirement: Chain-aware retry MUST сохранять partial success semantics
Система ДОЛЖНА (SHALL) при retry publication повторять только failed документы/цепочки для failed targets и не дублировать успешные side effects.

Система ДОЛЖНА (SHALL) сохранять внешний контракт статусов run (`published|partial_success|failed`) и лимиты retry policy.

#### Scenario: Retry повторяет только failed часть chain-публикации
- **GIVEN** в target database базовый документ успешно опубликован, а связанная счёт-фактура завершилась ошибкой
- **WHEN** оператор запускает retry failed
- **THEN** worker повторяет только failed шаг(и) цепочки
- **AND** already-successful шаги не дублируются
