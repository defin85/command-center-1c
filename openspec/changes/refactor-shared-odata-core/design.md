## Context
Сейчас OData transport concerns распределены между разными runtime-владельцами:
- `odataops` использует worker OData transport;
- `pool.publication_odata` выполняется в Orchestrator domain runtime с отдельным transport stack.

При такой схеме растут риски drift по retry/error/auth/session semantics и повышается стоимость сопровождения. Пользователь выбрал стратегию Big-bang переноса вместо staged migration.

## Goals
- Единый shared OData transport слой в worker для `odataops` и `pool.publication_odata`.
- Поведенческий паритет по retry/error/auth/session.
- Наблюдаемость transport-поведения на уровне метрик и трейсинга.
- Атомарный cutover без длительного mixed-mode.

## Non-Goals
- Рефакторинг всей pool domain state-machine.
- Изменение публичных REST контрактов pools API.
- Перенос non-OData pool шагов в worker (`pool.prepare_input`, `pool.distribution_calculation.*`, `pool.reconciliation_report`, `pool.approval_gate`).

## Decisions
### Decision 1: Выделить `odata-core` как transport-only слой
`odata-core` отвечает только за transport concerns:
- конфигурация клиента и сессии;
- выполнение HTTP-запросов к OData;
- retry policy;
- нормализация ошибок;
- shared helpers для batch/upsert/posting.

Доменные правила (`pool publication`, `generic CRUD`) остаются в соответствующих драйверах.

### Decision 2: Big-bang cutover в одном релизном окне
Переключение на новый transport path выполняется атомарно:
1. `odataops` и `pool.publication_odata` одновременно переходят на worker `odata-core`;
2. legacy transport path для `pool.publication_odata` в Orchestrator выключается в том же релизе.

В production НЕ допускается состояние, где только один из двух путей работает через новый `odata-core`.

### Decision 3: Владелец OData transport для `pool.publication_odata` переносится в worker
После cutover OData side effects публикации выполняются в worker `odata-core`.

Orchestrator сохраняет:
- bridge-контракт и доменную оркестрацию non-OData pool шагов;
- lifecycle/projection/diagnostics semantics.

### Decision 3.1: Ownership enforcement через явный fail-closed код
После cutover bridge path для `operation_type=pool.publication_odata` НЕ исполняет OData side effects и возвращает non-retryable код:
- `POOL_RUNTIME_PUBLICATION_PATH_DISABLED`.

Это исключает неявный fallback к legacy publication transport при инцидентах/ошибках конфигурации.

### Decision 4: Retry policy стандартизируется
`odata-core` использует bounded exponential backoff + jitter для retryable ошибок (transport errors, `5xx`, `429`) с ограниченным количеством попыток.

Для non-retryable ошибок (`4xx` кроме `429`) повтор не выполняется.

### Decision 5: Наблюдаемость обязательна
`odata-core` публикует единые telemetry-сигналы:
- request latency;
- retry count;
- финальный status class/error code;
- trace-атрибут resend attempt для повторных HTTP-запросов.

### Decision 6: Cutover управляется единым release gate + rollback runbook
Вместо per-driver production rollout используется единый Big-bang gate:
- pre-cutover parity suite и staging rehearsal обязательны;
- rollback допускается только как откат релиза целиком (без долгого dual-write/mixed-mode).

### Decision 7: Idempotency owner переносится вместе с transport owner
При переносе publication OData path в worker идемпотентность side effects ДОЛЖНА (SHALL) остаться детерминированной и эквивалентной текущему доменному контракту:
- stable key per `step_attempt`;
- transport retries внутри `step_attempt` не создают новый business side effect;
- conflict/replay semantics покрываются контрактными тестами.

### Decision 8: Source-of-truth для publication diagnostics остаётся в Orchestrator read-model
После cutover исполнение OData side effects полностью переносится в worker, но канонический read-model для операторских отчётов сохраняется в Orchestrator:
- `PoolPublicationAttempt` (`pool_publication_attempts`) остаётся источником истины для `/api/v2/pools/runs/{run_id}/report`;
- worker возвращает нормализованные attempt/diagnostics данные в результатах workflow step;
- Orchestrator проецирует эти данные в существующий read-model без изменения публичного facade-контракта.

Это сохраняет обратную совместимость frontend/API и исключает миграцию клиентской логики в рамках данного change.

### Decision 9: Fail-closed bridge error contract фиксируется как HTTP 409 + ErrorResponse
Для `operation_type=pool.publication_odata` после cutover bridge endpoint
`POST /api/v2/internal/workflows/execute-pool-runtime-step` возвращает:
- HTTP статус `409 Conflict`;
- payload схемы `ErrorResponse` (`error`, `code`, optional `details`);
- стабильный machine-readable код `POOL_RUNTIME_PUBLICATION_PATH_DISABLED`.

Этот ответ классифицируется как non-retryable и исключает silent fallback на legacy publication transport.

### Decision 10: Единые release gates фиксируются как blocking критерии
Cutover допускается только при выполнении всех условий:
- parity suite (CRUD + publication path) без критических расхождений;
- compatibility preflight (`odata-compatibility-profile`) для целевого окружения;
- staging rehearsal и rollback drill завершены успешно;
- контрактные тесты fail-closed bridge path зелёные;
- post-cutover smoke в staging фиксирует совместимость status/diagnostics facade.

## Alternatives Considered
### A1. Staged migration (`poolops` first -> `odataops`)
Отклонено: длительный mixed-mode и повышенная операционная сложность.

### A2. Оставить независимые transport-пути
Отклонено: drift, неоднородная telemetry и дорогая поддержка.

### A3. Перенести всю pool domain логику в worker в рамках этого change
Отклонено: слишком большой blast radius и выход за scope transport refactor.

## Risks / Trade-offs
- Риск крупного blast radius в релизе.
  - Mitigation: обязательные pre-cutover parity tests, staging rehearsal и freeze window.
- Риск rollback под давлением инцидента.
  - Mitigation: заранее подготовленный rollback runbook и автоматизированный smoke-check после отката.
- Риск дрейфа доменной семантики публикации при смене transport owner.
  - Mitigation: contract tests на diagnostics/idempotency/status projection и strict проверка `pool-workflow-execution-core`.
- Риск регрессий по media-type совместимости 1С.
  - Mitigation: compatibility profile checks (`odata-compatibility-profile`) как fail-closed gate перед cutover.

## Migration Plan
1. Зафиксировать контракт Big-bang cutover в spec deltas (`worker-odata-transport-core`, `pool-workflow-execution-core`).
2. Добавить/обновить `pool-odata-publication` delta с фиксацией ownership и неизменности доменных инвариантов publication.
3. Подготовить worker `odata-core` для двух путей (`odataops`, `pool.publication_odata`) и унифицировать retry/error/telemetry behavior.
4. Зафиксировать bridge contract enforcement для publication path (`POOL_RUNTIME_PUBLICATION_PATH_DISABLED`).
5. Подготовить/прогнать parity suite: old vs new transport behavior для CRUD + publication diagnostics/idempotency.
6. Подготовить staging rehearsal и rollback drill (обязательные release gates).
7. Выполнить Big-bang cutover в одном релизном окне:
   - одновременно включить новый path для `odataops` и `pool.publication_odata`;
   - выключить legacy publication OData transport в Orchestrator runtime;
   - включить fail-closed reject в bridge publication path.
8. Прогнать post-cutover smoke + регрессию (включая сценарий run `500` на 3 организации).
9. Удалить/деактивировать legacy transport-компоненты и зафиксировать финальную ownership-модель.

## Implementation Readiness
### Definition of Ready (DoR)
- Спеки и contract-diff согласованы, включая `POOL_RUNTIME_PUBLICATION_PATH_DISABLED`.
- Подготовлены test fixtures/parity baseline для CRUD и publication path.
- Подготовлены cutover checklist, rollback runbook и staging rehearsal сценарий.
- Зафиксированы владельцы работ:
  - worker `odata-core`: Go команда worker;
  - bridge contract/OpenAPI: команда Orchestrator API;
  - release gates/rehearsal: platform/ops.

### Definition of Done (DoD)
- Оба пути (`odataops`, `pool.publication_odata`) используют только worker `odata-core`.
- Legacy publication transport path в Orchestrator отключён.
- Bridge publication path возвращает только fail-closed `409` + `POOL_RUNTIME_PUBLICATION_PATH_DISABLED`.
- `PoolRunReport` и diagnostics обратно совместимы для существующих клиентов.
- Все gates (parity, preflight, rehearsal, rollback drill, contract tests) пройдены и задокументированы.

## Normative References
- 1C KB: Standard OData interface  
  https://kb.1ci.com/1C_Enterprise_Platform/Guides/Developer_Guides/1C_Enterprise_8.3.23_Developer_Guide/Chapter_17._Integration_with_external_systems/17.4._Standard_OData_interface/
- 1C KB FAQ: Publishing standard REST/OData API  
  https://kb.1ci.com/1C_Enterprise_Platform/FAQ/Development/Integration/Publishing_standard_REST_API_for_your_infobase/
- OData v4.01 Protocol  
  https://docs.oasis-open.org/odata/odata/v4.01/odata-v4.01-part1-protocol.html
- HTTP Semantics (RFC 9110)  
  https://www.rfc-editor.org/rfc/rfc9110.html
- Problem Details for HTTP APIs (RFC 9457)  
  https://www.rfc-editor.org/rfc/rfc9457.html
