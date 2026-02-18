# Readiness sign-off: refactor-shared-odata-core

Дата: 2026-02-18
Сигнал старта реализации: пользовательский `Go!`.

## 1) DoR sign-off

DoR принят как обязательный входной gate перед основными изменениями.

Проверочные пункты:
- [x] Contract-diff для bridge path и fail-closed направления зафиксирован в OpenSpec change.
- [x] Source-of-truth read-model для report (`PoolPublicationAttempt`) зафиксирован.
- [x] Baseline контрактов и тестов зафиксирован: `artifacts/2026-02-18-baseline-contracts-and-tests.md`.
- [x] Rollout artifacts определены как обязательные deliverables (`cutover checklist`, `rollback runbook`, `staging rehearsal plan`).

## 2) DoD acceptance

DoD для change принят в исполнение:
- worker `odata-core` — единственный transport-owner для `odataops` и `pool.publication_odata`;
- legacy publication OData transport path в orchestrator отключен;
- bridge publication path возвращает fail-closed `409` + `POOL_RUNTIME_PUBLICATION_PATH_DISABLED`;
- facade contract (`PoolRunReport` + diagnostics) обратно совместим;
- quality gates (parity, preflight, rehearsal, rollback drill, contract tests) пройдены.

## 3) Ownership matrix

- Worker OData core, transport behavior, retries, telemetry labels: команда worker (Go).
- Internal bridge contract/OpenAPI и API-internal behavior: команда orchestrator API (Python/Django).
- Publication diagnostics projection/read-model compatibility: команда intercompany pools (orchestrator domain).
- Release gates, rehearsal, rollback readiness, operational sign-off: platform/ops.

## 4) Status

Решение readiness: **Approved for implementation**.
