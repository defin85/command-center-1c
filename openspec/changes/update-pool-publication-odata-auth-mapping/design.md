## Context
После `refactor-shared-odata-core` transport-owner для `pool.publication_odata` уже в worker, но auth source-of-truth остался legacy:
- публикация запрашивает credentials без actor/service контекста;
- orchestrator credentials endpoint возвращает OData `username/password` из `Database`;
- существующий RBAC `InfobaseUserMapping` фактически не участвует в pool publication path.

В результате один и тот же бизнес-контур (OData публикация) имеет два конкурирующих механизма credentials management.

## Goals
- Сделать `InfobaseUserMapping` единственным source-of-truth для OData auth в `pool.publication_odata`.
- Прокинуть publication auth context (actor/service) от pool runtime до credentials fetch.
- Сохранить обратную совместимость pools facade API и текущий diagnostics/read-model контракт.
- Обеспечить fail-closed semantics без fallback на `Database.username/password`.

## Non-Goals
- Не менять публичный контракт `/api/v2/pools/runs/*`.
- Не вводить новый storage credentials поверх существующего `InfobaseUserMapping`.
- Не делать полный редизайн RBAC permission model.

## Constraints and NFR
- Security: publication auth не должен использовать legacy `Database.username/password` fallback после cutover.
- Reliability: missing/ambiguous mapping и invalid runtime context обрабатываются deterministic fail-closed с machine-readable кодами.
- Operability: оператор должен получать понятный remediation path (`/rbac`) и preflight сигнал до запуска/релиза.
- Compatibility: публичный pools facade API остаётся неизменным; меняется только internal runtime/transport contract.

## Decisions
### Decision 1: Reuse existing RBAC infobase mapping as OData auth source
Для `pool.publication_odata` OData credentials резолвятся только через `InfobaseUserMapping`:
- `actor` strategy: `(database_id, actor_username)`;
- `service` strategy: `(database_id, is_service=true)`.

`Database.odata_url` остаётся endpoint-конфигурацией, но `Database.username/password` не участвуют в publication auth.

### Decision 2: Publication auth context becomes explicit runtime contract
В workflow input/execution context добавляется `publication_auth`:
- `strategy`: `actor|service`;
- `actor_username`: non-empty для `actor`;
- `source`: provenance (кто сформировал publication attempt: run create / confirm / retry).

Этот контекст обязан дойти до worker operation node и использоваться при credentials fetch.

### Decision 3: Deterministic fail-closed lookup
Lookup mapping должен быть однозначным:
- при отсутствии mapping — fail-closed;
- при конфликтном/неоднозначном состоянии mapping — fail-closed;
- fallback на `Database.username/password` запрещён.

Ошибка классифицируется как credentials/runtime configuration issue (non-retryable на уровне бизнес-решения оператора, если mapping не исправлен).

### Decision 4: UX split remains, but source-of-truth is clarified
Operator UX фиксируется:
- `odata_url` настраивается в `Databases`;
- OData user/password настраиваются в `/rbac` -> `Infobase Users`.

`Databases -> Credentials` не должен восприниматься как источник auth для pool publication.

### Decision 5: Contract-first internal credentials transport
Внутренний transport contract для `get-database-credentials` фиксируется как часть архитектуры change:
- `created_by` и `ib_auth_strategy` считаются обязательными сигналами для publication auth lookup (с учётом strategy semantics);
- runtime/transport ошибки классифицируются через стабильные machine-readable коды:
  - `ODATA_MAPPING_NOT_CONFIGURED`,
  - `ODATA_MAPPING_AMBIGUOUS`,
  - `ODATA_PUBLICATION_AUTH_CONTEXT_INVALID`.

Неформализованный implicit contract между orchestrator и worker не допускается.

### Decision 6: Mandatory rollout gates and operator sign-off
Переключение на mapping-only auth выполняется только через gated rollout:
- preflight coverage report по target databases обязателен;
- staging rehearsal обязателен;
- для staging/prod требуется явный operator sign-off.

## Alternatives Considered
### A1. Оставить `Database.username/password` как fallback
Отклонено: сохраняет два источника секретов и не устраняет root-cause рассинхронизации.

### A2. Ввести новый отдельный `ODataUserMapping`
Отклонено: дублирует уже существующую модель `InfobaseUserMapping`, увеличивает стоимость миграции и операторскую сложность.

### A3. Делать actor selection только из `PoolRun.created_by`
Частично отклонено: недостаточно для safe/retry сценариев, где publication attempt инициирует другой оператор. Нужен explicit per-attempt provenance.

## Migration Plan
1. Зафиксировать `publication_auth` и credentials transport contract (including error taxonomy).  
   Gate: architecture/contract review.
2. Внедрить `publication_auth` propagation в orchestrator (`run create`, `confirm`, `retry`) с корректным actor provenance.  
   Depends on: 1.
3. Прокинуть context до worker node contract и переключить publication transport на context-aware credentials fetch.  
   Depends on: 2.
4. Переключить orchestrator credentials resolver на mapping-only для publication use-case и добавить deterministic lookup constraints/validation.  
   Depends on: 3.
5. Выполнить UX alignment и ранние operator validations (`/rbac` как remediation path).  
   Depends on: 4 (может идти частично параллельно).
6. Прогнать preflight coverage, e2e regression и observability checks; выполнить staging rehearsal + rollback drill.  
   Depends on: 4, 5.
7. Провести production cutover только после mandatory operator sign-off.  
   Depends on: 6.

## Risks and Mitigations
- Риск массовых падений публикации после cutover из-за отсутствующих mapping.
  - Mitigation: preflight coverage report + rollout gate.
- Риск неоднозначного actor provenance в safe/retry flows.
  - Mitigation: явный `publication_auth.source` и тесты на command actor propagation.
- Риск регрессии из-за legacy UI ожиданий (`Databases credentials`).
  - Mitigation: UI copy + документация + fail-fast error messages с указанием `/rbac` как точки исправления.
- Риск contract drift между orchestrator и worker для credentials payload.
  - Mitigation: contract-first schema фиксация + contract drift checks в CI.

## Readiness Criteria
### Definition of Ready (DoR)
- Согласован runtime contract `publication_auth` и credentials transport contract (`created_by`, `ib_auth_strategy`, error codes).
- Подтверждён список affected endpoints/handlers/tests.
- Подготовлен preflight чек mapping coverage.
- Назначены owners для orchestrator/worker/frontend/ops частей rollout.

### Definition of Done (DoD)
- `pool.publication_odata` больше не использует `Database.username/password`.
- Credentials lookup для publication path всегда context-aware (`actor|service`).
- Missing/ambiguous mapping обрабатывается fail-closed и детерминированно.
- e2e сценарии публикации через RBAC mapping проходят.
- Staging rehearsal и rollback drill выполнены, operator sign-off для staging/prod задокументирован.
- OpenSpec validate проходит в strict режиме.
