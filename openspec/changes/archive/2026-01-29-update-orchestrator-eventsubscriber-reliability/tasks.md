## 1. Implementation
- [x] Добавить модель/миграцию для receipts обработанных stream сообщений (уникальность `(stream, group, message_id)`).
- [x] Встроить receipt-check в обработку EventSubscriber: транзакция БД → commit → ACK; при duplicate receipt → ACK без бизнес-эффектов.
- [x] Добавить reclaim pending (PEL): периодический `XPENDING` + `XCLAIM`/`XAUTOCLAIM` для stream’ов EventSubscriber.
- [x] Определить и реализовать политику poison messages (что ACK’ать, что отправлять в DLQ/FailedEvent, что ретраить).
- [x] Добавить метрики/логи для: claimed_count, duplicate_receipt_count, poison_count, pending_size.

## 2. Tests
- [x] Unit tests: дубли сообщения не дублируют DB-сайд-эффекты (receipt).
- [x] Unit tests: сообщение, оставшееся pending, потом обрабатывается через claim.
- [x] Unit tests: poison message не приводит к бесконечному pending росту (по выбранной политике).

## 3. Validation
- [x] `./scripts/dev/lint.sh` (ruff + остальное)
- [x] `cd orchestrator && pytest apps/operations/tests/test_event_subscriber_reliability.py -q`
- [x] Проверить миграции Django на чистой БД (минимум: наличие уникального индекса)
