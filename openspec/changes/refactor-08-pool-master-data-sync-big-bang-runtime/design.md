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

### Decision 3: Affinity-aware worker topology
Используется единая очередь, но worker-пулы фильтруют задачи по `server_affinity` и `role`.
Это позволяет:
- держать локальность доступа к 1С серверу;
- масштабировать обработку независимо по серверам;
- избежать дублирования реализации воркеров.

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

## Capacity Notes
- Целевой объём: `720` ИБ за `120` секунд => средняя интенсивность `6` probe jobs/sec.
- На один сервер: `120` ИБ за `120` секунд => `1` job/sec.
- Базовая оценка пула на сервер:
  `pool_size = ceil(ib_per_server * p95_task_seconds / window_seconds) * safety_factor`.
  Для `p95=3s`, `ib_per_server=120`, `window=120s`, `safety_factor=3`:
  `ceil(120*3/120)*3 = 9` worker slots на сервер.

## Risks / Trade-offs
- Риск: starvation низких приоритетов при постоянном потоке `p0/p1`.
  - Mitigation: fairness quota per priority band и мониторинг oldest-age.
- Риск: неверная affinity mapping приводит к cross-server задержкам.
  - Mitigation: fail-closed валидация `server_affinity` + fallback только по явному override.
- Риск: cutover выявит скрытые различия inbound/outbound side effects.
  - Mitigation: replay gate и golden-path regression набор до включения.

## Migration Plan
1. Внедрить новые workflow steps и scheduling contract.
2. Перевести inbound на runtime steps.
3. Включить reconcile fan-out/fan-in window.
4. Пройти Go/No-Go gates.
5. Выполнить single-shot enablement в non-prod.
6. Удалить legacy inbound execution path.

## Rollback Plan
Если gate не пройдены, релиз не активируется.
Если проблема выявлена сразу после enablement, откат выполняется на предыдущий релизный артефакт (без частичного dual-path режима внутри одного артефакта).

## Open Questions
- Нужна ли отдельная квота на `manual_remediation` поверх `p0`, чтобы operator actions не блокировались массовым reconcile окном?
- Нужен ли tenant-level budget limiter для noisy tenant в общей очереди?
