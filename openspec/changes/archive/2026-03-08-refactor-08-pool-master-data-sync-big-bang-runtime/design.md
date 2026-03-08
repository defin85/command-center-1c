## Context
Текущий sync runtime для master-data имеет архитектурный разрыв:
- outbound проходит через `workflow -> operations -> worker`;
- inbound реализован отдельным poller-модулем и не является workflow step.

Для целевого масштаба `6` серверов 1С x `120` ИБ (итого `720` ИБ) такой split-path увеличивает операционную сложность: разные retry/observability/error contracts, сложная поддержка SLA reconcile-окон.

## Goals / Non-Goals
### Goals
- Единый runtime lifecycle для inbound/outbound/reconcile.
- Общая очередь с управляемым scheduling (`priority`, `role`, `server_affinity`, `deadline_at`).
- Поддержка reconcile-window 120 секунд для 720 ИБ.
- Прозрачный операторский read-model очередей и задач (видимые состояния, причины ошибок, дедлайны, backlog/lag разрезы).
- Fail-closed cutover без legacy обходов.

### Non-Goals
- Поддержка длительного dual-path режима в production.
- Перенос sync persistence в отдельную физическую БД.
- Введение второго независимого runtime контура для sync.

## Decisions
### Decision 1: Один execution path для sync
Все sync операции (outbound dispatch, inbound poll/apply/ack, reconcile probe) исполняются как workflow operation steps через общий pipeline:
`domain -> workflow execution -> operations enqueue/outbox -> worker`.

Legacy inbound path, вызываемый вне workflow runtime, удаляется после cutover.

### Decision 2: Shared queue + scheduling contract
Workflow enqueue payload расширяется обязательными scheduling-полями:
- `priority`: `p0|p1|p2|p3`;
- `role`: `inbound|outbound|reconcile|manual_remediation`;
- `server_affinity`: стабильный ключ сервера/кластера 1С;
- `deadline_at`: RFC3339 UTC для SLA-aware обработки.

Невалидный scheduling payload блокирует enqueue fail-closed.
Дополнительно:
- `deadline_at` ДОЛЖЕН быть в будущем на момент enqueue;
- отсутствие обязательных полей и некорректные enum значения приводят к machine-readable validation error (`SCHEDULING_CONTRACT_INVALID`) и отказу публикации в stream;
- `deadline_at` в прошлом приводит к machine-readable ошибке `SCHEDULING_DEADLINE_INVALID`.

### Decision 3: Affinity-aware worker topology
Используется единая очередь, но worker-пулы фильтруют задачи по `server_affinity` и `role`.
Это позволяет:
- держать локальность доступа к 1С серверу;
- масштабировать обработку независимо по серверам;
- избежать дублирования реализации воркеров.

Source-of-truth и детерминированный порядок резолва `IB scope -> server_affinity`:
1. database-level explicit mapping override;
2. cluster-level mapping (`cluster_id -> server_affinity`);
3. derived affinity key из нормализованного server endpoint (`ras_server`/server identifier).

Если резолв неуспешен, enqueue блокируется fail-closed с кодом `SERVER_AFFINITY_UNRESOLVED`.

Архитектурный инвариант:
- единая реализация worker runtime (single codebase);
- разделение нагрузки и изоляция выполняются через `role/priority/server_affinity`, а не через отдельные runtime-сервисы.

### Decision 4: Reconcile fan-out/fan-in с дедлайном 120 секунд
Планировщик формирует окно reconcile:
1. fan-out: создаёт `reconcile_probe` job на каждый scope ИБ;
2. fan-in: агрегирует completion до `deadline_at`;
3. partial результат считается валидным outcome окна с machine-readable diagnostics.

SLA рассчитывается по окнам, а не по отдельным probe-задачам.

### Decision 5: Big-bang cutover с обязательными Go/No-Go gates
Так как production-трафик отсутствует, выполняется single-shot cutover. Перед включением обязательны gate:
- load;
- replay/consistency;
- failover/restart;
- security diagnostics.

При провале любого gate включение блокируется.

### Decision 6: Формальные pass/fail критерии для readiness gates
Каждый gate имеет фиксированные пороги (pass/fail), проверяемые автоматически:
- `load gate`:
  - `reconcile_window_p95_seconds <= 120`;
  - `reconcile_window_p99_seconds <= 150`;
  - `coverage_ratio >= 0.995`;
  - `partial_outcome_rate <= 0.05` на номинальной нагрузке.
- `replay/consistency gate`:
  - `lost_events_total = 0`;
  - `duplicate_apply_total = 0`;
  - `deterministic_replay_match_ratio = 1.0`.
- `failover/restart gate`:
  - `checkpoint_monotonicity_violations = 0`;
  - `ack_before_commit_violations = 0`;
  - `worker_recovery_to_steady_state_seconds <= 60`.
- `security gate`:
  - `secrets_exposed_in_diagnostics = 0`;
  - `secrets_exposed_in_last_error = 0`;
  - `redaction_test_failures = 0`.

Формат отчёта gate-runner:
- machine-readable JSON со `schema_version`;
- секции `load`, `replay_consistency`, `failover_restart`, `security`;
- для каждой секции: `status`, `measured_values`, `thresholds`, `evidence_refs`;
- итоговые поля `overall_status`, `generated_at_utc`, `signed_off_by`.

### Decision 7: Safe cutover/rollback для in-flight сообщений
Cutover выполняется по протоколу:
1. `freeze`: блокировать создание новых sync enqueue на legacy path;
2. `drain`: довести in-flight backlog legacy path до нуля;
3. `watermark capture`: зафиксировать checkpoint/outbox watermark;
4. `enable`: включить unified runtime;
5. `verify`: прогнать post-enable smoke + gate subset.

Rollback выполняется через:
1. откат релизного артефакта;
2. восстановление по watermark без потери/дублирования;
3. повторный gate-check до повторного enable.

### Decision 8: Workflow enqueue outbox dispatch MUST иметь deferred relay
Публикация enqueue-команды поддерживает два режима:
1. inline dispatch в request path;
2. deferred relay для pending outbox rows.

Инварианты:
- root projection переходит в `queued` только после подтверждённой публикации (`XADD` success);
- при падении inline dispatch outbox entry остаётся `PENDING` и обрабатывается relay-процедурой;
- relay использует idempotent dispatch key и retry/backoff;
- зависшие outbox/root projection рассинхроны детектируются и исправляются detect+repair процедурой с machine-readable diagnostics.

### Decision 9: Fairness policy и tenant budget limiter
Чтобы исключить starvation и блокировки операторских действий, вводятся управляемые квоты:
- reserved capacity для `manual_remediation`: минимум 1 слот на server pool;
- age-based promotion: задача с ожиданием выше `oldest_age_threshold_seconds` поднимается в следующую dispatch-итерацию;
- tenant budget limiter: один tenant не может занять более заданной доли server pool.

Дефолтные значения фиксируются конфигом окружения и попадают под observability (`quota saturation`, `throttle hits`, `oldest task age`).

### Decision 10: Inbound ACK semantics MUST быть commit-safe
Для inbound exchange-plan/OData pipeline:
- `SelectChanges` читается в рамках poll/apply шага;
- локальное применение и checkpoint фиксируются транзакционно;
- `NotifyChangesReceived` выполняется только после успешного commit.

При rollback локального apply acknowledge не отправляется, чтобы исключить потерю данных и недетерминированные replay эффекты.

## Capacity Notes
- Целевой объём: `720` ИБ за `120` секунд => средняя интенсивность `6` probe jobs/sec.
- На один сервер: `120` ИБ за `120` секунд => `1` job/sec.
- Базовая оценка пула на сервер:
  `pool_size = ceil(ib_per_server * p95_task_seconds / window_seconds) * safety_factor`.
  Для `p95=3s`, `ib_per_server=120`, `window=120s`, `safety_factor=3`:
  `ceil(120*3/120)*3 = 9` worker slots на сервер.

## Observability Contract
- Система публикует read-model queue/task lifecycle со статусами `queued|processing|retrying|failed|completed`.
- Для каждой задачи доступны `priority`, `role`, `server_affinity`, `deadline_at`, `deadline_state`, `error_code`.
- Backlog/lag и latency метрики доступны в разрезах `priority x role x server_affinity`.
- Для fairness публикуются `oldest_task_age_seconds`, `manual_remediation_quota_saturation`, `tenant_budget_throttle_total`.
- Операторские API поддерживают фильтры по scheduling-полям и дедлайн-состоянию.

## Risks / Trade-offs
- Риск: starvation низких приоритетов при постоянном потоке `p0/p1`.
  - Mitigation: fairness quota per priority band и мониторинг oldest-age.
- Риск: неверная affinity mapping приводит к cross-server задержкам.
  - Mitigation: fail-closed валидация `server_affinity` + fallback только по явному override.
- Риск: cutover выявит скрытые различия inbound/outbound side effects.
  - Mitigation: replay gate и golden-path regression набор до включения.

## Migration Plan
1. Зафиксировать scheduling enums, affinity source-of-truth и observability contract в коде/контрактах.
2. Внедрить workflow-step path для inbound poll/apply/ack и удалить legacy bypass hooks.
3. Реализовать reconcile fan-out/fan-in window + partial semantics.
4. Реализовать safe cutover protocol (`freeze -> drain -> watermark -> enable -> verify`).
5. Пройти формальные Go/No-Go gates и сохранить machine-readable отчёт.
6. Выполнить single-shot enablement в non-prod и удалить legacy inbound execution path.

## Rollback Plan
Если gate не пройдены, релиз не активируется.
Если проблема выявлена после enablement:
1. немедленно активировать `freeze` для новых enqueue;
2. откатить релизный артефакт;
3. восстановить состояние по watermark (checkpoint/outbox) и выполнить replay-safe revalidation;
4. повторно пройти gate subset до снятия freeze.

## Resolved Questions
- Отдельная квота для `manual_remediation` обязательна: минимум один зарезервированный слот в каждом server pool.
- Tenant-level budget limiter обязателен и включён по умолчанию для защиты общей очереди от noisy tenant.
