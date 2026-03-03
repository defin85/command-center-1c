## POOL_MASTER_DATA_SYNC Unified Runtime Incident Runbook

Цель: операционно поддерживать unified runtime `domain -> workflow -> operations -> worker` для master-data sync и выполнять rollback/cutover действия без потери checkpoint/outbox консистентности.

Смежные документы:
- readiness gates + ORR sign-off: `docs/observability/POOL_MASTER_DATA_SYNC_READINESS_GATES.md`
- gate report schema: `docs/observability/schemas/pool_master_data_sync_readiness_gate_report.schema.json`

### Scope

- контур: `CC <-> ИБ` (inbound/outbound/reconcile/manual remediation);
- ключи runtime:
  - `pools.master_data.sync.enabled`
  - `pools.master_data.sync.outbound.enabled`
  - `pools.master_data.sync.inbound.enabled`
  - `pools.master_data.sync.default_policy`
  - `pools.master_data.sync.poll_interval_seconds`
  - `pools.master_data.sync.dispatch_batch_size`
  - `pools.master_data.sync.max_retry_backoff_seconds`
- precedence: `tenant override -> global runtime setting -> env default`;
- fail-closed инварианты:
  - legacy inbound path блокируется кодом `SYNC_LEGACY_INBOUND_ROUTE_DISABLED`;
  - невалидный scheduling payload блокируется `SCHEDULING_CONTRACT_INVALID` или `SCHEDULING_DEADLINE_INVALID`;
  - неразрешимый affinity блокируется `SERVER_AFFINITY_UNRESOLVED`;
  - enqueue не переводит root operation в `queued` до подтверждённой публикации;
- операторские API:
  - `GET /api/v2/pools/master-data/sync-status/`
  - `GET /api/v2/pools/master-data/sync-conflicts/`
  - `POST /api/v2/pools/master-data/sync-conflicts/{id}/retry|reconcile|resolve/`

### Ключевые сигналы и метрики

- backlog/retry/conflicts:
  - `cc1c_orchestrator_pool_master_data_sync_outbox_lag_seconds`
  - `cc1c_orchestrator_pool_master_data_sync_outbox_pending_total`
  - `cc1c_orchestrator_pool_master_data_sync_outbox_retry_total`
  - `cc1c_orchestrator_pool_master_data_sync_outbox_retry_saturated_total`
  - `cc1c_orchestrator_pool_master_data_sync_outbox_retry_saturation_ratio`
  - `cc1c_orchestrator_pool_master_data_sync_conflicts_pending_total`
  - `cc1c_orchestrator_pool_master_data_sync_conflicts_retrying_total`
- queue scheduling slices (`status x priority x role x server_affinity`):
  - `cc1c_orchestrator_pool_master_data_sync_queue_backlog_total`
  - `cc1c_orchestrator_pool_master_data_sync_queue_lag_seconds`
- reconcile window:
  - `cc1c_orchestrator_pool_master_data_sync_reconcile_window_total`
  - `cc1c_orchestrator_pool_master_data_sync_reconcile_window_coverage_ratio`
  - `cc1c_orchestrator_pool_master_data_sync_reconcile_window_deadline_miss_total`
  - `cc1c_orchestrator_pool_master_data_sync_reconcile_window_partial_total`
  - `cc1c_orchestrator_pool_master_data_sync_reconcile_window_latency_seconds`
- fairness/starvation (worker):
  - `worker_oldest_task_age_seconds{server_affinity,role}`
  - `worker_manual_remediation_quota_saturation{server_affinity}`
  - `worker_tenant_budget_throttle_total{server_affinity}`

### Быстрый triage (первые 15 минут)

1. Подтвердить состояние рантаймов:
   - `./debug/probe.sh all`
2. Снять срез статусов по проблемному tenant/scope:
   - `curl -sS -H "Authorization: Bearer $TOKEN" -H "X-CC1C-Tenant-ID: $TENANT_ID" "http://localhost:8000/api/v2/pools/master-data/sync-status/?priority=p1&role=reconcile&server_affinity=srv-a&deadline_state=missed"`
3. Проверить queue lifecycle в ответе `sync-status`:
   - `queue_states.queued|processing|retrying|failed|completed`
   - `last_error_code`, `last_error_reason`, `deadline_state`
4. Снять очереди конфликтов:
   - `curl -sS -H "Authorization: Bearer $TOKEN" -H "X-CC1C-Tenant-ID: $TENANT_ID" "http://localhost:8000/api/v2/pools/master-data/sync-conflicts/?limit=100"`
5. Если backlog растёт или root projection отстаёт, выполнить detect+repair отчёт:
   - `cd orchestrator && ./venv/bin/python manage.py repair_workflow_enqueue_consistency --json > /tmp/workflow_enqueue_repair.json`
6. Если нужен целевой relay pending outbox:
   - `cd orchestrator && ./venv/bin/python manage.py dispatch_workflow_enqueue_outbox --batch-size 200 --json`

### Карта симптомов и действий

- Симптом: рост `cc1c_orchestrator_pool_master_data_sync_queue_backlog_total{status="retrying"}` и `cc1c_orchestrator_pool_master_data_sync_outbox_retry_saturation_ratio > 0.25`.
  - Проверка: `sync-status` и `/tmp/workflow_enqueue_repair.json` (`stuck_outbox_candidates_after`, `relay.failed`).
  - Действие: запуск `repair_workflow_enqueue_consistency`; RCA по `last_error_code`; временно увеличить `max_retry_backoff_seconds`.

- Симптом: `deadline_state=missed` и рост `...reconcile_window_deadline_miss_total`.
  - Проверка: фильтр `deadline_state=missed` + `role=reconcile`.
  - Действие: локализовать `server_affinity` hotspot, проверить `worker_oldest_task_age_seconds`, уменьшить шум tenant через budget limiter.

- Симптом: fail-closed ошибки enqueue (`SCHEDULING_*`, `SERVER_AFFINITY_UNRESOLVED`).
  - Проверка: `last_error_code`/timeline root operation.
  - Действие: исправить scheduling metadata (`priority`, `role`, `server_affinity`, `deadline_at`) и affinity mapping; повторить enqueue только после исправления.

- Симптом: резкий рост `queue_states.failed`.
  - Проверка: grouped `last_error_code` + `sync-conflicts`.
  - Действие: точечный `retry/reconcile/resolve`; не запускать массовый reconcile без RCA.

- Симптом: starvation `manual_remediation`.
  - Проверка: `worker_manual_remediation_quota_saturation=1` и рост `worker_oldest_task_age_seconds{role="manual_remediation"}`.
  - Действие: выделить capacity на затронутом `server_affinity`, ограничить noisy tenant, повторно проверить saturation.

### Rollback и ограничение blast radius

#### Tenant rollback (предпочтительно)

1. Для проблемного tenant отключить sync:
   - `pools.master_data.sync.enabled = false` (tenant override, status `published`)
2. Снизить давление очереди:
   - увеличить `poll_interval_seconds`;
   - уменьшить `dispatch_batch_size`.
3. Проверить, что новые enqueue по tenant не накапливаются, а история остаётся доступной.

#### Global rollback

1. Выставить global:
   - `pools.master_data.sync.enabled = false`
2. Проверить:
   - новые sync enqueue не выполняются;
   - данные `pool_master_data_sync_*` и `workflow_enqueue_outbox` не удаляются.

### Post-Incident Checklist

1. Зафиксирован machine-readable артефакт:
   - `/tmp/workflow_enqueue_repair.json` (schema `workflow_enqueue_repair.v1`).
2. Для каждого затронутого scope задокументированы:
   - `priority`, `role`, `server_affinity`, `deadline_state`,
   - `last_error_code` и remediation.
3. Подтверждены инварианты:
   - нет `ack_before_commit` нарушений,
   - нет silent fallback на legacy inbound path,
   - queue lifecycle отражает фактическое состояние.
4. Внесены follow-up задачи в Beads с owner и дедлайном.
