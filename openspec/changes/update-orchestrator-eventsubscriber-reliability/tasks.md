## 1. Implementation
- [ ] Добавить модель/миграцию для receipts обработанных stream сообщений (уникальность `(stream, group, message_id)`).
- [ ] Встроить receipt-check в обработку EventSubscriber: транзакция БД → commit → ACK; при duplicate receipt → ACK без бизнес-эффектов.
- [ ] Добавить reclaim pending (PEL): периодический `XPENDING` + `XCLAIM`/`XAUTOCLAIM` для stream’ов EventSubscriber.
- [ ] Определить и реализовать политику poison messages (что ACK’ать, что отправлять в DLQ/FailedEvent, что ретраить).
- [ ] Добавить метрики/логи для: claimed_count, duplicate_receipt_count, poison_count, pending_size.

## 2. Tests
- [ ] Unit tests: дубли сообщения не дублируют DB-сайд-эффекты (receipt).
- [ ] Unit tests: сообщение, оставшееся pending, потом обрабатывается через claim.
- [ ] Unit tests: poison message не приводит к бесконечному pending росту (по выбранной политике).

## 3. Validation
- [ ] `./scripts/dev/lint.sh` (ruff + остальное)
- [ ] `cd orchestrator && pytest apps/operations/tests/test_event_subscriber.py -q`
- [ ] Проверить миграции Django на чистой БД (минимум: наличие уникального индекса)

