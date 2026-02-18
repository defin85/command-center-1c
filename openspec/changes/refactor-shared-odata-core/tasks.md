## 0. Readiness Baseline (до начала кодинга)
- [x] 0.1 Зафиксировать baseline контрактов и тестов: current `PoolRunReport`, bridge endpoint, publication diagnostics.
- [x] 0.2 Утвердить DoR/DoD и владельцев работ (worker, orchestrator API, platform/ops).
- [x] 0.3 Подготовить release artifacts: cutover checklist, rollback runbook, staging rehearsal plan.

## 1. Contracts & Specs
- [x] 1.1 Обновить internal OpenAPI bridge-контракт: для `pool.publication_odata` после cutover возвращается `409` + `ErrorResponse.code=POOL_RUNTIME_PUBLICATION_PATH_DISABLED`.
- [x] 1.2 Зафиксировать в capability deltas atomic Big-bang, запрет mixed-mode и ownership worker `odata-core`.
- [x] 1.3 Зафиксировать source-of-truth diagnostics: `PoolPublicationAttempt` остаётся каноническим read-model для `/api/v2/pools/runs/{run_id}/report`.

## 2. Worker OData Core
- [x] 2.1 Реализовать/доработать shared `odata-core` для двух путей: `odataops` и `pool.publication_odata`.
- [x] 2.2 Унифицировать retry policy (retryable/non-retryable, bounded exponential backoff + jitter, max attempts).
- [x] 2.3 Унифицировать error normalization и labels для telemetry.
- [x] 2.4 Подключить compatibility profile checks (`odata-compatibility-profile`) в publication path.

## 3. Pool Publication Migration
- [x] 3.1 Перенести execution `pool.publication_odata` на worker `odata-core` без изменения доменных инвариантов (`partial_success`, retry caps, diagnostics, idempotency).
- [x] 3.2 Обеспечить проекцию publication attempts/diagnostics в существующий read-model Orchestrator (`PoolPublicationAttempt`).
- [x] 3.3 Сохранить совместимость facade контракта (`PoolRunReport`, status projection, diagnostics payload).

## 4. Bridge Fail-Closed Enforcement
- [x] 4.1 Отключить legacy OData side effects в bridge-path для `pool.publication_odata`.
- [x] 4.2 Включить deterministic fail-closed поведение: `409` + `POOL_RUNTIME_PUBLICATION_PATH_DISABLED` + non-retryable classification.
- [x] 4.3 Добавить защиту от silent fallback на legacy-path в runtime/config validation.

## 5. Observability & Operability
- [x] 5.1 Добавить метрики и tracing для transport-level retries/latency/errors/resend-attempt.
- [x] 5.2 Вывести единый dashboard/checks для сравнения `odataops` vs `pool.publication_odata` после миграции.
- [x] 5.3 Подготовить cutover SRE-пакет: alert thresholds, abort criteria, post-cutover smoke checklist.

## 6. Validation & Quality Gates
- [x] 6.1 Unit tests: retry classifier, jitter bounds, error normalization, idempotency behavior.
- [x] 6.2 Integration tests: publication flow, generic CRUD, compatibility profile enforcement.
- [x] 6.3 Contract tests: bridge fail-closed (`409`, `POOL_RUNTIME_PUBLICATION_PATH_DISABLED`, `ErrorResponse` schema).
- [x] 6.4 Parity suite old/new transport: без критических расхождений по status/diagnostics/idempotency.
- [x] 6.5 Rehearsal в staging + rollback drill до cutover.
- [x] 6.6 E2E регрессия: run `500` на 3 организации с публикацией документов.

## 7. Big-bang Cutover & Cleanup
- [ ] 7.1 Выполнить атомарный cutover обоих путей (`odataops` + `pool.publication_odata`) в одном релизном окне.
- [ ] 7.2 Подтвердить post-cutover smoke и стабильность по telemetry в agreed soak window.
- [x] 7.3 Удалить/деактивировать legacy transport-компоненты и закрыть migration debt в том же change-set.
- [x] 7.4 Прогнать `openspec validate refactor-shared-odata-core --strict --no-interactive` и приложить результаты в release evidence.

Примечание к 7.1/7.2:
- pre-release readiness подтверждена артефактами `2026-02-18-bigbang-cutover-execution-readiness.md` и `2026-02-18-post-cutover-smoke-soak-report.md`;
- live cutover/smoke/soak требуют отдельного релизного окна и operator execution в staging/prod.
