## 1. Единый orchestration contract
- [ ] 1.1 Убрать split-path исполнение inbound и зафиксировать единую цепочку `domain -> workflow -> operations -> worker` для inbound/outbound.
- [ ] 1.2 Добавить workflow-step(ы) для inbound polling/ack и подключить их в runtime backend роутинг.
- [ ] 1.3 Удалить/деактивировать legacy inbound entrypoints, обходящие workflow runtime.

## 2. Scheduling contract и очередь
- [ ] 2.1 Расширить workflow enqueue envelope полями `priority`, `role`, `server_affinity`, `deadline_at` с fail-closed валидацией.
- [ ] 2.2 Обновить contracts и сериализацию payload для новой scheduling-семантики.
- [ ] 2.3 Реализовать deterministic mapping sync-use-case -> scheduling profile (policy+SLA aware).

## 3. Worker topology для 6x120 ИБ
- [ ] 3.1 Реализовать affinity mapping по серверу/кластеру 1С (IB scope -> `server_affinity`).
- [ ] 3.2 Реализовать per-server worker pools с role-based обработкой (`inbound`, `outbound`, `reconcile`, `manual_remediation`).
- [ ] 3.3 Обеспечить работу с общей очередью без дублирования исполнения и без starvation.

## 4. Reconcile окно 120 секунд
- [ ] 4.1 Реализовать fan-out scheduler для reconcile probes по всем scope ИБ.
- [ ] 4.2 Реализовать fan-in агрегатор с дедлайном 120 секунд и partial completion semantics.
- [ ] 4.3 Добавить retry/backpressure политику для перегрузки без silent skip.

## 5. Надёжность и безопасность
- [ ] 5.1 Зафиксировать crash/restart/replay сценарии для checkpoint/dedupe/ack и покрыть тестами.
- [ ] 5.2 Обеспечить fail-closed поведение при нарушении scheduling contract или affinity resolution.
- [ ] 5.3 Исключить утечку секретов в diagnostics/last_error на новом runtime пути.

## 6. Observability и SLA
- [ ] 6.1 Добавить метрики для окна reconcile: coverage, deadline miss, partial rate, p95 latency.
- [ ] 6.2 Добавить разрезы backlog/lag по `priority`, `role`, `server_affinity`.
- [ ] 6.3 Обновить runbook инцидентов для unified sync runtime.

## 7. Go/No-Go gates (обязательные)
- [ ] 7.1 Пройти load gate на целевой модели 6x120 ИБ с подтверждённым SLA окна 120 секунд.
- [ ] 7.2 Пройти replay/consistency gate (нет потерь, нет duplicate apply, deterministic idempotency).
- [ ] 7.3 Пройти failover gate (перезапуск worker pool не нарушает checkpoint/ack контракт).
- [ ] 7.4 Пройти security gate (diagnostics не содержат credentials/secrets).

## 8. Cutover
- [ ] 8.1 Выполнить single-shot включение big-bang runtime в non-prod контуре.
- [ ] 8.2 Удалить feature-flags/ветки временной совместимости, не нужные после cutover.
- [ ] 8.3 Зафиксировать post-cutover report и статус readiness для следующего окружения.
