## 1. Domain and contract baseline
- [ ] 1.1 Зафиксировать и реализовать модель sync scope/policy для master-data (`cc_master`, `ib_master`, `bidirectional`) с tenant-scoped конфигурацией.
- [ ] 1.2 Добавить persisted модели `sync_job`, `sync_checkpoint`, `sync_outbox`, `sync_conflict` с tenant/database/entity scope и machine-readable статусами в общем Postgres (отдельные таблицы, без отдельной БД).
- [ ] 1.3 Зафиксировать invariants идемпотентности и dedupe key для inbound/outbound контуров.

## 2. Orchestration path (`domain -> workflows -> operations -> worker`)
- [ ] 2.1 Зафиксировать workflow template/contract для sync job (включая входной контекст scope/policy и correlation identifiers).
- [ ] 2.2 Реализовать запуск sync из domain слоя через `workflows/execute-workflow` (без long-running синхронного API flow).
- [ ] 2.3 Реализовать публикацию workflow execution в operations enqueue/outbox и связать `sync_job` с `workflow_execution_id`/`operation_id`.

## 3. Outbound pipeline (`CC -> ИБ`)
- [ ] 3.1 Реализовать transactional outbox intent при mutating изменениях canonical сущностей и bindings.
- [ ] 3.2 Реализовать dispatcher с `SELECT ... FOR UPDATE SKIP LOCKED`, retry/backoff и fail-closed обработкой transport/domain ошибок.
- [ ] 3.3 Реализовать idempotent apply в ИБ с фиксацией `last_synced_at`, fingerprints и audit metadata без раскрытия секретов.

## 4. Inbound pipeline (`ИБ -> CC`)
- [ ] 4.1 Реализовать exchange-plan poller (`SelectChanges`) по checkpoint на `(tenant, database, entity)`.
- [ ] 4.2 Реализовать commit-aware acknowledge (`NotifyChangesReceived`) только после успешного local commit в CC.
- [ ] 4.3 Реализовать recovery/replay semantics для at-least-once доставки и restart/crash сценариев.

## 5. Conflict handling and anti-loop
- [ ] 5.1 Реализовать fail-closed конфликтный контракт с persisted conflict queue и deterministic error codes.
- [ ] 5.2 Реализовать anti-loop contract (`origin_system`, `origin_event_id`) и защиту от ping-pong репликации.
- [ ] 5.3 Реализовать операторские действия `retry/reconcile/resolve` для конфликтов с audit trail.

## 6. API/UI and settings
- [ ] 6.1 Добавить API read-model для статусов sync (lag, retries, checkpoints, conflicts) и mutating API для manual reconcile.
- [ ] 6.2 Добавить UI surfaces в pools для мониторинга sync и управления конфликтами.
- [ ] 6.3 Добавить runtime settings keys управления sync и интегрировать precedence resolver (tenant override -> global -> env default).

## 7. Verification and rollout
- [ ] 7.1 Добавить backend тесты inbound/outbound, idempotency, conflict, anti-loop и recovery сценариев.
- [ ] 7.2 Добавить frontend integration/e2e тесты для sync status/conflict flows.
- [ ] 7.3 Добавить rollout/runbook: shadow mode -> pilot tenant -> full enable, с rollback без удаления sync-данных.
- [ ] 7.4 Прогнать `openspec validate add-07-pool-master-data-bidirectional-sync --strict --no-interactive`.
