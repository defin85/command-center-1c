## ADDED Requirements
### Requirement: Publication auth context MUST быть частью workflow runtime execution context
Система ДОЛЖНА (SHALL) формировать для `pool.publication_odata` явный `publication_auth` контекст в workflow execution:
- `strategy` (`actor|service`);
- `actor_username` (для `actor`);
- `source` (provenance инициатора publication attempt).

Система ДОЛЖНА (SHALL) прокидывать этот контекст от orchestrator runtime до worker operation node без потери данных.

#### Scenario: Safe confirm формирует actor publication context
- **GIVEN** safe run ожидает approval
- **AND** оператор вызывает `confirm-publication`
- **WHEN** publication step enqueue в workflow runtime
- **THEN** execution context содержит `publication_auth.strategy=actor`
- **AND** `publication_auth.actor_username` соответствует оператору, подтвердившему публикацию

#### Scenario: Retry publication фиксирует нового инициатора attempt
- **GIVEN** run в `partial_success` и оператор запускает retry
- **WHEN** создаётся новый publication attempt
- **THEN** новый execution context содержит актуальный `publication_auth` provenance
- **AND** worker использует этот context для credentials lookup

### Requirement: Publication auth context MUST валидироваться fail-closed до OData side effects
Система ДОЛЖНА (SHALL) fail-closed отклонять execution, если `publication_auth` неконсистентен:
- `strategy=actor`, но `actor_username` пустой;
- strategy неизвестна;
- context отсутствует для publication node.

#### Scenario: Неконсистентный publication_auth блокирует шаг до transport вызовов
- **GIVEN** workflow execution дошёл до `pool.publication_odata`
- **AND** `publication_auth` невалиден
- **WHEN** worker валидирует runtime context
- **THEN** шаг завершается fail-closed с machine-readable ошибкой
- **AND** OData side effect не выполняется

### Requirement: Publication provenance MUST отражать фактического инициатора safe/retry команды
Система ДОЛЖНА (SHALL) формировать `publication_auth.source` и `publication_auth.actor_username` от фактического инициатора команд `confirm-publication` и `retry`, если стратегия `actor`.

Система НЕ ДОЛЖНА (SHALL NOT) подменять actor provenance generic actor'ом (например, `workflow_engine`) в тех сценариях, где инициатор-оператор известен.

#### Scenario: Confirm от оператора сохраняет actor provenance без подмены
- **GIVEN** safe run находится в `awaiting_approval`
- **AND** оператор `alice` вызывает `confirm-publication`
- **WHEN** публикационный шаг enqueue в workflow runtime
- **THEN** execution context содержит `publication_auth.actor_username=alice`
- **AND** provenance не подменён техническим `workflow_engine`
