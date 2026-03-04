## 1. Единый orchestration contract
- [x] 1.1 Убрать split-path исполнение inbound и зафиксировать единую цепочку `domain -> workflow -> operations -> worker` для inbound/outbound.
- [x] 1.2 Добавить workflow-step(ы) для inbound polling/ack и подключить их в runtime backend роутинг.
- [x] 1.3 Удалить/деактивировать legacy inbound entrypoints, обходящие workflow runtime.
- [x] 1.4 Добавить contract/integration проверки, что legacy inbound route возвращает fail-closed machine-readable код и не создаёт side effects.
- [x] 1.5 Зафиксировать commit-before-ack инвариант для inbound (`NotifyChangesReceived` только после локального commit + checkpoint persist) и покрыть rollback-сценарии тестами.

## 2. Scheduling contract и очередь
- [x] 2.1 Расширить workflow enqueue envelope полями `priority`, `role`, `server_affinity`, `deadline_at` с fail-closed валидацией.
- [x] 2.2 Обновить contracts и сериализацию payload для новой scheduling-семантики.
- [x] 2.3 Реализовать deterministic mapping sync-use-case -> scheduling profile (policy+SLA aware).
- [x] 2.4 Зафиксировать и внедрить строгие enum-ы scheduling contract (`priority`, `role`) и RFC3339 UTC-валидацию `deadline_at` в orchestrator/go/contracts.
- [x] 2.5 Добавить fail-closed проверку `deadline_at` (не в прошлом на момент enqueue) и запрет публикации в stream при нарушении.
- [x] 2.6 Реализовать deferred outbox relay для `workflow_enqueue_outbox` (retry/backoff/idempotent dispatch) для случаев, когда inline dispatch не завершился успешно.
- [x] 2.7 Добавить detect+repair/backfill процедуру для зависших outbox-записей и пропущенных root operation projection с machine-readable diagnostics.

## 3. Worker topology для 6x120 ИБ
- [x] 3.1 Реализовать affinity mapping по серверу/кластеру 1С (IB scope -> `server_affinity`).
- [x] 3.2 Реализовать per-server worker pools с role-based обработкой (`inbound`, `outbound`, `reconcile`, `manual_remediation`).
- [x] 3.3 Обеспечить работу с общей очередью без дублирования исполнения и без starvation.
- [x] 3.4 Зафиксировать source-of-truth и deterministic resolution order для `IB scope -> server_affinity` (database override -> cluster mapping -> derived key).
- [x] 3.5 Добавить fail-closed поведение при неразрешимом affinity (`SERVER_AFFINITY_UNRESOLVED`) без permissive fallback.
- [x] 3.6 Зафиксировать архитектурный инвариант: единая реализация worker runtime (single codebase), разделение достигается через `role/priority/affinity` профили.
- [x] 3.7 Внедрить fairness policy: reserved capacity для `manual_remediation`, anti-starvation age-based promotion и tenant budget limiter для noisy tenant.

## 4. Reconcile окно 120 секунд
- [x] 4.1 Реализовать fan-out scheduler для reconcile probes по всем scope ИБ.
- [x] 4.2 Реализовать fan-in агрегатор с дедлайном 120 секунд и partial completion semantics.
- [x] 4.3 Добавить retry/backpressure политику для перегрузки без silent skip.

## 5. Надёжность и безопасность
- [x] 5.1 Зафиксировать crash/restart/replay сценарии для checkpoint/dedupe/ack и покрыть тестами.
- [x] 5.2 Обеспечить fail-closed поведение при нарушении scheduling contract или affinity resolution.
- [x] 5.3 Исключить утечку секретов в diagnostics/last_error на новом runtime пути.

## 6. Observability и SLA
- [x] 6.1 Добавить метрики для окна reconcile: coverage, deadline miss, partial rate, p95 latency.
- [x] 6.2 Добавить разрезы backlog/lag по `priority`, `role`, `server_affinity`.
- [x] 6.3 Обновить runbook инцидентов для unified sync runtime.
- [x] 6.4 Добавить API/read-model прозрачности очередей и задач: состояния `queued|processing|retrying|failed|completed`, причины ошибок, дедлайн-статус.
- [x] 6.5 Добавить фильтры операторского просмотра по `priority`, `role`, `server_affinity`, `deadline_state`.
- [x] 6.6 Добавить метрики fairness/защиты от starvation (`oldest_task_age_seconds`, `manual_remediation_quota_saturation`, `tenant_budget_throttle_total`).

## 7. Go/No-Go gates (обязательные)
- [x] 7.1 Зафиксировать формальные pass/fail пороги gate-проверок (числовые KPI и zero-tolerance инварианты).
- [x] 7.2 Пройти load gate на целевой модели 6x120 ИБ с подтверждённым SLA окна 120 секунд по зафиксированным порогам.
- [x] 7.3 Пройти replay/consistency gate (нет потерь, нет duplicate apply, deterministic idempotency).
- [x] 7.4 Пройти failover gate (перезапуск worker pool не нарушает checkpoint/ack контракт).
- [x] 7.5 Пройти security gate (diagnostics не содержат credentials/secrets).
- [x] 7.6 Автоматизировать gate-runner (blocking pre-cutover) и сохранить machine-readable отчёт проверки.
- [x] 7.7 Зафиксировать schema machine-readable отчёта readiness gates и обязательный ORR sign-off чеклист (`platform + security + operations`).

## 8. Cutover
- [x] 8.1 Зафиксировать runbook безопасного cutover для in-flight: `freeze new enqueue -> drain old path -> watermark capture -> enable`.
- [x] 8.2 Выполнить single-shot включение big-bang runtime в non-prod контуре по утверждённому runbook.
- [x] 8.3 Зафиксировать rollback-протокол для in-flight (artifact rollback + watermark-based replay-safe recovery + revalidation gates).
- [x] 8.4 Удалить feature-flags/ветки временной совместимости, не нужные после cutover.
- [x] 8.5 Зафиксировать post-cutover report и статус readiness для следующего окружения.
- [x] 8.6 Провести обязательный dry-run cutover/rollback в non-prod с артефактами (`freeze`, `drain`, `watermark`, `gate_report`).
