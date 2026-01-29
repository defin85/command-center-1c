# Change: Надёжная обработка критичных событий Redis Streams в Orchestrator (EventSubscriber)

## Why
Redis Streams события используются как **критичный** механизм бизнес-операций, а консистентность объявлена приоритетом.

Сейчас в Orchestrator EventSubscriber есть две системные проблемы, которые могут приводить к “зависшим” операциям и потере прогресса при рестартах/сбоях:

1) EventSubscriber читает только новые сообщения (`">"`) и **не занимается Pending Entries List (PEL)**. Это означает, что сообщение, доставленное конкретному consumer’у, но не ACK’нутое из‑за крэша/kill, может остаться pending и не быть обработано никогда (особенно при смене `consumer_name` после рестарта).
   - См. `orchestrator/apps/operations/event_subscriber/subscriber.py:61-69` и `orchestrator/apps/operations/event_subscriber/subscriber.py:111-125`.

2) В обработчиках нет чёткой идемпотентности “на границе БД”, поэтому при at‑least‑once доставке (и особенно после внедрения reclaim pending) дубли доставки могут приводить к повторным сайд‑эффектам или перезаписи полей (например `completed_at`, `duration_seconds`).

Для сравнения, Go Worker уже содержит логику reclaim pending через `XPENDING/XCLAIM`:
- `go-services/worker/internal/queue/stream_consumer_claim.go:39-103`.

## What Changes
Добавляем “consistency-first” контур для Orchestrator EventSubscriber:

- **Reclaim pending сообщений** для stream’ов `events:*` и `commands:*`, которые читает EventSubscriber:
  - периодически проверять pending (PEL) по consumer group;
  - забирать “протухшие” pending сообщения на себя (claim) и обрабатывать.
- **Идемпотентность на границе БД** для обработки stream‑сообщений:
  - фиксировать обработанные сообщения в Postgres (receipt/inbox) по ключу `(stream, group, message_id)`;
  - бизнес‑обработку делать в транзакции, а ACK выполнять только после успешного коммита.
- **Политика ошибок/poison messages**:
  - определяем правило: что считается “неисправимым” сообщением, когда оно уходит в DLQ/архив/failed-events и как это мониторится.

## Non-Goals
- Не меняем формат событий и протоколы Go Worker’а (envelope/payload) в рамках этого change.
- Не вводим “градации критичности” событий — все рассматриваем как критичные по консистентности.
- Не переписываем всю модель прогресса операций/тасков (только обеспечиваем корректность при повторах).

## Impact
- Изменения в Orchestrator (Python/Django):
  - `apps/operations/event_subscriber/*` (алгоритм чтения/claim/ACK);
  - новые таблицы/индексы в Postgres для receipts (миграция);
  - тесты EventSubscriber.
- Ожидается улучшение поведения при:
  - рестартах EventSubscriber;
  - сетевых проблемах Redis;
  - многопроцессном запуске subscriber’ов.

