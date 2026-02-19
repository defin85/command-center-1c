## ADDED Requirements
### Requirement: Pool publication credentials lookup MUST быть context-aware
Система ДОЛЖНА (SHALL) для `pool.publication_odata` вызывать credentials fetcher с явным auth context:
- `requested_by` (для `actor` flow);
- `ib_auth_strategy` (`actor|service`).

Система ДОЛЖНА (SHALL) прокидывать эти значения в credentials transport request (`get-database-credentials`) как machine-readable поля (`created_by`, `ib_auth_strategy`).

#### Scenario: Actor strategy прокидывается в credentials request
- **GIVEN** `pool.publication_odata` выполняется со стратегией `actor`
- **WHEN** worker запрашивает credentials для target database
- **THEN** credentials request содержит `created_by=<actor_username>` и `ib_auth_strategy=actor`
- **AND** orchestrator резолвит credentials через actor mapping

#### Scenario: Service strategy прокидывается без actor username
- **GIVEN** `pool.publication_odata` выполняется со стратегией `service`
- **WHEN** worker запрашивает credentials
- **THEN** credentials request содержит `ib_auth_strategy=service`
- **AND** credentials резолвятся через service mapping

### Requirement: Context-aware lookup MUST исключать legacy fallback
Система НЕ ДОЛЖНА (SHALL NOT) для `pool.publication_odata` выполнять неявный fallback на `Database.username/password`, если context-aware mapping lookup неуспешен.

#### Scenario: Missing mapping не приводит к fallback на Database credentials
- **GIVEN** publication lookup по mapping вернул "not configured"
- **WHEN** worker обрабатывает результат credentials fetch
- **THEN** шаг завершается fail-closed credentials error
- **AND** OData transport не инициируется с `Database.username/password`

### Requirement: Credentials transport contract MUST быть явным и детерминированным
Система ДОЛЖНА (SHALL) использовать формализованный internal contract для credentials request/response в publication path:
- request содержит `ib_auth_strategy` и (для `actor`) `created_by`;
- при невалидном контексте возвращается `ODATA_PUBLICATION_AUTH_CONTEXT_INVALID`;
- для неоднозначного mapping возвращается `ODATA_MAPPING_AMBIGUOUS`;
- для отсутствующего mapping возвращается `ODATA_MAPPING_NOT_CONFIGURED`.

Ошибки этого класса ДОЛЖНЫ (SHALL) считаться non-retryable до изменения конфигурации оператором.

#### Scenario: Невалидный actor context возвращает non-retryable contract error
- **GIVEN** `pool.publication_odata` исполняется со стратегией `actor`
- **AND** credentials request не содержит `created_by`
- **WHEN** orchestrator/worker валидирует credentials contract
- **THEN** шаг завершается fail-closed с `error_code=ODATA_PUBLICATION_AUTH_CONTEXT_INVALID`
- **AND** ошибка классифицирована как non-retryable configuration issue
