# Design: EventSubscriber reliability (Redis Streams, at-least-once + DB-idempotency)

## Контекст и инварианты
Инвариант консистентности: **если Orchestrator принял событие от Worker’а, то состояние в Postgres должно стать истинным “ровно один раз”**, независимо от количества доставок сообщения Redis Streams.

Мы принимаем, что Redis Streams даёт **at-least-once delivery**, поэтому:
- “ровно один раз” реализуем **на границе БД** (idempotency receipts);
- `ACK` делаем только после фиксации результатов в БД.

## Проблема PEL (Pending Entries List)
Текущее чтение в Orchestrator:
- stream IDs = `">"` для всех stream’ов (`orchestrator/apps/operations/event_subscriber/subscriber.py:61-69`);
- используется `XREADGROUP` и `XACK` (`orchestrator/apps/operations/event_subscriber/subscriber.py:111-125`);
- но отсутствует reclaim pending.

Это опасно, потому что:
- при крэше между `XREADGROUP` и `XACK` сообщение остаётся в pending, и при чтении только `">"` оно не будет снова доставлено;
- `consumer_name` в Orchestrator зависит от PID (`orchestrator/apps/operations/event_subscriber/subscriber.py:58`), поэтому после рестарта “старый” consumer исчезает, а pending остаётся привязанным к нему.

## Предлагаемое решение

### 1) Receipt / Inbox в Postgres (идемпотентность на границе БД)
Добавить модель/таблицу `stream_message_receipts` (название уточняется) с уникальностью:
- `stream` (строка)
- `group` (строка)
- `message_id` (строка redis stream id)

Поля:
- `processed_at` (timestamp)
- `event_type` (опционально, для отладки)
- `correlation_id` (опционально)
- `handler` (опционально: какой обработчик применён)
- `payload_hash` (опционально: диагностика)

Алгоритм обработки одного сообщения:
1) `BEGIN`
2) `INSERT receipt (stream, group, message_id, ...)`
   - если `UNIQUE` конфликт → считаем, что сообщение уже обработано: `COMMIT` → `XACK` (чтобы “погасить” повторную доставку)
3) выполнить бизнес‑обработку (обновление `Task`, `BatchOperation`, …)
4) `COMMIT`
5) `XACK`

Это обеспечивает:
- при крэше между `COMMIT` и `XACK` сообщение придёт снова (pending/claim), но receipt предотвратит повторный DB эффект и мы просто ACK’нем;
- при повторной доставке без крэша — то же.

### 2) Reclaim pending (PEL)
Добавить отдельный цикл/периодическую проверку в EventSubscriber:
- проверять pending по group для stream’ов EventSubscriber’а;
- забирать (claim) сообщения, которые “idle” дольше порога, и прогонять их через тот же `process_message`.

Референс поведения уже есть в Go Worker:
- `go-services/worker/internal/queue/stream_consumer_claim.go:39-103` (XPENDING + XCLAIM).

Варианты:
- Redis 7+: `XAUTOCLAIM` предпочтительнее (меньше гонок, проще курсор).
- Базовый: `XPENDING`/`XPENDINGEXT` + `XCLAIM`.

На уровне параметров:
- `claim_idle_threshold` (например 5 минут, как в worker)
- `claim_check_interval` (например 30 секунд)
- `max_pending_to_check` (например 100)

### 3) Poison messages и DLQ
Уточнить правила:
- какие ошибки считаем “неисправимыми” (например, невалидный JSON envelope / неизвестный event_type / отсутствует required поле);
- куда их складывать:
  - в Redis DLQ stream (если это входной stream `commands:*`),
  - или в Postgres (аналогично `FailedEvent`) с ручным разбором.

Требование: ошибки должны быть **наблюдаемыми** (метрики/лог) и не приводить к бесконечному pending росту.

## Открытые вопросы (не блокируют proposal)
1) TTL/retention для receipts (например 30–90 дней) и джоба очистки.
2) Нужно ли хранить payload_hash / полные данные для форензики, или достаточно `stream+message_id`.

