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
2. Подготовить worker `odata-core` для двух путей (`odataops`, `pool.publication_odata`) и унифицировать retry/error/telemetry behavior.
3. Подготовить/прогнать parity suite: old vs new transport behavior для CRUD + publication diagnostics/idempotency.
4. Подготовить staging rehearsal и rollback drill (обязательные release gates).
5. Выполнить Big-bang cutover в одном релизном окне:
   - одновременно включить новый path для `odataops` и `pool.publication_odata`;
   - выключить legacy publication OData transport в Orchestrator runtime.
6. Прогнать post-cutover smoke + регрессию (включая сценарий run `500` на 3 организации).
7. Удалить/деактивировать legacy transport-компоненты и зафиксировать финальную ownership-модель.

## Open Questions
- Нужен ли жёсткий fail-closed код для запрета legacy publication path после cutover (вместо generic conflict).
